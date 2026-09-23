from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.database import SessionLocal
from app.models import (AlertTransition, AuthSession, NotificationDevice, NotificationDelivery,
                        NotificationEvent, User, utc_now)
from app.services.notification_provider import (
    FakeNotificationProvider, NoopNotificationProvider, PushTarget, SendOutcome, configured_provider)
from app.services.notification_service import enqueue_transition, process_pending
from app.services.telemetry_service import ingest_telemetry
from app.schemas import TelemetryCreate
from test_accounts import account, headers, reset_accounts, staff
from test_alerts import episodes, payload, send, station, transitions

TOKEN = "synthetic-push-token-for-tests-only"
INSTALLATION = "00000000-0000-4000-8000-000000000001"


def registration(token=TOKEN, installation=INSTALLATION):
    return dict(provider="fcm", platform="android", provider_token=token, installation_id=installation)


def resident(client, email="resident@example.com"):
    return headers(client.post("/api/auth/register", json=account(email)))


def register(client, access, **kwargs):
    response = client.post("/api/notification-devices", headers=access, json=registration(**kwargs))
    assert response.status_code == 200, response.text
    return response.json()


def rows(model):
    with SessionLocal() as db:
        return db.scalars(select(model).order_by(model.id)).all()


def prepare(client, station):
    access = resident(client)
    device = register(client, access)
    send(client, station, 1, 100)
    return access, device


def make_due():
    with SessionLocal() as db:
        db.execute(update(NotificationDelivery).where(NotificationDelivery.state == "FAILED",
                   NotificationDelivery.next_attempt_at.is_not(None))
                   .values(next_attempt_at=utc_now() - timedelta(seconds=1)))
        db.commit()


class RejectingProvider:
    mode = "test"
    def __init__(self, outcome=SendOutcome.RETRYABLE_REJECTION):
        self.outcome = outcome
        self.calls = 0
    def send(self, target, message, *, delivery_key):
        self.calls += 1
        return self.outcome


def test_register_private_upsert_rotation_and_reinstall(client):
    access = resident(client)
    one = register(client, access)
    assert one["enabled"] and one["provider"] == "fcm"
    assert set(one) == {"id", "provider", "platform", "enabled", "created_at", "updated_at", "last_seen_at"}
    assert one["created_at"].endswith("Z")
    assert register(client, access)["id"] == one["id"]
    assert rows(NotificationDevice)[0].revision == 1
    assert register(client, access, token=TOKEN + "-rotated")["id"] == one["id"]
    assert rows(NotificationDevice)[0].revision == 2
    assert register(client, access, token=TOKEN + "-rotated", installation=str(uuid4()))["id"] == one["id"]
    assert len(rows(NotificationDevice)) == 1
    response = client.post("/api/notification-devices", headers=access, json=registration(token="bad token"))
    assert response.status_code == 422 and "bad token" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "provider_token" not in one and TOKEN not in str(one)
    assert TOKEN not in repr(PushTarget("fcm", TOKEN))


@pytest.mark.parametrize("role", ["admin", "officer"])
def test_staff_cannot_register_resident_push_devices(client, role):
    assert client.post("/api/notification-devices", headers=staff(client, role), json=registration()).status_code == 403


def test_authentication_ownership_and_no_token_enumeration(client):
    assert client.post("/api/notification-devices", json=registration()).status_code == 401
    owner = resident(client)
    device = register(client, owner)
    other = resident(client, "other@example.com")
    assert client.delete(f"/api/notification-devices/{device['id']}").status_code == 401
    assert client.delete(f"/api/notification-devices/{device['id']}", headers=other).status_code == 404
    conflict = client.post("/api/notification-devices", headers=other, json=registration())
    assert conflict.status_code == 409 and TOKEN not in conflict.text
    assert client.get("/api/notification-devices", headers=owner).status_code == 405
    assert client.get(f"/api/notification-devices/{device['id']}", headers=other).status_code == 405
    assert rows(NotificationDevice)[0].enabled
    assert client.delete(f"/api/notification-devices/{device['id']}", headers=owner).status_code == 204
    assert client.delete(f"/api/notification-devices/{device['id']}", headers=owner).status_code == 204
    disabled = rows(NotificationDevice)[0]
    assert not disabled.enabled and disabled.provider_token is None and disabled.token_hash is None
    assert register(client, other)["id"] != device["id"]


