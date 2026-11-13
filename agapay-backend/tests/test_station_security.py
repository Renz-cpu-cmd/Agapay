"""F01/F02 acceptance using real auth/provisioning and mocked broker transport."""
from datetime import timedelta
import json
from types import SimpleNamespace
from uuid import uuid4

import paho.mqtt.client as mqtt
from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.main import app
from app.models import (Alert, AlertTransition, NotificationDelivery, NotificationEvent, Station,
                        StationAuditEvent, StationCredential, StationIdentity, StationIngressBudget, Telemetry, utc_now)
from app.services.mqtt_subscriber import start_mqtt_subscriber
from app.services.station_security import digest
from test_accounts import account, headers, reset_accounts, staff
from test_alerts import payload
from test_rain_gauge import event


def commissioning(**changes):
    return {"device_id": "DEVICE_" + uuid4().hex, "state": "commissioned", "coordinates_verified": True,
            "reference_datum": "Synthetic surveyed test datum", "calibration_note": "Fixture only; not field calibration",
            "reason": "Controlled security acceptance test", "source_class": "physical_device", "stream": "operational",
            "provenance_evidence": "Synthetic acceptance identity; not field proof", **changes}


def provision(client, access, **changes):
    station_id = "SEC_" + uuid4().hex[:16].upper()
    body = {"station_id": station_id, "station_name": "Disposable security fixture",
            "latitude": 15.98, "longitude": 120.56, "commissioning": commissioning(), **changes}
    return body, client.post("/api/stations", headers=access, json=body)


@pytest.fixture
def device(client):
    admin = staff(client)
    body, response = provision(client, admin)
    assert response.status_code == 201, response.text
    station_id = body["station_id"]
    issued = client.post(f"/api/stations/{station_id}/credentials", headers=admin, json={
        "expected_version": 1, "label": "Acceptance device", "reason": "Controlled provisioning test",
    })
    assert issued.status_code == 201, issued.text
    return station_id, admin, issued.json()


def business_counts():
    with SessionLocal() as db:
        return tuple(db.scalar(select(func.count()).select_from(model)) for model in (
            Station, Telemetry, Alert, AlertTransition, NotificationEvent, NotificationDelivery))


def token_headers(issued):
    return {"Authorization": "Bearer " + issued["ingest_token"]}


@pytest.mark.parametrize("role", ["anonymous", "resident", "officer", "invalid", "station"])
def test_station_provisioning_denies_non_admin_without_writes(client, device, role):
    _, _, issued = device
    access = {} if role == "anonymous" else {"Authorization": "Bearer invalid"}
    if role == "resident":
        access = headers(client.post("/api/auth/register", json=account()))
    elif role == "officer":
        access = staff(client, "officer")
    elif role == "station":
        access = token_headers(issued)
    before = business_counts()
    _, response = provision(client, access)
    assert response.status_code == (403 if role in ("resident", "officer") else 401)
    assert business_counts() == before


def test_admin_provisioning_audits_calibration_binding_activation_and_actor(client, device):
    station_id, admin, _ = device
    result = client.get(f"/api/stations/{station_id}/provisioning", headers=admin)
    assert result.status_code == 200 and result.json()["state"] == "commissioned"
    assert result.json()["version"] == 1 and result.json()["coordinates_verified"] is True
    audit = client.get(f"/api/stations/{station_id}/audit", headers=admin).json()
    assert {row["action"] for row in audit} == {"station_provisioned", "credential_issued"}
    provisioned = next(row for row in audit if row["action"] == "station_provisioned")
    assert provisioned["actor_id"] > 0 and provisioned["actor_name"]
    assert provisioned["reason"] == "Controlled security acceptance test"
    assert provisioned["details"]["after"]["reference_datum"] == "Synthetic surveyed test datum"
    assert provisioned["details"]["station"]["status"] == "active"
    assert provisioned["details"]["station"]["latitude"] == 15.98


