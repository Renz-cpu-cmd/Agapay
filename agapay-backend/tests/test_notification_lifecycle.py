from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import AuthSession, NotificationDevice, NotificationDelivery, User, utc_now
from app.notification_schemas import DeviceRegistration
from app.services.accounts import current_user, revoke_session, revoke_sessions, token_digest
from app.services.notification_provider import FakeNotificationProvider
from app.services.notification_service import device_is_eligible, process_pending
from test_accounts import PASSWORD, headers, reset_accounts, sign_in, staff
from test_alerts import send, station
from test_notifications import TOKEN, register, registration, resident, rows


def digest(access):
    return token_digest(access["Authorization"].removeprefix("Bearer "))


def expire(access):
    with SessionLocal() as db:
        db.execute(update(AuthSession).where(AuthSession.token_hash == digest(access))
                   .values(expires_at=utc_now() - timedelta(days=1)))
        db.commit()


def two_phones(client):
    a = resident(client)
    phone_a = register(client, a)
    b = headers(sign_in(client, "resident@example.com"))
    phone_b = register(client, b, token=TOKEN + "-phone-b", installation=str(uuid4()))
    return a, phone_a, b, phone_b


@pytest.mark.parametrize("prune", [False, True])
@pytest.mark.parametrize("expire_before_capture", [False, True])
def test_natural_expiry_preserves_capture_and_processing(client, station, prune, expire_before_capture):
    access = resident(client)
    device = register(client, access)
    if not expire_before_capture:
        send(client, station, 1, 100)
    expire(access)
    if prune:
        assert sign_in(client, "resident@example.com").status_code == 200
        with SessionLocal() as db:
            assert db.get(AuthSession, digest(access)) is None
    assert client.get("/api/auth/me", headers=access).status_code == 401
    assert client.delete(f"/api/notification-devices/{device['id']}", headers=access).status_code == 401
    assert client.post("/api/notification-devices", headers=access, json=registration()).status_code == 401
    if expire_before_capture:
        send(client, station, 1, 100)
    delivery, = rows(NotificationDelivery)
    assert delivery.device_id == device["id"]
    with SessionLocal() as db:
        current = db.get(NotificationDevice, device["id"])
        assert current.enabled and current.revision == 1 and device_is_eligible(db, current)
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 1 and len(provider.messages) == 1
    assert rows(NotificationDelivery)[0].state == "TESTED"


@pytest.mark.parametrize("session_state", ["current", "expired", "pruned"])
def test_logout_authoritatively_disables_without_mobile_delete(client, station, session_state):
    access = resident(client)
    device = register(client, access)
    if session_state != "current":
        expire(access)
    if session_state == "pruned":
        sign_in(client, "resident@example.com")
    # Intentionally skip mobile DELETE. Logout itself owns this cleanup.
    response = client.post("/api/auth/logout", headers=access)
    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    with SessionLocal() as db:
        current = db.get(NotificationDevice, device["id"])
        assert not current.enabled and current.provider_token is None and current.token_hash is None
        assert current.revision == 2 and db.get(AuthSession, digest(access)) is None
    assert client.post("/api/auth/logout", headers=access).status_code == 204
    assert rows(NotificationDevice)[0].revision == 2
    send(client, station, 1, 100)
    assert rows(NotificationDelivery) == []


def test_logout_session_a_preserves_session_b_and_other_account(client, station):
    a, phone_a, b, phone_b = two_phones(client)
    other = register(client, resident(client, "other@example.com"), token=TOKEN + "-other")
    assert client.post("/api/auth/logout", headers=a).status_code == 204
    with SessionLocal() as db:
        assert not db.get(NotificationDevice, phone_a["id"]).enabled
        assert db.get(NotificationDevice, phone_b["id"]).enabled
        assert db.get(NotificationDevice, other["id"]).enabled
        assert db.get(AuthSession, digest(b)) is not None
    send(client, station, 1, 100)
    assert {d.device_id for d in rows(NotificationDelivery)} == {phone_b["id"], other["id"]}


@pytest.mark.parametrize("prune_old_session", [False, True])
def test_password_revokes_all_devices_including_pruned_provenance(client, station, prune_old_session):
    a, phone_a, b, phone_b = two_phones(client)
    if prune_old_session:
        expire(a)
        sign_in(client, "resident@example.com")
        with SessionLocal() as db:
            assert db.get(AuthSession, digest(a)) is None
    response = client.patch("/api/auth/me", headers=b,
                            json={"current_password": PASSWORD, "password": PASSWORD + "-changed"})
    assert response.status_code == 200
    for access in (a, b):
        assert client.get("/api/auth/me", headers=access).status_code == 401
    for device in rows(NotificationDevice):
        assert not device.enabled and device.provider_token is None and device.token_hash is None
        assert device.revision == 2
    send(client, station, 1, 100)
    assert rows(NotificationDelivery) == []
    fresh = headers(sign_in(client, "resident@example.com", password=PASSWORD + "-changed"))
    renewed = register(client, fresh, token=TOKEN + "-renewed")
    assert renewed["id"] == phone_a["id"]
    assert client.post("/api/auth/logout", headers=a).status_code == 204
    assert client.post("/api/auth/logout", headers=b).status_code == 204
    with SessionLocal() as db:
        assert db.get(NotificationDevice, renewed["id"]).enabled
        assert db.get(NotificationDevice, renewed["id"]).revision == 3
        assert not db.get(NotificationDevice, phone_b["id"]).enabled


