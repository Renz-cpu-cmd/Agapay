from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import SosRequest, User, utc_now
from test_accounts import account, headers, reset_accounts, staff


def payload(**changes):
    return dict(request_id=str(uuid4()), location="Practice site near San Vicente barangay hall",
                message="Practice only: assistance scenario", latitude=15.976145, longitude=120.571203,
                location_source="manual", **changes)


@pytest.fixture
def resident(client):
    return headers(client.post("/api/auth/register", json=account()))


def test_create_snapshot_practice_history_and_private_access(client, resident):
    assert client.get("/api/sos").status_code == 401
    response = client.post("/api/sos", headers=resident, json=payload())
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    item = response.json()
    assert item["practice"] is True and item["status"] == "ACTIVE"
    assert item["resident_name"] == "Test Resident"
    assert item["created_at"].endswith("Z")
    assert "payload_hash" not in item and "password" not in response.text
    other = headers(client.post("/api/auth/register", json=account("other@example.com")))
    assert client.get("/api/sos", headers=other).json()["total"] == 0
    assert client.get(f"/api/sos/{item['id']}", headers=other).status_code == 404
    assert client.get("/api/sos", headers=resident).json()["items"][0]["id"] == item["id"]
    officer = staff(client, "officer")
    assert client.get("/api/sos", headers=officer).json()["total"] == 1
    assert client.post("/api/sos", headers=officer, json=payload()).status_code == 403
    client.patch("/api/auth/me", headers=resident, json={"name": "Changed Resident"})
    assert client.get(f"/api/sos/{item['id']}", headers=resident).json()["resident_name"] == "Test Resident"


def test_retry_is_deduplicated_and_changed_payload_conflicts(client, resident):
    data = payload()
    first = client.post("/api/sos", headers=resident, json=data).json()
    retry = client.post("/api/sos", headers=resident, json=data)
    assert retry.status_code == 200 and retry.json() == first
    assert client.post("/api/sos", headers=resident, json={**data, "message": "Changed"}).status_code == 409
    with SessionLocal() as db:
        assert len(db.scalars(select(SosRequest)).all()) == 1


def test_staff_transitions_are_ordered_audited_and_idempotent(client, resident):
    officer = staff(client, "officer")
    admin = staff(client)
    data = payload()
    item = client.post("/api/sos", headers=resident, json=data).json()
    url = f"/api/sos/{item['id']}"
    assert client.patch(url, headers=resident, json={"status": "ACKNOWLEDGED"}).status_code == 403
    assert client.patch(url, headers=officer, json={"status": "RESOLVED"}).status_code == 409
    ack = client.patch(url, headers=officer, json={"status": "ACKNOWLEDGED"}).json()
    assert ack["status"] == "ACKNOWLEDGED" and ack["acknowledged_at"].endswith("Z")
    assert client.patch(url, headers=admin, json={"status": "ACKNOWLEDGED"}).json() == ack
    resolved = client.patch(url, headers=admin, json={"status": "RESOLVED", "resolution_note": "Practice exercise complete."}).json()
    assert resolved["status"] == "RESOLVED" and resolved["resolved_by_name"] == "Test Resident"
    assert resolved["acknowledged_at"] == ack["acknowledged_at"]
    assert client.patch(url, headers=officer, json={"status": "RESOLVED", "resolution_note": "Overwrite"}).json() == resolved
    assert client.patch(url, headers=officer, json={"status": "ACKNOWLEDGED"}).status_code == 409
    assert client.patch(url, headers=officer, json={"status": "ACTIVE"}).status_code == 422
    assert client.get(url, headers=resident).json() == resolved
    assert client.post("/api/sos", headers=resident, json=data).json() == resolved


@pytest.mark.parametrize("changes", [
    {"latitude": 91}, {"longitude": -181}, {"longitude": None}, {"location": " "},
    {"message": "x" * 1001}, {"user_id": 99}, {"practice": False}, {"status": "RESOLVED"},
    {"location_source": "gps"}, {"accuracy_m": 8}, {"request_id": "invalid"},
])
def test_invalid_location_and_identity_injection_rejected(client, resident, changes):
    assert client.post("/api/sos", headers=resident, json={**payload(), **changes}).status_code == 422