@pytest.mark.parametrize("old_sorts_first", [True, False])
def test_logged_out_owner_releases_token(client, monkeypatch, old_sorts_first):
    # UUID lexical order is unrelated to registration order. Exercise both.
    identifiers = ["00000000-0000-4000-8000-000000000001",
                   "ffffffff-ffff-4fff-8fff-ffffffffffff"]
    generated = iter(identifiers if old_sorts_first else reversed(identifiers))
    monkeypatch.setattr("app.models.uuid4", lambda: next(generated))
    owner = resident(client)
    old = register(client, owner)
    assert client.post("/api/auth/logout", headers=owner).status_code == 204
    new = register(client, resident(client, "other@example.com"))
    assert old["id"] != new["id"]
    with SessionLocal() as db:
        previous = db.get(NotificationDevice, old["id"])
        replacement = db.get(NotificationDevice, new["id"])
        assert not previous.enabled and previous.provider_token is None
        assert replacement.enabled and replacement.user_id != previous.user_id


@pytest.mark.parametrize("depth,severity", [(60, "ADVISORY"), (85, "WARNING"), (100, "EVACUATE")])
def test_direct_rise_creates_one_event_per_transition_one_delivery_per_device(client, station, depth, severity):
    owner = resident(client)
    register(client, owner)
    register(client, owner, token=TOKEN + "-second", installation=str(uuid4()))
    send(client, station, 1, depth)
    assert len(rows(NotificationEvent)) == 1 and len(rows(NotificationDelivery)) == 2
    assert transitions(station)[0].new_severity == severity
    assert client.post("/api/telemetry", json=payload(station, 1, depth)).status_code == 409
    with SessionLocal() as db:
        enqueue_transition(db, db.get(AlertTransition, transitions(station)[0].id))
        db.commit()
    assert len(rows(NotificationDelivery)) == 2


def test_invalid_same_tier_downgrade_and_recovery_never_enqueue(client, station):
    register(client, resident(client))
    for seq, depth in enumerate([None, 0, 60, 65, None, 85, 100, None, 90, 65, 0], 1):
        send(client, station, seq, depth)
    events = rows(NotificationEvent)
    assert len(events) == len(rows(NotificationDelivery)) == 3
    assert [t.new_severity for t in transitions(station) if t.id in {e.transition_id for e in events}] == ["ADVISORY", "WARNING", "EVACUATE"]
    assert episodes(station)[0].status == "RESOLVED"


def test_zero_recipients_keeps_intent_and_new_device_does_not_replay(client, station):
    send(client, station, 1, 100)
    assert len(rows(NotificationEvent)) == 1 and rows(NotificationDelivery) == []
    register(client, resident(client))
    assert process_pending(FakeNotificationProvider()) == 0


def test_intent_rolls_back_with_transition(client, station, monkeypatch):
    from app.services import alert_service
    register(client, resident(client))
    enqueue = alert_service.enqueue_transition
    def fail(db, transition):
        enqueue(db, transition)
        db.flush()
        raise RuntimeError("transaction test")
    monkeypatch.setattr(alert_service, "enqueue_transition", fail)
    with SessionLocal() as db, pytest.raises(RuntimeError):
        ingest_telemetry(db, TelemetryCreate(**payload(station, 1, 100)))
    assert not episodes(station) and not rows(NotificationEvent) and not rows(NotificationDelivery)