@pytest.mark.parametrize("change", [{"is_active": False}, {"role": "officer"}])
def test_admin_security_changes_disable_and_do_not_auto_reactivate(client, station, change):
    access = resident(client)
    device = register(client, access)
    admin = staff(client)
    with SessionLocal() as db:
        user_id = db.get(NotificationDevice, device["id"]).user_id
    assert client.patch(f"/api/users/{user_id}", headers=admin, json=change).status_code == 200
    assert client.patch(f"/api/users/{user_id}", headers=admin,
                        json={"is_active": True, "role": "resident"}).status_code == 200
    with SessionLocal() as db:
        current = db.get(NotificationDevice, device["id"])
        assert not current.enabled and current.provider_token is None
    send(client, station, 1, 100)
    assert rows(NotificationDelivery) == []


def test_expired_session_token_cannot_be_taken_by_another_resident(client):
    access = resident(client)
    device = register(client, access)
    expire(access)
    other = resident(client, "other@example.com")  # also prunes expired sessions
    assert client.post("/api/notification-devices", headers=other, json=registration()).status_code == 409
    with SessionLocal() as db:
        assert db.get(NotificationDevice, device["id"]).enabled


@pytest.mark.parametrize("missing", ["provider_token", "token_hash"])
@pytest.mark.parametrize("capture_first", [False, True])
def test_empty_token_fields_ineligible_at_capture_and_processing(client, station, missing, capture_first):
    access = resident(client)
    device = register(client, access)
    if capture_first:
        send(client, station, 1, 100)
    with SessionLocal() as db:
        db.execute(update(NotificationDevice).where(NotificationDevice.id == device["id"]).values({missing: ""}))
        db.commit()
    if not capture_first:
        send(client, station, 1, 100)
        assert rows(NotificationDelivery) == []
    else:
        provider = FakeNotificationProvider()
        process_pending(provider)
        assert not provider.messages and rows(NotificationDelivery)[0].state == "SUPPRESSED"


@pytest.mark.parametrize("all_sessions", [False, True])
def test_revocation_and_device_changes_roll_back_atomically(client, all_sessions):
    access = resident(client)
    device = register(client, access)
    with SessionLocal() as db:
        if all_sessions:
            revoke_sessions(db, db.get(NotificationDevice, device["id"]).user_id)
        else:
            revoke_session(db, digest(access))
        db.rollback()
    with SessionLocal() as db:
        assert db.get(AuthSession, digest(access)) is not None
        current = db.get(NotificationDevice, device["id"])
        assert current.enabled and current.revision == 1 and current.provider_token is not None


@pytest.mark.parametrize("all_sessions", [False, True])
def test_stale_authenticated_registration_cannot_restore_revoked_device(client, monkeypatch, all_sessions):
    # Deterministic race: request authenticated; revocation holds the account
    # lock; registration waits, then must reject its now-revoked API session.
    from app.routers import notification_devices
    access = resident(client)
    device = register(client, access)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer",
        credentials=access["Authorization"].removeprefix("Bearer "))
    authenticated, attempt_lock = Event(), Event()
    release_registration = Event()
    real_lock = notification_devices.lock_account
    def observed_lock(db, user_id):
        attempt_lock.set()
        real_lock(db, user_id)
    monkeypatch.setattr(notification_devices, "lock_account", observed_lock)
    def delayed_registration():
        with SessionLocal() as db:
            user = current_user(credentials, db)
            authenticated.set()
            assert release_registration.wait(5)
            try:
                notification_devices.register_device(
                    DeviceRegistration(**registration(token=TOKEN + "-late")), user, credentials, db)
            except HTTPException as exc:
                return exc.status_code
            return 200
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(delayed_registration)
        assert authenticated.wait(5)
        with SessionLocal() as db:
            if all_sessions:
                revoke_sessions(db, db.get(NotificationDevice, device["id"]).user_id)
            else:
                revoke_session(db, digest(access))
            release_registration.set()
            assert attempt_lock.wait(5)
            db.commit()
        assert future.result(timeout=10) == 401
    with SessionLocal() as db:
        current = db.get(NotificationDevice, device["id"])
        assert not current.enabled and current.provider_token is None and current.revision == 2