@pytest.mark.parametrize("role", ["anonymous", "resident", "officer", "device"])
def test_every_station_administration_operation_requires_admin(client, device, role):
    station_id, _, issued = device
    access = {}
    if role == "resident": access = headers(client.post("/api/auth/register", json=account()))
    if role == "officer": access = staff(client, "officer")
    if role == "device": access = token_headers(issued)
    root = f"/api/stations/{station_id}"
    operations = [
        ("GET", root + "/provisioning", None), ("GET", root + "/credentials", None),
        ("GET", root + "/audit", None),
        ("POST", root + "/commission", {**commissioning(), "expected_version": 1}),
        ("POST", root + "/credentials", {"expected_version": 1, "label": "Forbidden", "reason": "Must be rejected"}),
        ("POST", root + f"/credentials/{issued['id']}/revoke", {"reason": "Must be rejected"}),
    ]
    with SessionLocal() as db:
        audits = db.scalar(select(func.count()).select_from(StationAuditEvent))
    for method, path, body in operations:
        result = client.request(method, path, headers=access, **({"json": body} if body else {}))
        assert result.status_code == (403 if role in ("resident", "officer") else 401)
    with SessionLocal() as db:
        assert db.get(StationIdentity, station_id).version == 1
        assert db.get(StationCredential, issued["id"]).revoked_at is None
        assert db.scalar(select(func.count()).select_from(StationAuditEvent)) == audits


def test_pending_requires_explicit_commission_and_conflicts_do_not_overwrite(client):
    admin = staff(client)
    meta = commissioning(state="pending", coordinates_verified=False)
    body, created = provision(client, admin, commissioning=meta)
    assert created.status_code == 201 and created.json()["status"] == "inactive"
    station_id = body["station_id"]
    endpoint = f"/api/stations/{station_id}"
    assert client.post(endpoint + "/credentials", headers=admin, json={
        "expected_version": 1, "label": "pending", "reason": "Must not be issued"}).status_code == 409
    assert client.post(endpoint + "/commission", headers=admin, json={
        **meta, "expected_version": 1, "state": "commissioned"}).status_code == 422
    approved = {**meta, "coordinates_verified": True, "state": "commissioned", "expected_version": 1}
    assert client.post(endpoint + "/commission", headers=admin, json=approved).status_code == 200
    assert client.post(endpoint + "/commission", headers=admin, json=approved).status_code == 409
    assert client.get(endpoint + "/provisioning", headers=admin).json()["version"] == 2


@pytest.mark.parametrize("changes", [
    {"commissioning": commissioning(coordinates_verified=False)},
    {"latitude": None}, {"commissioning": commissioning(reason=" ")},
    {"commissioning": commissioning(reference_datum=" ")},
])
def test_incomplete_commissioning_rolls_back_station_and_audit(client, changes):
    admin = staff(client)
    before = business_counts()
    body, response = provision(client, admin, **changes)
    assert response.status_code == 422
    assert business_counts() == before
    with SessionLocal() as db:
        assert db.scalar(select(StationAuditEvent.id).where(StationAuditEvent.station_id == body["station_id"])) is None


def test_duplicate_device_binding_is_atomic(client, device):
    station_id, admin, _ = device
    meta = client.get(f"/api/stations/{station_id}/provisioning", headers=admin).json()
    before = business_counts()
    _, response = provision(client, admin, commissioning=commissioning(device_id=meta["device_id"]))
    assert response.status_code == 409 and business_counts() == before


def test_pending_station_without_location_can_be_commissioned_with_audited_coordinates(client):
    admin = staff(client)
    meta = commissioning(state="pending", coordinates_verified=False)
    body, created = provision(client, admin, latitude=None, longitude=None, commissioning=meta)
    assert created.status_code == 201
    root = f"/api/stations/{body['station_id']}"
    update = {**meta, "state": "commissioned", "coordinates_verified": True, "expected_version": 1,
              "latitude": 15.98, "longitude": 120.56}
    assert client.post(root + "/commission", headers=admin, json=update).status_code == 200
    audit = client.get(root + "/audit", headers=admin).json()[0]
    assert audit["details"]["station_before"]["latitude"] is None
    assert audit["details"]["station"]["latitude"] == 15.98
    public = client.get(root).json()
    assert public["latitude"] == 15.98 and public["status"] == "active"


