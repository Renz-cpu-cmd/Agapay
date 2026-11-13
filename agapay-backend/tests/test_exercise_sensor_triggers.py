"""Stage B: sensor-triggered EXERCISE_TEST notifications (migration 0007).

Telemetry enters through the real authenticated ingestion path on a disposable SQLite
database. The watcher only reads operational telemetry. Fake providers only; no FCM,
device, ESP32 or live database is contacted."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, inspect, select, text, update
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import SessionLocal
from app.exercise_models import (ExerciseSensorDelivery, ExerciseSensorTrigger, ExerciseSession,
                                 ExerciseStationArm)
from app.models import (Alert, AlertTransition, NotificationDelivery, NotificationEvent, SosRequest, Telemetry,
                        TelemetryProvenance, utc_now)
from app.services.exercise_notifications import (EXERCISE_TITLE, process_pending, process_sensor_pending,
                                                 scan_sensor_triggers)
from app.services.notification_provider import FakeNotificationProvider
from test_accounts import reset_accounts  # noqa: F401  (autouse account isolation)
from test_alerts import payload as legacy_payload
from test_exercise_notifications import ROOT, device_for, opt_in
from test_station_security import device, token_headers  # noqa: F401  (pytest fixture)


@pytest.fixture
def armed(client, device, monkeypatch):
    """Enabled feature, opted-in allowlisted tester, active session, NO baseline reading."""
    monkeypatch.setattr(get_settings(), 'exercise_notifications_enabled', True)
    monkeypatch.setattr(get_settings(), 'exercise_min_send_interval_seconds', 0)
    station, admin, issued = device
    access, device_id = device_for(client, 'tester@example.com', 1)
    opt_in(client, access, device_id)
    session_id = client.post(f'{ROOT}/sessions', headers=admin, json={
        'reason': 'Synthetic sensor exercise session', 'duration_minutes': 30, 'max_sends': 10}).json()['id']
    assert client.post(f'{ROOT}/sessions/{session_id}/recipients', headers=admin,
                       json={'device_id': device_id, 'reason': 'Designated test phone'}).status_code == 200
    return dict(station=station, admin=admin, issued=issued, access=access, device_id=device_id, session=session_id)


def arm(client, ctx):
    response = client.post(f"{ROOT}/sessions/{ctx['session']}/stations", headers=ctx['admin'],
                           json={'station_id': ctx['station'], 'reason': 'Cardboard target demonstration'})
    assert response.status_code == 200, response.text
    return response.json()


_sequence = {}


def water(client, ctx, depth, *, measured=None, sequence=None):
    seq = sequence or _sequence.setdefault(ctx['station'], 0) + 1
    _sequence[ctx['station']] = max(seq, _sequence.get(ctx['station'], 0))
    body = {**legacy_payload(ctx['station'], seq, depth),
            'measured_at': (measured or utc_now()).isoformat(), 'device_uptime_ms': seq * 1000}
    response = client.post('/api/telemetry', headers=token_headers(ctx['issued']), json=body)
    assert response.status_code in (201, 409), response.text
    return response


@pytest.fixture(autouse=True)
def reset_sequence():
    _sequence.clear()


def triggers():
    with SessionLocal() as db:
        return db.scalars(select(ExerciseSensorTrigger).order_by(ExerciseSensorTrigger.processed_at)).all()


def sensor_deliveries():
    with SessionLocal() as db:
        return db.scalars(select(ExerciseSensorDelivery).order_by(ExerciseSensorDelivery.created_at)).all()


def operational_counts():
    with SessionLocal() as db:
        return {m.__name__: db.scalar(select(func.count()).select_from(m))
                for m in (Telemetry, Alert, AlertTransition, NotificationEvent, NotificationDelivery, SosRequest)}


# --- Trigger rules ---------------------------------------------------------------------------

def test_upward_progression_triggers_each_tier_once(client, armed):
    arm(client, armed)
    water(client, armed, 10)  # unknown baseline at arming: first valid sample only sets it
    for depth in (65, 66, 90, 91, 105, 106):
        water(client, armed, depth)
    assert scan_sensor_triggers() == 3
    rows = triggers()
    assert [(t.previous_tier, t.current_tier) for t in rows] == [
        ('NORMAL', 'ADVISORY'), ('ADVISORY', 'WARNING'), ('WARNING', 'EVACUATE')]
    trigger = rows[-1]
    with SessionLocal() as db:
        telemetry = db.get(Telemetry, trigger.telemetry_id)
        provenance = db.get(TelemetryProvenance, trigger.telemetry_id)
    assert telemetry.water_depth_cm == trigger.water_depth_cm == 105
    assert (trigger.source_class, trigger.ingress_identity, trigger.registry_version, trigger.credential_id) == (
        'physical_device', provenance.ingress_identity, provenance.registry_version, provenance.credential_id)
    assert trigger.reason == 'observed_tier_increase' and trigger.status == 'DELIVERIES_CREATED'
    assert len(sensor_deliveries()) == 3 and {d.state for d in sensor_deliveries()} == {'PENDING'}
    assert scan_sensor_triggers() == 0  # cursor advanced; nothing reprocessed


def test_direct_normal_to_evacuate_is_one_trigger(client, armed):
    water(client, armed, 5)
    arm(client, armed)  # fresh NORMAL baseline captured at arming
    water(client, armed, 120)
    assert scan_sensor_triggers() == 1
    assert [(t.previous_tier, t.current_tier) for t in triggers()] == [('NORMAL', 'EVACUATE')]


def test_already_elevated_baseline_is_not_an_escalation(client, armed):
    water(client, armed, 110)
    state = arm(client, armed)
    assert state['armed_stations'][0]['baseline_tier'] == 'EVACUATE'
    for _ in range(3):
        water(client, armed, 112)
    assert scan_sensor_triggers() == 0 and triggers() == []
    water(client, armed, 5)
    water(client, armed, 70)  # a genuine later increase does count
    assert scan_sensor_triggers() == 1 and triggers()[0].current_tier == 'ADVISORY'


def test_repeated_tier_and_duplicate_telemetry_do_not_retrigger(client, armed):
    water(client, armed, 5)
    arm(client, armed)
    water(client, armed, 90, sequence=10)
    assert water(client, armed, 90, sequence=10).status_code == 409  # exact duplicate is rejected at ingress
    water(client, armed, 92, sequence=11)
    water(client, armed, 60, sequence=12)
    water(client, armed, 91, sequence=13)  # back up to WARNING: already triggered this session
    assert scan_sensor_triggers() == 1
    assert [t.current_tier for t in triggers()] == ['WARNING']


def test_out_of_order_and_replayed_samples_are_ignored(client, armed):
    from app.schemas import TelemetryCreate
    from app.models import StationCredential
    from app.services.telemetry_service import ingest_telemetry
    water(client, armed, 5, sequence=5)
    arm(client, armed)
    water(client, armed, 105, sequence=3)  # lower sequence after a newer one: out_of_order
    with SessionLocal() as db:
        credential = db.scalar(select(StationCredential).where(StationCredential.station_id == armed['station']))
        replay = TelemetryCreate(**{**legacy_payload(armed['station'], 9, 105), 'measured_at': utc_now().isoformat(),
                                    'device_uptime_ms': 9000})
        row = ingest_telemetry(db, replay, credential_id=credential.id, transport='http', historical=True)
        assert row.disposition == 'journal_backfill'
    with SessionLocal() as db:
        dispositions = set(db.scalars(select(Telemetry.disposition).where(Telemetry.station_id == armed['station'])))
    assert {'out_of_order', 'journal_backfill'} <= dispositions
    assert scan_sensor_triggers() == 0 and triggers() == []


@pytest.mark.parametrize('flaw', ['invalid', 'stale', 'untrusted', 'pre_arming'])
def test_invalid_stale_untrusted_and_pre_arming_samples_are_ignored(client, armed, flaw):
    water(client, armed, 5)
    arm(client, armed)
    if flaw == 'invalid':
        water(client, armed, None)
    elif flaw == 'pre_arming':
        water(client, armed, 105, measured=utc_now() - timedelta(seconds=30))
    else:
        response = water(client, armed, 105)
        telemetry_id = response.json()['id']
        with SessionLocal() as db:
            if flaw == 'stale':  # committed fresh, but the watcher runs too late
                db.execute(update(Telemetry).where(Telemetry.id == telemetry_id)
                           .values(measured_at=utc_now() - timedelta(minutes=5)))
            else:
                db.delete(db.get(TelemetryProvenance, telemetry_id))
            db.commit()
    assert scan_sensor_triggers() == 0 and triggers() == []


def test_unarmed_and_unrelated_stations_are_never_evaluated(client, armed):
    water(client, armed, 5)
    water(client, armed, 105)  # before arming: never evaluated
    assert scan_sensor_triggers() == 0 and triggers() == []


def test_concurrent_watchers_record_each_trigger_once(client, armed):
    water(client, armed, 5)
    arm(client, armed)
    water(client, armed, 70)
    water(client, armed, 105)
    barrier = Barrier(4)

    def run(_):
        barrier.wait()
        return scan_sensor_triggers()
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(run, range(4)))
    assert sum(results) == 2
    assert [t.current_tier for t in triggers()] == ['ADVISORY', 'EVACUATE']
    assert len(sensor_deliveries()) == 2


def test_database_enforces_upward_unique_and_exercise_only(client, armed):
    water(client, armed, 5)
    arm(client, armed)
    water(client, armed, 105)
    scan_sensor_triggers()
    trigger, = triggers()
    for change in ({'previous_tier': 'EVACUATE'}, {'current_tier': 'NORMAL'}, {'source_class': 'simulator'}):
        with SessionLocal() as db, pytest.raises(IntegrityError):
            db.execute(update(ExerciseSensorTrigger).values(**change))
            db.commit()
    with SessionLocal() as db, pytest.raises(IntegrityError):
        db.execute(update(ExerciseSensorDelivery).values(message_type='EVACUATE'))
        db.commit()
    with SessionLocal() as db, pytest.raises(IntegrityError):
        db.execute(update(ExerciseSensorDelivery).values(attempts=2))
        db.commit()


# --- Delivery safeguards (shared with Stage A) ----------------------------------------

def progress_to_evacuate(client, armed):
    water(client, armed, 5)
    arm(client, armed)
    water(client, armed, 105)
    assert scan_sensor_triggers() == 1


def test_fake_provider_sends_labelled_exercise_with_test_context_only(client, armed):
    progress_to_evacuate(client, armed)
    before = operational_counts()
    provider = FakeNotificationProvider()
    assert process_sensor_pending(provider) == 1
    (key, message), = provider.messages.items()
    delivery, = sensor_deliveries()
    assert key == 'exercise:' + delivery.id and delivery.state == 'TESTED' and delivery.attempts == 1
    assert message.title == EXERCISE_TITLE == 'AGAPAY TEST ALERT — NOT A REAL EMERGENCY'
    assert message.data == {'type': 'EXERCISE_TEST', 'exercise': 'true', 'trigger': 'sensor',
                            'session_id': armed['session'], 'delivery_id': delivery.id}
    assert 'observed EVACUATE-level reading' in message.body and 'not a flood warning' in message.body
    assert 'Prepare to evacuate' not in message.body and 'SENSOR_ESCALATION' not in str(message.data)
    assert operational_counts() == before  # watcher + worker never touch operational records
    # Manual Stage A queue is separate.
    assert process_pending(FakeNotificationProvider()) == 0


@pytest.mark.parametrize('change,reason', [
    ('terminate', 'session_terminated'), ('expire', 'session_expired'), ('opt_out', 'device_owner_not_opted_in'),
    ('revoke', 'device_not_allowlisted'), ('disarm', 'station_disarmed'),
    ('disable', 'exercise_notifications_disabled'), ('production', 'prohibited_in_production'),
])
def test_worker_revalidates_before_sending(client, armed, monkeypatch, change, reason):
    progress_to_evacuate(client, armed)
    session, admin = armed['session'], armed['admin']
    if change == 'terminate':
        client.post(f'{ROOT}/sessions/{session}/terminate', headers=admin, json={'reason': 'Stop'})
    elif change == 'expire':
        with SessionLocal() as db:
            db.execute(update(ExerciseSession).values(expires_at=utc_now() - timedelta(seconds=1)))
            db.commit()
    elif change == 'opt_out':
        client.delete(f"{ROOT}/consent/{armed['device_id']}", headers=armed['access'])
    elif change == 'revoke':
        client.post(f'{ROOT}/sessions/{session}/recipients/revoke', headers=admin,
                    json={'device_id': armed['device_id'], 'reason': 'Removed'})
    elif change == 'disarm':
        client.post(f'{ROOT}/sessions/{session}/stations/disarm', headers=admin,
                    json={'station_id': armed['station'], 'reason': 'Demo over'})
    elif change == 'disable':
        monkeypatch.setattr(get_settings(), 'exercise_notifications_enabled', False)
    else:
        monkeypatch.setattr(get_settings(), 'environment', 'production')
    provider = FakeNotificationProvider()
    if change == 'production':
        # R2 P0: production send-capable workers fail closed without the external restore
        # witness, before any claim. Nothing is attempted; the row is left unclaimed.
        from app.services.delivery_recovery import DeliveryFenced
        with pytest.raises(DeliveryFenced, match='AGAPAY_DELIVERY_LEDGER_PATH'):
            process_sensor_pending(provider)
        delivery, = sensor_deliveries()
        assert delivery.state == 'PENDING' and delivery.attempts == 0 and provider.messages == {}
        return
    assert process_sensor_pending(provider) == 1
    delivery, = sensor_deliveries()
    assert (delivery.state, delivery.outcome) == ('SUPPRESSED', reason) and provider.messages == {}


@pytest.mark.parametrize('stop', ['terminate', 'expire', 'disarm', 'disable'])
def test_stopped_sessions_create_no_new_triggers(client, armed, monkeypatch, stop):
    water(client, armed, 5)
    arm(client, armed)
    session, admin = armed['session'], armed['admin']
    if stop == 'terminate':
        client.post(f'{ROOT}/sessions/{session}/terminate', headers=admin, json={'reason': 'Stop'})
    elif stop == 'expire':
        with SessionLocal() as db:
            db.execute(update(ExerciseSession).values(expires_at=utc_now() - timedelta(seconds=1)))
            db.commit()
    elif stop == 'disarm':
        client.post(f'{ROOT}/sessions/{session}/stations/disarm', headers=admin,
                    json={'station_id': armed['station'], 'reason': 'Demo over'})
    else:
        monkeypatch.setattr(get_settings(), 'exercise_notifications_enabled', False)
    water(client, armed, 105)
    assert scan_sensor_triggers() == 0 and triggers() == []


def test_revoked_recipient_gets_no_delivery_and_trigger_records_it(client, armed):
    water(client, armed, 5)
    arm(client, armed)
    client.post(f"{ROOT}/sessions/{armed['session']}/recipients/revoke", headers=armed['admin'],
                json={'device_id': armed['device_id'], 'reason': 'Removed'})
    water(client, armed, 105)
    assert scan_sensor_triggers() == 1
    assert triggers()[0].status == 'NO_RECIPIENTS' and sensor_deliveries() == []


def test_unknown_outcome_is_never_resent(client, armed):
    progress_to_evacuate(client, armed)

    class Exploding(FakeNotificationProvider):
        def send(self, target, message, *, delivery_key):
            raise TimeoutError('synthetic timeout after possible acceptance')
    assert process_sensor_pending(Exploding()) == 1
    assert sensor_deliveries()[0].state == 'UNKNOWN'
    provider = FakeNotificationProvider()
    assert process_sensor_pending(provider) == 0 and provider.messages == {}


def test_shared_rate_limit_and_session_cap(client, armed, monkeypatch):
    monkeypatch.setattr(get_settings(), 'exercise_min_send_interval_seconds', 30)
    water(client, armed, 5)
    arm(client, armed)
    water(client, armed, 70)
    water(client, armed, 105)
    assert scan_sensor_triggers() == 2
    assert [(d.state, d.outcome) for d in sensor_deliveries()] == [('PENDING', None), ('SUPPRESSED', 'rate_limited')]
    # The manual Stage A path sees the sensor send in the same per-device interval.
    response = client.post(f"{ROOT}/sessions/{armed['session']}/send", headers=armed['admin'], json={
        'device_id': armed['device_id'], 'idempotency_key': 'manual-after-sensor', 'reason': 'Manual check'})
    assert response.status_code == 429


def test_session_cap_marks_trigger_send_limit(client, armed):
    with SessionLocal() as db:
        db.execute(update(ExerciseSession).values(max_sends=1))
        db.commit()
    water(client, armed, 5)
    arm(client, armed)
    water(client, armed, 70)
    water(client, armed, 105)
    assert scan_sensor_triggers() == 2
    assert [t.status for t in triggers()] == ['DELIVERIES_CREATED', 'SEND_LIMIT']
    assert len(sensor_deliveries()) == 1


def test_arming_requires_admin_active_session_and_trusted_physical_station(client, armed):
    from test_notifications import resident
    url = f"{ROOT}/sessions/{armed['session']}/stations"
    body = {'station_id': armed['station'], 'reason': 'Demo'}
    assert client.post(url, json=body).status_code == 401
    assert client.post(url, headers=resident(client, 'other@example.com'), json=body).status_code == 403
    assert client.post(url, headers=armed['admin'], json={**body, 'station_id': 'NO_SUCH_STATION'}).status_code == 409
    client.post(f"{ROOT}/sessions/{armed['session']}/terminate", headers=armed['admin'], json={'reason': 'Stop'})
    assert client.post(url, headers=armed['admin'], json=body).status_code == 409


# --- Migration integrity ----------------------------------------------------------------

def test_0007_upgrades_after_0006_preserving_rows_and_detects_drift(tmp_path, monkeypatch):
    import app.migrations as migrations
    bind = create_engine(f"sqlite:///{(tmp_path / 'incremental.db').as_posix()}")
    full_revisions, full_snapshots = migrations.REVISIONS, migrations.SNAPSHOTS
    through = full_revisions.index('0007_exercise_sensor_triggers')  # later revisions (0008+) may follow
    monkeypatch.setattr(migrations, 'REVISIONS', full_revisions[:through])
    monkeypatch.setattr(migrations, 'SNAPSHOTS', full_snapshots[:through])
    assert migrations.upgrade(bind)[-1] == '0006_exercise_notifications'
    assert not inspect(bind).has_table('exercise_sensor_triggers')
    from sqlalchemy.orm import Session
    from app.models import User
    with Session(bind) as db:  # a 0006-era row that the 0007 upgrade must preserve
        admin = User(name='Synthetic admin', email='a@example.invalid', password_hash='not-a-login', role='admin')
        db.add(admin)
        db.flush()
        db.add(ExerciseSession(id='s1', created_by=admin.id, reason='kept', max_sends=1,
                               expires_at=utc_now() + timedelta(minutes=5)))
        db.commit()
    monkeypatch.setattr(migrations, 'REVISIONS', full_revisions[:through + 1])
    monkeypatch.setattr(migrations, 'SNAPSHOTS', full_snapshots[:through + 1])
    assert migrations.upgrade(bind) == ['0007_exercise_sensor_triggers']
    migrations.require_current(bind)
    with bind.connect() as connection:
        assert connection.execute(text("SELECT reason FROM exercise_sessions")).scalar() == 'kept'
    with bind.begin() as connection:
        connection.execute(text('DROP TABLE exercise_sensor_deliveries'))
    with pytest.raises(RuntimeError, match='missing table'):
        migrations.require_current(bind)
    bind.dispose()


def test_session_evidence_lists_arm_triggers_and_sensor_deliveries(client, armed):
    progress_to_evacuate(client, armed)
    evidence = client.get(f"{ROOT}/sessions/{armed['session']}", headers=armed['admin']).json()
    assert evidence['armed_stations'][0]['station_id'] == armed['station']
    assert evidence['sensor_triggers'][0]['current_tier'] == 'EVACUATE'
    assert evidence['sensor_triggers'][0]['message_type'] == 'EXERCISE_TEST'
    assert evidence['sensor_deliveries'][0]['trigger'] == 'sensor'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ExerciseStationArm)) == 1
