"""Exercise delivery integration: Firebase EXERCISE_TEST gate (mocked SDK), the
development runner and consent reads. No real FCM, device or live database."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from unittest.mock import Mock

import firebase_admin
import pytest
from firebase_admin import credentials, messaging
from google.auth.credentials import AnonymousCredentials
from sqlalchemy import select, update

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.exercise_models import ExerciseDelivery, ExerciseSensorDelivery
from app.models import NotificationDevice
from app.services import exercise_notifications as service
from app.services.notification_provider import PushTarget, SendOutcome, configured_provider
from app.services.notification_service import message_for
from test_accounts import reset_accounts  # noqa: F401  (autouse account isolation)
from test_exercise_notifications import ROOT, device_for, enabled, opt_in, ready, send  # noqa: F401  (fixtures)
from test_exercise_sensor_triggers import arm, armed, water  # noqa: F401  (fixture)
from test_station_security import device  # noqa: F401  (fixture)


@pytest.fixture
def fcm(monkeypatch):
    """Real FirebaseNotificationProvider with anonymous credentials and a mocked SDK send."""
    monkeypatch.setattr(credentials.ApplicationDefault, "get_credential", lambda _: AnonymousCredentials())
    provider = configured_provider(Settings(_env_file=None, notification_provider="fcm",
                                            firebase_project_id="agapay-test-project"))
    sdk = Mock(return_value="projects/agapay-test-project/messages/exercise-accepted")
    monkeypatch.setattr(messaging, "send", sdk)
    yield provider, sdk
    firebase_admin.delete_app(provider._app)


def manual_delivery():
    with SessionLocal() as db:
        return db.scalars(select(ExerciseDelivery)).one()


def device_token(device_id):
    with SessionLocal() as db:
        return db.get(NotificationDevice, device_id).provider_token


# --- Firebase EXERCISE_TEST branch -----------------------------------------------------

def test_fcm_sends_a_claimed_manual_exercise_token_only(client, ready, fcm):
    provider, sdk = fcm
    admin, _, device_id, session_id = ready
    send(client, admin, session_id, device_id)
    assert service.process_pending(provider) == 1
    delivery = manual_delivery()
    assert (delivery.state, delivery.outcome, delivery.attempts) == ("SENT", "accepted", 1)
    assert sdk.call_count == 1
    sent = sdk.call_args.args[0]
    assert sent.token == device_token(device_id) and sent.topic is None and sent.condition is None
    assert sent.notification.title == "AGAPAY TEST ALERT — NOT A REAL EMERGENCY"
    assert sent.data == {"type": "EXERCISE_TEST", "exercise": "true", "session_id": session_id, "delivery_id": delivery.id}
    assert 0 < sent.android.ttl.total_seconds() <= 600


def test_fcm_sends_a_claimed_sensor_exercise(client, armed, fcm):
    provider, sdk = fcm
    water(client, armed, 5)
    arm(client, armed)
    water(client, armed, 105)
    assert service.scan_sensor_triggers() == 1
    assert service.process_sensor_pending(provider) == 1
    with SessionLocal() as db:
        delivery = db.scalars(select(ExerciseSensorDelivery)).one()
    assert (delivery.state, delivery.attempts) == ("SENT", 1)
    data = sdk.call_args.args[0].data
    assert data["trigger"] == "sensor" and data["type"] == "EXERCISE_TEST"
    assert "observed EVACUATE-level reading" in sdk.call_args.args[0].notification.body


def claimed(client, ready):
    """Claim a manual delivery the way the worker does, then return its exact message."""
    admin, _, device_id, session_id = ready
    send(client, admin, session_id, device_id)
    delivery = manual_delivery()
    with SessionLocal() as db:
        db.execute(update(ExerciseDelivery).values(state="PROCESSING", attempts=1))
        db.commit()
    return service.exercise_message(session_id, delivery.id), PushTarget("fcm", device_token(device_id)), delivery


@pytest.mark.parametrize("tamper", [
    "title", "body", "extra_key", "missing_key", "trigger_value", "bad_uuid", "non_string",
    "wrong_key", "other_token", "not_claimed", "second_attempt", "unknown_delivery",
])
def test_fcm_gate_rejects_anything_but_the_service_built_claimed_message(client, ready, fcm, tamper):
    provider, sdk = fcm
    message, target, delivery = claimed(client, ready)
    key = "exercise:" + delivery.id
    data = dict(message.data)
    if tamper == "title":
        message = replace(message, title="AGAPAY EVACUATE-level sensor alert")
    elif tamper == "body":
        message = replace(message, body="Evacuate now.")
    elif tamper == "extra_key":
        message = replace(message, data={**data, "topic": "all-residents"})
    elif tamper == "missing_key":
        data.pop("exercise")
        message = replace(message, data=data)
    elif tamper == "trigger_value":
        message = replace(message, data={**data, "trigger": "citywide"})
    elif tamper == "bad_uuid":
        message = replace(message, data={**data, "delivery_id": "42"})
    elif tamper == "non_string":
        message = replace(message, data={**data, "exercise": True})
    elif tamper == "wrong_key":
        key = "operational:" + delivery.id
    elif tamper == "other_token":
        target = PushTarget("fcm", "some-other-registration-token")
    elif tamper == "not_claimed":
        with SessionLocal() as db:
            db.execute(update(ExerciseDelivery).values(state="PENDING", attempts=0))
            db.commit()
    elif tamper == "second_attempt":
        with SessionLocal() as db:
            db.execute(update(ExerciseDelivery).values(attempts=1, state="TESTED"))
            db.commit()
    else:
        message = replace(message, data={**data, "delivery_id": "6f9a1d22-3c4b-4e5f-8a9b-0c1d2e3f4a5b"})
        key = "exercise:6f9a1d22-3c4b-4e5f-8a9b-0c1d2e3f4a5b"
    assert provider.send(target, message, delivery_key=key) == SendOutcome.PERMANENT_REJECTION
    assert sdk.call_count == 0


def test_fcm_gate_accepts_the_exact_claimed_message_once(client, ready, fcm):
    provider, sdk = fcm
    message, target, delivery = claimed(client, ready)
    key = "exercise:" + delivery.id
    assert provider.send(target, message, delivery_key=key) == SendOutcome.ACCEPTED
    assert provider.send(target, message, delivery_key=key) == SendOutcome.PERMANENT_REJECTION  # no replay
    assert sdk.call_count == 1


@pytest.mark.parametrize("change,outcome", [
    ("production", SendOutcome.DISABLED), ("disabled", SendOutcome.DISABLED),
    ("opt_out", SendOutcome.PERMANENT_REJECTION), ("revoke", SendOutcome.PERMANENT_REJECTION),
    ("terminate", SendOutcome.PERMANENT_REJECTION), ("expire", SendOutcome.PERMANENT_REJECTION),
    ("admin_demoted", SendOutcome.PERMANENT_REJECTION),
])
def test_fcm_gate_revalidates_eligibility_at_the_sdk_boundary(client, ready, fcm, monkeypatch, change, outcome):
    from datetime import timedelta
    from app.exercise_models import ExerciseSession
    from app.models import User, utc_now
    provider, sdk = fcm
    admin, access, device_id, session_id = ready
    message, target, delivery = claimed(client, ready)
    if change == "production":
        monkeypatch.setattr(get_settings(), "environment", "production")
    elif change == "disabled":
        monkeypatch.setattr(get_settings(), "exercise_notifications_enabled", False)
    elif change == "opt_out":
        client.delete(f"{ROOT}/consent/{device_id}", headers=access)
    elif change == "revoke":
        client.post(f"{ROOT}/sessions/{session_id}/recipients/revoke", headers=admin,
                    json={"device_id": device_id, "reason": "Removed"})
    elif change == "terminate":
        client.post(f"{ROOT}/sessions/{session_id}/terminate", headers=admin, json={"reason": "Stop"})
    elif change == "expire":
        with SessionLocal() as db:
            db.execute(update(ExerciseSession).values(expires_at=utc_now() - timedelta(seconds=1)))
            db.commit()
    else:
        with SessionLocal() as db:
            db.execute(update(User).where(User.email == "admin@example.com").values(role="officer"))
            db.commit()
    assert provider.send(target, message, delivery_key="exercise:" + delivery.id) == outcome
    assert sdk.call_count == 0


def test_operational_fcm_validation_is_unchanged(fcm):
    from types import SimpleNamespace
    provider, sdk = fcm
    operational = message_for(SimpleNamespace(new_severity="EVACUATE", alert_id=12, station_id="STATION_TEST"))
    assert provider.send(PushTarget("fcm", "t"), operational, delivery_key="one") == SendOutcome.ACCEPTED
    assert sdk.call_args.args[0].data["type"] == "SENSOR_ESCALATION"
    # An operational payload cannot smuggle exercise keys, and unknown types stay rejected.
    for data in ({**operational.data, "exercise": "true"}, {**operational.data, "type": "EXERCISE"},
                 {**operational.data, "type": "TOPIC_BROADCAST"}):
        assert provider.send(PushTarget("fcm", "t"), replace(operational, data=data), delivery_key="two") \
            == SendOutcome.PERMANENT_REJECTION
    assert sdk.call_count == 1


def test_ambiguous_fcm_outcome_is_unknown_and_never_resent(client, ready, fcm, monkeypatch):
    provider, _ = fcm
    admin, _, device_id, session_id = ready
    send(client, admin, session_id, device_id)
    monkeypatch.setattr(messaging, "send", Mock(side_effect=TimeoutError("synthetic timeout")))
    assert service.process_pending(provider) == 1
    assert manual_delivery().state == "UNKNOWN"
    retry = Mock(return_value="projects/x/messages/y")
    monkeypatch.setattr(messaging, "send", retry)
    assert service.process_pending(provider) == 0 and retry.call_count == 0


# --- Development runner ----------------------------------------------------------------

def test_runner_is_not_part_of_the_production_worker():
    import inspect
    from app import worker_service
    assert "exercise" not in inspect.getsource(worker_service)


@pytest.mark.parametrize("mode", ["dry-run", "fake", "fcm"])
def test_runner_refuses_when_disabled_or_in_production(monkeypatch, mode):
    from app.exercise_runner import RunnerRefused, run
    with pytest.raises(RunnerRefused, match="disabled"):
        run(mode, once=True)
    monkeypatch.setattr(get_settings(), "exercise_notifications_enabled", True)
    monkeypatch.setattr(get_settings(), "environment", "production")
    with pytest.raises(RunnerRefused, match="production"):
        run(mode, once=True)


def test_runner_real_mode_needs_its_own_opt_in_and_fcm(monkeypatch):
    from app.exercise_runner import RunnerRefused, run
    monkeypatch.setattr(get_settings(), "exercise_notifications_enabled", True)
    with pytest.raises(RunnerRefused, match="real exercise delivery"):
        run("fcm", once=True)
    monkeypatch.setattr(get_settings(), "exercise_real_delivery_enabled", True)
    with pytest.raises(RunnerRefused, match="FCM"):
        run("fcm", once=True)
    with pytest.raises(ValueError, match="prohibited in production"):
        Settings(_env_file=None, environment="production", exercise_real_delivery_enabled=True)


def test_runner_dry_run_writes_nothing(client, ready):
    from app.exercise_runner import run
    admin, _, device_id, session_id = ready
    send(client, admin, session_id, device_id)
    summary, = run("dry-run")
    assert summary == {"armed_stations": 0, "pending_manual": 1, "pending_sensor": 0}
    assert manual_delivery().state == "PENDING"


def test_runner_fake_tick_scans_and_delivers_both_kinds(client, armed):
    from app.exercise_runner import run
    water(client, armed, 5)
    arm(client, armed)
    water(client, armed, 105)
    client.post(f"{ROOT}/sessions/{armed['session']}/send", headers=armed["admin"], json={
        "device_id": armed["device_id"], "idempotency_key": "manual-runner-check", "reason": "Manual check"})
    outcome, = run("fake", once=True)
    assert outcome == {"triggers": 1, "manual": 1, "sensor": 1}
    with SessionLocal() as db:
        assert db.scalars(select(ExerciseSensorDelivery.state)).all() == ["TESTED"]
        assert db.scalars(select(ExerciseDelivery.state)).all() == ["TESTED"]


def test_two_concurrent_runners_never_duplicate_triggers_or_attempts(client, armed):
    from app.exercise_runner import run
    from app.services.notification_provider import FakeNotificationProvider
    water(client, armed, 5)
    arm(client, armed)
    water(client, armed, 70)
    water(client, armed, 105)
    provider, barrier = FakeNotificationProvider(), Barrier(2)

    def runner(_):
        barrier.wait()
        return run("fake", once=True, provider=provider)[0]
    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(runner, range(2)))
    assert sum(o["triggers"] for o in outcomes) == 2
    assert sum(o["sensor"] for o in outcomes) == 2
    with SessionLocal() as db:
        rows = db.scalars(select(ExerciseSensorDelivery)).all()
    assert len(rows) == 2 and all(r.attempts == 1 and r.state == "TESTED" for r in rows)
    assert len(provider.messages) == 2


def test_runner_stops_when_the_feature_is_switched_off(client, ready, monkeypatch):
    from threading import Event
    from app.exercise_runner import run
    stop = Event()
    calls = []

    def switch_off(*args, **kwargs):
        calls.append(1)
        monkeypatch.setattr(get_settings(), "exercise_notifications_enabled", False)
        return {"triggers": 0, "manual": 0, "sensor": 0}
    monkeypatch.setattr("app.exercise_runner.tick", switch_off)
    results = run("fake", interval=0, stop=stop)
    assert len(results) == 1 and len(calls) == 1  # second tick refused by the per-tick preflight


def test_importing_the_runner_has_no_side_effects(monkeypatch):
    import importlib
    import sys
    sdk = Mock()
    monkeypatch.setattr(messaging, "send", sdk)
    sys.modules.pop("app.exercise_runner", None)
    importlib.import_module("app.exercise_runner")
    assert sdk.call_count == 0


# --- Consent reads ------------------------------------------------------------------------

def test_consent_is_owner_only_off_by_default_and_revision_bound(client, ready):
    _, access, device_id, _ = ready
    assert client.get(f"{ROOT}/consent/{device_id}", headers=access).json()["opted_in"] is True
    other, other_id = device_for(client, "other@example.com", 2)
    assert client.get(f"{ROOT}/consent/{other_id}", headers=other).json()["opted_in"] is False  # default off
    assert client.get(f"{ROOT}/consent/{device_id}", headers=other).status_code == 404
    with SessionLocal() as db:
        db.execute(update(NotificationDevice).where(NotificationDevice.id == device_id)
                   .values(revision=NotificationDevice.revision + 1))
        db.commit()
    assert client.get(f"{ROOT}/consent/{device_id}", headers=access).json()["opted_in"] is False