@pytest.mark.parametrize("kind", ["anonymous", "invalid", "staff", "resident", "expired", "revoked", "other_station", "wrong_transport"])
def test_http_denial_cannot_change_telemetry_alerts_outbox_or_heartbeat(client, device, kind):
    station_id, admin, issued = device
    reading = payload(station_id, 1, 105)
    access = token_headers(issued)
    if kind == "anonymous": access = {}
    if kind == "invalid": access = {"Authorization": "Bearer agi_" + "x" * 43}
    if kind == "staff": access = admin
    if kind == "resident": access = headers(client.post("/api/auth/register", json=account()))
    if kind == "other_station": reading["station_id"] = "STATION_001"
    if kind in ("expired", "wrong_transport"):
        with SessionLocal() as db:
            credential = db.get(StationCredential, issued["id"])
            if kind == "expired": credential.expires_at = utc_now() - timedelta(seconds=1)
            else: credential.transport = "mqtt"
            db.commit()
    if kind == "revoked":
        endpoint = f"/api/stations/{station_id}/credentials/{issued['id']}/revoke"
        assert client.post(endpoint, headers=admin, json={"reason": "Lost test device"}).status_code == 200
    before = business_counts()
    result = client.post("/api/telemetry", headers=access, json=reading)
    assert result.status_code == (403 if kind in ("other_station", "wrong_transport") else 401)
    assert business_counts() == before
    with SessionLocal() as db:
        assert db.scalar(select(Station).where(Station.station_id == station_id)).last_ping is None


def test_valid_station_http_works_and_secrets_are_not_readable_or_audited(client, device):
    station_id, admin, issued = device
    assert issued["expires_at"].endswith("Z") and issued["created_at"].endswith("Z")
    access = token_headers(issued)
    response = client.post("/api/telemetry", headers=access, json=payload(station_id, 1, 105))
    assert response.status_code == 201
    assert issued["ingest_token"] not in response.text
    assert client.post("/api/telemetry", headers=access, json=payload(station_id, 1, 105)).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(Alert).where(Alert.station_id == station_id)).current_severity == "EVACUATE"
        assert db.get(StationCredential, issued["id"]).token_hash == digest(issued["ingest_token"])
    for suffix in ("credentials", "audit", "provisioning"):
        result = client.get(f"/api/stations/{station_id}/{suffix}", headers=admin)
        assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
        assert issued["ingest_token"] not in result.text and "token_hash" not in result.text
        assert client.get(f"/api/stations/{station_id}/{suffix}", headers=access).status_code == 401
    assert client.get("/api/stations").status_code == 200
    assert client.get(f"/api/telemetry/{station_id}/latest").status_code == 200


def test_recommission_invalidates_old_tokens_and_revoke_is_idempotent(client, device):
    station_id, admin, issued = device
    endpoint = f"/api/stations/{station_id}"
    assert client.post(endpoint + "/commission", headers=admin, json={
        **commissioning(state="decommissioned"), "expected_version": 1,
    }).status_code == 200
    assert client.post("/api/telemetry", headers=token_headers(issued), json=payload(station_id, 1, 105)).status_code == 401
    revoke = endpoint + f"/credentials/{issued['id']}/revoke"
    first = client.post(revoke, headers=admin, json={"reason": "Confirm revocation"})
    again = client.post(revoke, headers=admin, json={"reason": "Repeated action"})
    assert first.status_code == again.status_code == 200
    assert first.json()["revoked_at"] == again.json()["revoked_at"]


def test_http_budget_counts_duplicates_and_is_shared_across_sessions(client, device):
    station_id, _, issued = device
    settings = Settings(telemetry_ingest_per_minute=2)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        access, reading = token_headers(issued), payload(station_id, 1, 105)
        assert client.post("/api/telemetry", headers=access, json=reading).status_code == 201
        assert client.post("/api/telemetry", headers=access, json=reading).status_code == 409
        before = business_counts()
        limited = client.post("/api/telemetry", headers=access, json=payload(station_id, 2, 0))
        assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
        assert business_counts() == before
        with SessionLocal() as db:
            assert db.get(StationIngressBudget, (station_id, "telemetry")).attempts == 2
            db.get(StationIngressBudget, (station_id, "telemetry")).window_start = utc_now() - timedelta(minutes=2)
            db.commit()
        assert client.post("/api/telemetry", headers=access, json=payload(station_id, 2, 0)).status_code == 201
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_body_budget_applies_before_json_and_to_streams_without_content_length(client, device):
    station_id, _, issued = device
    before = business_counts()
    response = client.post("/api/telemetry", headers=token_headers(issued), content=b"x" * 4097)
    assert response.status_code == 413
    response = client.post("/api/telemetry", headers=token_headers(issued), content=iter([b"x" * 2048, b"x" * 2049]))
    assert response.status_code == 413
    assert business_counts() == before