def test_database_uniqueness(client, station):
    prepare(client, station)
    original = rows(NotificationDelivery)[0]
    with SessionLocal() as db:
        db.add(NotificationDelivery(event_id=original.event_id, device_id=original.device_id,
                                   user_id=original.user_id, device_revision=original.device_revision))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(NotificationEvent(transition_id=rows(NotificationEvent)[0].transition_id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_fake_delivery_is_idempotent_safe_and_never_sent(client, station, caplog):
    prepare(client, station)
    provider = FakeNotificationProvider()
    with caplog.at_level("INFO"):
        assert process_pending(provider) == 1
    assert process_pending(provider) == 0 and len(provider.messages) == 1
    delivery = rows(NotificationDelivery)[0]
    assert delivery.state == "TESTED" and delivery.attempts == 1
    message = next(iter(provider.messages.values()))
    assert set(message.data) == {"type", "alert_id", "severity", "station_id", "status"}
    assert message.data["alert_id"] == str(episodes(station)[0].id)
    assert "EVACUATE-level sensor alert" in message.title
    assert "follow official local authority instructions" in message.body
    assert "official evacuation order" not in message.body.lower()
    assert TOKEN not in caplog.text and "state=TESTED" in caplog.text


def test_disabled_provider_suppresses_without_delivery(client, station):
    prepare(client, station)
    provider = configured_provider(Settings(notification_provider="disabled"))
    assert isinstance(provider, NoopNotificationProvider)
    assert process_pending(provider) == 1
    assert rows(NotificationDelivery)[0].state == "SUPPRESSED"
    assert rows(NotificationDelivery)[0].result_category == "disabled"
    with pytest.raises(ValueError, match="not implemented"):
        configured_provider(Settings(notification_provider="fcm"))


def test_retry_is_bounded_delayed_and_alert_is_already_committed(client, station):
    prepare(client, station)
    provider = RejectingProvider()
    for attempt in range(1, 4):
        assert process_pending(provider) == 1
        delivery = rows(NotificationDelivery)[0]
        assert delivery.attempts == attempt and delivery.state == "FAILED"
        assert episodes(station)[0].current_severity == "EVACUATE"
        assert process_pending(provider) == 0
        make_due()
    assert provider.calls == 3 and rows(NotificationDelivery)[0].next_attempt_at is None


def test_retry_success_then_never_sent_again(client, station):
    prepare(client, station)
    process_pending(RejectingProvider())
    make_due()
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 1
    assert rows(NotificationDelivery)[0].state == "TESTED"
    assert process_pending(provider) == 0


@pytest.mark.parametrize("outcome,state", [
    (SendOutcome.PERMANENT_REJECTION, "FAILED"), (SendOutcome.UNKNOWN, "UNKNOWN"),
    (SendOutcome.INVALID_TOKEN, "FAILED"), (SendOutcome.ACCEPTED, "TESTED")])
def test_terminal_results_and_invalid_token(client, station, outcome, state):
    prepare(client, station)
    provider = RejectingProvider(outcome)
    process_pending(provider)
    assert rows(NotificationDelivery)[0].state == state
    assert process_pending(provider) == 0
    assert rows(NotificationDevice)[0].enabled == (outcome != SendOutcome.INVALID_TOKEN)


def test_provider_exception_is_unknown_no_secret_log_no_rollback(client, station, caplog):
    prepare(client, station)
    class Broken:
        mode = "test"
        def send(self, *args, **kwargs):
            raise RuntimeError(TOKEN)
    process_pending(Broken())
    assert TOKEN not in caplog.text
    assert rows(NotificationDelivery)[0].state == "UNKNOWN"
    assert process_pending(Broken()) == 0 and episodes(station)[0].status == "ACTIVE"


@pytest.mark.parametrize("change", ["delete", "logout", "inactive", "rotate", "resolved", "downshift"])
def test_recheck_eligibility_and_superseded_intents(client, station, change):
    access, device = prepare(client, station)
    if change == "delete":
        client.delete(f"/api/notification-devices/{device['id']}", headers=access)
    elif change == "logout":
        client.post("/api/auth/logout", headers=access)
    elif change == "rotate":
        register(client, access, token=TOKEN + "-rotated")
    elif change in ("resolved", "downshift"):
        send(client, station, 2, 0 if change == "resolved" else 90)
    else:
        with SessionLocal() as db:
            db.execute(update(User).values(is_active=False))
            db.commit()
    provider = FakeNotificationProvider()
    process_pending(provider)
    assert not provider.messages and rows(NotificationDelivery)[0].state == "SUPPRESSED"


def test_concurrent_workers_claim_once_and_network_has_no_write_lock(client, station):
    prepare(client, station)
    start = Barrier(2)
    class Provider(FakeNotificationProvider):
        def send(self, *args, **kwargs):
            # Another write transaction works during provider invocation.
            with SessionLocal() as db:
                db.execute(update(NotificationDevice).values(last_seen_at=utc_now()))
                db.commit()
            return super().send(*args, **kwargs)
    provider = Provider()
    def work(_):
        start.wait(timeout=10)
        return process_pending(provider)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(work, range(2))) == 1
    assert len(provider.messages) == 1 and rows(NotificationDelivery)[0].attempts == 1


def test_crashed_claim_is_not_blindly_retried(client, station):
    prepare(client, station)
    with SessionLocal() as db:
        db.execute(update(NotificationDelivery).values(state="PROCESSING", attempts=1))
        db.commit()
    assert process_pending(FakeNotificationProvider()) == 0


def test_worker_bounded_batch(client, station):
    access = resident(client)
    for i in range(3):
        register(client, access, token=TOKEN + str(i), installation=str(uuid4()))
    send(client, station, 1, 100)
    assert process_pending(FakeNotificationProvider(), limit=1) == 1
    assert [d.state for d in rows(NotificationDelivery)].count("PENDING") == 2
    with pytest.raises(ValueError):
        process_pending(FakeNotificationProvider(), limit=101)


def test_invalid_old_token_result_cannot_disable_rotated_registration(client, station):
    access, device = prepare(client, station)
    class RotateDuringSend:
        mode = "test"
        def send(self, *args, **kwargs):
            register(client, access, token=TOKEN + "-rotated")
            return SendOutcome.INVALID_TOKEN
    process_pending(RotateDuringSend())
    current = rows(NotificationDevice)[0]
    assert current.enabled and current.revision == 2
    assert rows(NotificationDelivery)[0].state == "FAILED"