def test_manual_fallback_and_stale_gps(client, resident):
    assert client.post("/api/sos", headers=resident, json={**payload(), "latitude": None, "longitude": None}).status_code == 201
    data = {**payload(), "location_source": "gps", "accuracy_m": 10, "location_recorded_at": utc_now().isoformat()}
    first = client.post("/api/sos", headers=resident, json=data)
    assert first.status_code == 201
    assert client.post("/api/sos", headers=resident, json=data).status_code == 200
    for captured in (utc_now() - timedelta(minutes=11), utc_now() + timedelta(minutes=2)):
        assert client.post("/api/sos", headers=resident, json={**data, "request_id": str(uuid4()), "location_recorded_at": captured.isoformat()}).status_code == 422


def test_owner_can_share_fresh_location_until_request_is_resolved(client, resident):
    officer = staff(client, "officer")
    other = headers(client.post("/api/auth/register", json=account("other@example.com")))
    item = client.post("/api/sos", headers=resident, json=payload()).json()
    url = f"/api/sos/{item['id']}/location"
    captured = utc_now()
    fix = dict(latitude=15.97883, longitude=120.56382, accuracy_m=7.5,
               location_recorded_at=captured.isoformat())

    updated = client.patch(url, headers=resident, json=fix)
    assert updated.status_code == 200
    assert updated.json()["location_source"] == "gps"
    assert updated.json()["latitude"] == 15.97883
    assert updated.json()["location_recorded_at"].endswith("Z")
    assert client.get(f"/api/sos/{item['id']}", headers=officer).json()["longitude"] == 120.56382
    assert client.patch(url, headers=resident, json=fix).status_code == 200
    assert client.patch(url, headers=other, json=fix).status_code == 404
    assert client.patch(url, headers=officer, json=fix).status_code == 403

    older = {**fix, "location_recorded_at": (captured - timedelta(seconds=1)).isoformat()}
    assert client.patch(url, headers=resident, json=older).status_code == 409
    assert client.patch(f"/api/sos/{item['id']}", headers=officer,
                        json={"status": "ACKNOWLEDGED"}).status_code == 200
    assert client.patch(f"/api/sos/{item['id']}", headers=officer,
                        json={"status": "RESOLVED"}).status_code == 200
    assert client.patch(url, headers=resident, json={**fix, "location_recorded_at": utc_now().isoformat()}).status_code == 409


@pytest.mark.parametrize("changes", [
    {"latitude": 91}, {"longitude": 181}, {"accuracy_m": -1},
    lambda: {"location_recorded_at": (utc_now() - timedelta(minutes=3)).isoformat()},
    lambda: {"location_recorded_at": (utc_now() + timedelta(minutes=2)).isoformat()},
    {"location_source": "gps"},
])
def test_live_location_rejects_invalid_or_injected_data(client, resident, changes):
    # Resolve time-relative inputs at execution, not collection: longer suites
    # must not turn an invalid future fix into a valid current fix.
    if callable(changes):
        changes = changes()
    item = client.post("/api/sos", headers=resident, json=payload()).json()
    fix = dict(latitude=15.97883, longitude=120.56382, accuracy_m=7.5,
               location_recorded_at=utc_now().isoformat())
    assert client.patch(f"/api/sos/{item['id']}/location", headers=resident,
                        json={**fix, **changes}).status_code == 422


def test_paging_filter_counts_and_revocation(client, resident):
    officer = staff(client, "officer")
    ids = [client.post("/api/sos", headers=resident, json=payload()).json()["id"] for _ in range(3)]
    client.patch(f"/api/sos/{ids[0]}", headers=officer, json={"status": "ACKNOWLEDGED"})
    page = client.get("/api/sos?status=ACTIVE&limit=1&offset=1", headers=officer).json()
    assert page["total"] == 2 and page["items"][0]["id"] == ids[1]
    assert page["counts"] == {"ACTIVE": 2, "ACKNOWLEDGED": 1, "RESOLVED": 0}
    assert client.get("/api/sos?limit=1000", headers=officer).status_code == 422
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "officer@example.com"))
        user.is_active = False
        db.commit()
    assert client.get("/api/sos", headers=officer).status_code == 401
    assert client.patch(f"/api/sos/{ids[1]}", headers=officer, json={"status": "ACKNOWLEDGED"}).status_code == 401