@pytest.fixture
def mqtt_transport(monkeypatch, tmp_path, device):
    station_id, _, _ = device
    monkeypatch.setattr(mqtt.Client, "connect_async", lambda *a, **k: None)
    monkeypatch.setattr(mqtt.Client, "loop_start", lambda *a, **k: None)
    acks = []
    monkeypatch.setattr(mqtt.Client, "publish", lambda self, topic, value, **kw: acks.append((topic, value)))
    settings = Settings(mqtt_username="backend-ingest", mqtt_password="synthetic-broker-password",
        rain_gauge_enabled=True, rain_gauge_calibrations={station_id: .7, "STATION_001": .7}, rain_gauge_store_path=str(tmp_path / "rain.db"))
    return start_mqtt_subscriber(settings), acks, settings


def deliver(subscriber, station_id, body, *, channel="telemetry", retain=False):
    encoded = body if isinstance(body, bytes) else json.dumps(body).encode()
    subscriber.on_message(subscriber, None, SimpleNamespace(
        topic=f"agapay/stations/{station_id}/{channel}", payload=encoded, retain=retain))


@pytest.mark.parametrize("kind", ["anonymous", "invalid", "expired", "revoked", "other_station", "wrong_transport", "retained", "oversized"])
@pytest.mark.parametrize("channel", ["telemetry", "rain"])
def test_mqtt_denials_leave_both_stores_and_outbox_unchanged(client, device, mqtt_transport, kind, channel, caplog):
    station_id, admin, issued = device
    sub, acks, settings = mqtt_transport
    inner = payload(station_id, 1, 105) if channel == "telemetry" else event(station=station_id).model_dump()
    envelope = {"ingest_token": issued["ingest_token"], channel: inner}
    if kind == "anonymous": envelope.pop("ingest_token")
    if kind == "invalid": envelope["ingest_token"] = "agi_" + "z" * 43
    if kind in ("expired", "revoked", "wrong_transport"):
        with SessionLocal() as db:
            credential = db.get(StationCredential, issued["id"])
            if kind == "expired": credential.expires_at = utc_now() - timedelta(seconds=1)
            elif kind == "revoked": credential.revoked_at = utc_now()
            else: credential.transport = "http"
            db.commit()
    topic_station = "STATION_001" if kind == "other_station" else station_id
    if kind == "other_station": inner["station_id"] = topic_station
    before = business_counts()
    deliver(sub, topic_station, b"x" * 4097 if kind == "oversized" else envelope,
            channel=channel, retain=kind == "retained")
    assert business_counts() == before and acks == []
    assert not __import__("pathlib").Path(settings.rain_gauge_store_path).exists()
    assert issued["ingest_token"] not in caplog.text


def test_valid_mqtt_water_and_rain_use_station_credential(client, device, mqtt_transport):
    from pathlib import Path
    from app.services.rain_gauge_service import RainGaugeStore
    station_id, _, issued = device
    sub, acks, settings = mqtt_transport
    deliver(sub, station_id, {"ingest_token": issued["ingest_token"], "telemetry": payload(station_id, 1, 105)})
    with SessionLocal() as db:
        assert db.scalar(select(Alert).where(Alert.station_id == station_id)).current_severity == "EVACUATE"
    for reading in (event(station=station_id), event(1, 2, 1000, station=station_id)):
        deliver(sub, station_id, {"ingest_token": issued["ingest_token"], "rain": reading.model_dump()}, channel="rain")
    assert len(acks) == 3
    assert sum(topic.endswith('/telemetry-ack') for topic,_ in acks) == 1
    assert sum(topic.endswith('/rain-ack') for topic,_ in acks) == 2
    snapshot = RainGaugeStore(Path(settings.rain_gauge_store_path)).snapshot(station_id, "physical_rain_gauge")
    assert snapshot["accepted_tip_count"] == 1
    assert issued["ingest_token"] not in json.dumps(acks)


