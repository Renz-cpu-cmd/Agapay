"""Isolated EXERCISE_TEST notifications (Stage A). Disposable SQLite, fake providers only.
No external FCM send, device, ESP32 or live database is contacted."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.exercise_models import ExerciseConsent, ExerciseDelivery, ExerciseSession
from app.governance_models import GovernanceAudit
from app.models import (Alert, AlertTransition, NotificationDelivery, NotificationDevice, NotificationEvent,
                        SosRequest, User, utc_now)
from app.services.exercise_notifications import EXERCISE_TITLE, process_pending
from app.services.notification_provider import FakeNotificationProvider, NoopNotificationProvider, SendOutcome
from test_accounts import reset_accounts, staff  # noqa: F401  (autouse account isolation)
from test_notifications import register, registration, resident

ROOT = '/api/exercise-notifications'


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(get_settings(), 'exercise_notifications_enabled', True)


def device_for(client, email, n):
    access = resident(client, email)
    response = client.post('/api/notification-devices', headers=access, json=registration(
        token=f'synthetic-exercise-token-{n}', installation=f'00000000-0000-4000-8000-00000000000{n}'))
    assert response.status_code == 200, response.text
    return access, response.json()['id']


def opt_in(client, access, device_id):
    response = client.put(f'{ROOT}/consent/{device_id}', headers=access)
    assert response.status_code == 200, response.text


def new_session(client, admin, **changes):
    response = client.post(f'{ROOT}/sessions', headers=admin, json={
        'reason': 'Synthetic exercise session for regression tests', 'duration_minutes': 30, **changes})
    assert response.status_code == 201, response.text
    return response.json()['id']


def allowlist(client, admin, session_id, device_id):
    return client.post(f'{ROOT}/sessions/{session_id}/recipients', headers=admin,
                       json={'device_id': device_id, 'reason': 'Designated test phone'})


def send(client, admin, session_id, device_id, key='exercise-key-0001', dry_run=False):
    return client.post(f'{ROOT}/sessions/{session_id}/send', headers=admin, json={
        'device_id': device_id, 'idempotency_key': key, 'reason': 'Manual exercise check', 'dry_run': dry_run})


@pytest.fixture
def ready(client, enabled):
    """Admin, one opted-in and allowlisted test device, and an active session."""
    admin = staff(client)
    access, device_id = device_for(client, 'tester@example.com', 1)
    opt_in(client, access, device_id)
    session_id = new_session(client, admin)
    assert allowlist(client, admin, session_id, device_id).status_code == 200
    return admin, access, device_id, session_id


def deliveries():
    with SessionLocal() as db:
        return db.scalars(select(ExerciseDelivery).order_by(ExerciseDelivery.created_at)).all()


def operational_counts():
    with SessionLocal() as db:
        return {m.__name__: db.scalar(select(func.count()).select_from(m))
                for m in (Alert, AlertTransition, NotificationEvent, NotificationDelivery, SosRequest)}


# --- Availability and authorization ------------------------------------------------------

def test_disabled_by_default_everywhere(client):
    assert Settings(_env_file=None).exercise_notifications_enabled is False
    admin = staff(client)
    access, device_id = device_for(client, 'tester@example.com', 1)
    assert client.post(f'{ROOT}/sessions', headers=admin, json={
        'reason': 'Synthetic exercise session', 'duration_minutes': 10}).status_code == 403
    assert client.put(f'{ROOT}/consent/{device_id}', headers=access).status_code == 403


def test_production_rejected_by_settings_and_at_runtime(client, enabled, monkeypatch):
    with pytest.raises(ValueError, match='prohibited in production'):
        Settings(_env_file=None, environment='production', exercise_notifications_enabled=True)
    monkeypatch.setattr(get_settings(), 'environment', 'production')
    response = client.post(f'{ROOT}/sessions', headers=staff(client), json={
        'reason': 'Synthetic exercise session', 'duration_minutes': 10})
    assert response.status_code == 403 and 'production' in response.json()['detail']


@pytest.mark.parametrize('role', ['anonymous', 'resident', 'officer'])
def test_only_administrators_manage_exercises(client, enabled, role):
    access = {} if role == 'anonymous' else resident(client) if role == 'resident' else staff(client, role)
    assert client.post(f'{ROOT}/sessions', headers=access, json={
        'reason': 'Synthetic exercise session', 'duration_minutes': 10}).status_code == (401 if role == 'anonymous' else 403)


def test_session_duration_is_bounded(client, enabled):
    admin = staff(client)
    assert client.post(f'{ROOT}/sessions', headers=admin, json={
        'reason': 'Synthetic exercise session', 'duration_minutes': 61}).status_code == 422


# --- Recipient allowlist -------------------------------------------------------------------

def test_allowlisting_requires_owner_opt_in_and_owner_only_consent(client, enabled):
    admin = staff(client)
    access, device_id = device_for(client, 'tester@example.com', 1)
    other, _ = device_for(client, 'other@example.com', 2)
    session_id = new_session(client, admin)
    assert allowlist(client, admin, session_id, device_id).status_code == 409  # not opted in
    assert client.put(f'{ROOT}/consent/{device_id}', headers=other).status_code == 404  # not the owner
    opt_in(client, access, device_id)
    assert allowlist(client, admin, session_id, device_id).status_code == 200


def test_subscriptions_never_expand_the_audience(client, enabled):
    admin = staff(client)
    access, device_id = device_for(client, 'tester@example.com', 1)
    opt_in(client, access, device_id)
    subscribed = resident(client, 'subscribed@example.com')
    other_id = register(client, subscribed, token='synthetic-subscribed-token',
                        installation='00000000-0000-4000-8000-000000000009')['id']
    client.put(f'{ROOT}/consent/{other_id}', headers=subscribed)  # opted in, but NOT allowlisted
    session_id = new_session(client, admin)
    assert allowlist(client, admin, session_id, device_id).status_code == 200
    assert send(client, admin, session_id, other_id).status_code == 409
    assert send(client, admin, session_id, device_id).status_code == 200
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 1
    assert len(provider.messages) == 1 and [d.device_id for d in deliveries()] == [device_id]


# --- Stage A delivery ------------------------------------------------------------------------

def test_dry_run_validates_without_recording_a_delivery(client, ready):
    admin, _, device_id, session_id = ready
    response = send(client, admin, session_id, device_id, dry_run=True)
    assert response.status_code == 200 and response.json()['eligible'] is True
    assert response.json()['title'] == EXERCISE_TITLE and response.json()['message_type'] == 'EXERCISE_TEST'
    assert deliveries() == []


def test_fake_provider_delivery_is_labelled_exercise_only(client, ready):
    admin, _, device_id, session_id = ready
    before = operational_counts()
    response = send(client, admin, session_id, device_id)
    assert response.status_code == 200 and response.json()['delivery']['state'] == 'PENDING'
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 1
    (key, message), = provider.messages.items()
    delivery, = deliveries()
    assert key == 'exercise:' + delivery.id and delivery.state == 'TESTED'
    assert message.title == 'AGAPAY TEST ALERT — NOT A REAL EMERGENCY'
    assert message.data == {'type': 'EXERCISE_TEST', 'exercise': 'true', 'session_id': session_id,
                            'delivery_id': delivery.id}
    assert 'EXERCISE ONLY' in message.body and 'not a flood warning' in message.body
    for operational in ('ADVISORY', 'WARNING', 'EVACUATE', 'SENSOR_ESCALATION', 'LGU', 'official order'):
        assert operational not in message.title and message.data['type'] != operational
    # Separation: no operational episode, outbox, advisory or SOS record was created.
    assert operational_counts() == before
    with SessionLocal() as db:
        actions = set(db.scalars(select(GovernanceAudit.action)))
    assert {'exercise_session_created', 'exercise_device_allowlisted', 'exercise_send_requested'} <= actions
    evidence = client.get(f'{ROOT}/sessions/{session_id}', headers=admin).json()
    assert evidence['deliveries'][0]['state'] == 'TESTED' and evidence['message_type'] == 'EXERCISE_TEST'


def test_database_refuses_non_exercise_message_types(client, ready):
    admin, _, device_id, session_id = ready
    assert send(client, admin, session_id, device_id).status_code == 200
    with SessionLocal() as db, pytest.raises(IntegrityError):
        db.execute(update(ExerciseDelivery).values(message_type='EVACUATE'))
        db.commit()


# --- Replay, idempotency and rate limits ------------------------------------------------

def test_idempotent_request_and_single_attempt_without_replay(client, ready):
    admin, _, device_id, session_id = ready
    first = send(client, admin, session_id, device_id).json()
    again = send(client, admin, session_id, device_id).json()
    assert again['replayed'] is True and again['delivery']['id'] == first['delivery']['id']
    assert len(deliveries()) == 1
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 1 and process_pending(provider) == 0
    assert len(provider.messages) == 1 and deliveries()[0].attempts == 1


def test_idempotency_key_cannot_be_reused_for_another_device(client, ready):
    admin, _, device_id, session_id = ready
    access, other_id = device_for(client, 'second@example.com', 2)
    opt_in(client, access, other_id)
    assert allowlist(client, admin, session_id, other_id).status_code == 200
    assert send(client, admin, session_id, device_id).status_code == 200
    assert send(client, admin, session_id, other_id).status_code == 409


def test_ambiguous_provider_outcome_is_never_resent(client, ready):
    admin, _, device_id, session_id = ready
    send(client, admin, session_id, device_id)

    class Exploding(FakeNotificationProvider):
        def send(self, target, message, *, delivery_key):
            raise TimeoutError('synthetic timeout after possible acceptance')
    assert process_pending(Exploding()) == 1
    assert deliveries()[0].state == 'UNKNOWN'
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 0 and provider.messages == {}


def test_rate_limits_per_device_and_per_session(client, ready, monkeypatch):
    admin, _, device_id, session_id = ready
    assert send(client, admin, session_id, device_id, key='exercise-key-a').status_code == 200
    assert send(client, admin, session_id, device_id, key='exercise-key-b').status_code == 429
    monkeypatch.setattr(get_settings(), 'exercise_min_send_interval_seconds', 5)
    with SessionLocal() as db:
        db.execute(update(ExerciseDelivery).values(created_at=utc_now() - timedelta(seconds=10)))
        db.execute(update(ExerciseSession).values(max_sends=2))
        db.commit()
    assert send(client, admin, session_id, device_id, key='exercise-key-c').status_code == 200
    with SessionLocal() as db:
        db.execute(update(ExerciseDelivery).values(created_at=utc_now() - timedelta(seconds=10)))
        db.commit()
    assert send(client, admin, session_id, device_id, key='exercise-key-d').status_code == 429  # session cap


# --- Expiry, revocation and worker-time revalidation -----------------------------------

def expire(session_id):
    with SessionLocal() as db:
        db.execute(update(ExerciseSession).where(ExerciseSession.id == session_id)
                   .values(expires_at=utc_now() - timedelta(seconds=1)))
        db.commit()


def test_request_time_refusals(client, ready):
    admin, access, device_id, session_id = ready
    client.delete(f'{ROOT}/consent/{device_id}', headers=access)
    assert send(client, admin, session_id, device_id).status_code == 409
    opt_in(client, access, device_id)
    client.post(f'{ROOT}/sessions/{session_id}/recipients/revoke', headers=admin,
                json={'device_id': device_id, 'reason': 'Removed from drill'})
    assert send(client, admin, session_id, device_id).status_code == 409
    assert allowlist(client, admin, session_id, device_id).status_code == 200
    expire(session_id)
    assert send(client, admin, session_id, device_id).status_code == 409
    other = new_session(client, admin)
    assert allowlist(client, admin, other, device_id).status_code == 200
    client.post(f'{ROOT}/sessions/{other}/terminate', headers=admin, json={'reason': 'Drill finished'})
    assert send(client, admin, other, device_id).status_code == 409
    assert deliveries() == []


@pytest.mark.parametrize('change,reason', [
    ('terminate', 'session_terminated'), ('expire', 'session_expired'), ('revoke_device', 'device_not_allowlisted'),
    ('opt_out', 'device_owner_not_opted_in'), ('disable_feature', 'exercise_notifications_disabled'),
    ('production', 'prohibited_in_production'), ('reregister', 'device_registration_changed'),
    ('device_disabled', 'device_not_enabled'), ('admin_demoted', 'session_creator_not_authorized'),
])
def test_worker_revalidates_everything_before_sending(client, ready, monkeypatch, change, reason):
    admin, access, device_id, session_id = ready
    assert send(client, admin, session_id, device_id).status_code == 200
    if change == 'terminate':
        client.post(f'{ROOT}/sessions/{session_id}/terminate', headers=admin, json={'reason': 'Stop drill'})
    elif change == 'expire':
        expire(session_id)
    elif change == 'revoke_device':
        client.post(f'{ROOT}/sessions/{session_id}/recipients/revoke', headers=admin,
                    json={'device_id': device_id, 'reason': 'Removed from drill'})
    elif change == 'opt_out':
        client.delete(f'{ROOT}/consent/{device_id}', headers=access)
    elif change == 'disable_feature':
        monkeypatch.setattr(get_settings(), 'exercise_notifications_enabled', False)
    elif change == 'production':
        monkeypatch.setattr(get_settings(), 'environment', 'production')
    elif change == 'reregister':
        with SessionLocal() as db:
            db.execute(update(NotificationDevice).where(NotificationDevice.id == device_id)
                       .values(revision=NotificationDevice.revision + 1))
            db.commit()
    elif change == 'device_disabled':
        assert client.delete(f'/api/notification-devices/{device_id}', headers=access).status_code in (200, 204)
    else:
        with SessionLocal() as db:
            db.execute(update(User).where(User.email == 'admin@example.com').values(role='officer'))
            db.commit()
    provider = FakeNotificationProvider()
    if change == 'production':
        # R2 P0: production send-capable workers fail closed without the external restore
        # witness, before any claim. Nothing is attempted; the row is left unclaimed.
        from app.services.delivery_recovery import DeliveryFenced
        with pytest.raises(DeliveryFenced, match='AGAPAY_DELIVERY_LEDGER_PATH'):
            process_pending(provider)
        delivery, = deliveries()
        assert delivery.state == 'PENDING' and delivery.attempts == 0 and provider.messages == {}
        return
    assert process_pending(provider) == 1
    delivery, = deliveries()
    assert delivery.state == 'SUPPRESSED' and delivery.outcome == reason and provider.messages == {}


def test_disabled_provider_suppresses_without_sending(client, ready):
    admin, _, device_id, session_id = ready
    send(client, admin, session_id, device_id)
    assert process_pending(NoopNotificationProvider()) == 1
    delivery, = deliveries()
    assert (delivery.state, delivery.outcome) == ('SUPPRESSED', 'provider_disabled')


def test_test_environment_never_configures_a_real_provider():
    assert get_settings().notification_provider == 'disabled'
    assert SendOutcome.TEST_ONLY.value == 'test_only'


def test_privacy_erasure_list_includes_exercise_consent():
    import inspect
    from app.services import privacy
    assert 'ExerciseConsent' in inspect.getsource(privacy)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ExerciseConsent)) == 0