def test_broker_startup_requires_authentication_and_production_tls(monkeypatch):
    for settings in (Settings(mqtt_username="", mqtt_password=""),
                     Settings(mqtt_username="backend", mqtt_password="test-only", mqtt_tls=False).model_copy(update={"environment":"production"})):
        with pytest.raises(ValueError): start_mqtt_subscriber(settings)


def test_ingress_http_and_mqtt_share_the_database_budget(client, device, mqtt_transport):
    station_id, _, issued = device
    subscriber, _, settings = mqtt_transport
    settings.telemetry_ingest_per_minute = 1
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        assert client.post("/api/telemetry", headers=token_headers(issued), json=payload(station_id, 1, 85)).status_code == 201
        before = business_counts()
        deliver(subscriber, station_id, {"ingest_token": issued["ingest_token"], "telemetry": payload(station_id, 2, 105)})
        assert business_counts() == before
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.parametrize("action", ["revoke", "expire"])
def test_credential_is_rechecked_after_quota_commit(client, device, monkeypatch, action):
    from app.services.station_security import prepare_ingress
    station_id, _, issued = device
    before = business_counts()
    with SessionLocal() as db:
        original = db.commit
        def commit_then_invalidate():
            original()
            with SessionLocal() as other:
                credential = other.get(StationCredential, issued["id"])
                if action == "revoke": credential.revoked_at = utc_now()
                else: credential.expires_at = utc_now() - timedelta(seconds=1)
                other.commit()
        monkeypatch.setattr(db, "commit", commit_then_invalidate)
        with pytest.raises(HTTPException) as failure:
            prepare_ingress(db, issued["ingest_token"], station_id, "http", "telemetry", Settings())
        assert failure.value.status_code == 401
    assert business_counts() == before


def test_ingress_requires_https_outside_development(client, device):
    station_id, _, issued = device
    app.dependency_overrides[get_settings] = lambda: Settings().model_copy(update={"environment":"production"})
    try:
        before = business_counts()
        result = client.post("/api/telemetry", headers=token_headers(issued), json=payload(station_id, 1, 105))
        assert result.status_code == 400 and business_counts() == before
        result = client.post("https://testserver/api/telemetry", headers=token_headers(issued), json=payload(station_id, 1, 105))
        assert result.status_code == 201
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.parametrize("change", ["pending", "uncommissioned", "stale_binding"])
def test_credential_alone_cannot_bypass_commissioning_gate(client, device, change):
    station_id, _, issued = device
    with SessionLocal() as db:
        identity = db.get(StationIdentity, station_id)
        if change == "pending": identity.state = "pending"
        elif change == "uncommissioned": db.delete(identity)
        else: identity.version += 1
        try:
            db.commit()
        except IntegrityError:
            # PostgreSQL enforces station_credentials -> station_identities: a credential can
            # never outlive its commissioned identity, so the bypass cannot even be set up.
            assert change == "uncommissioned" and db.bind.dialect.name == "postgresql"
            db.rollback()
            return
    before = business_counts()
    result = client.post("/api/telemetry", headers=token_headers(issued), json=payload(station_id, 1, 105))
    assert result.status_code == 403 and business_counts() == before


def test_additive_security_migration_preserves_existing_rows_and_is_repeatable(tmp_path):
    from app.database import Base
    from app.migrate_station_security import TABLES, migrate
    target = create_engine(f"sqlite:///{(tmp_path / 'existing.db').as_posix()}")
    try:
        core = [table for table in Base.metadata.sorted_tables if table not in TABLES]
        Base.metadata.create_all(target, tables=core)
        with target.begin() as connection:
            connection.execute(Station.__table__.insert().values(station_id="PRESERVE", station_name="Keep me", sensor_height_cm=120))
        assert set(migrate(target)) == {table.name for table in TABLES}
        migrate(target, apply=True)
        assert migrate(target, apply=True) == []
        with target.connect() as connection:
            assert connection.scalar(select(Station.station_name).where(Station.station_id == "PRESERVE")) == "Keep me"
        assert all(inspect(target).has_table(table.name) for table in TABLES)
    finally:
        target.dispose()
