"""R2 P0 on real PostgreSQL: restored deliveries are never replayed (pg_dump / pg_restore).

Opt-in. Runs only in PostgreSQL suite mode (AGAPAY_TEST_SUITE_POSTGRES_URL = source) with
AGAPAY_TEST_POSTGRES_RESTORE_URL (a second loopback agapay_test_* database, reset here) and
AGAPAY_TEST_PG_BIN. Optional: AGAPAY_TEST_POSTGRES_MIGRATE_URL (schema-mismatch backup) and
AGAPAY_TEST_PG_DATA (server restart). Independent engines/connections; fake providers only.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import subprocess
import threading

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import engine
from app.models import Alert, AlertTransition, NotificationDelivery, Telemetry, utc_now
from app.recovery_models import DeliveryGeneration, DeliveryHold, DeliveryRecoveryEvent
from app.services import delivery_recovery as recovery
from app.services.notification_service import enqueue_transition, process_pending
from test_accounts import reset_accounts, staff  # noqa: F401
from test_alerts import send, station  # noqa: F401
from test_notifications import register, resident

RESTORE_URL = os.environ.get('AGAPAY_TEST_POSTGRES_RESTORE_URL')
MIGRATE_URL = os.environ.get('AGAPAY_TEST_POSTGRES_MIGRATE_URL')
PG_BIN = os.environ.get('AGAPAY_TEST_PG_BIN')
PG_DATA = os.environ.get('AGAPAY_TEST_PG_DATA')
pytestmark = pytest.mark.skipif(not (engine.dialect.name == 'postgresql' and RESTORE_URL and PG_BIN),
                                reason='Real PostgreSQL backup/restore recovery drill not configured')
REASON = 'Synthetic R2 drill: database restored from an older backup'


def _loopback(url):
    target = make_url(url)
    assert target.host in ('127.0.0.1', 'localhost', '::1') and (target.database or '').startswith('agapay_test_')
    return target


def tool(name, url, *args, check=True):
    target = _loopback(url)
    result = subprocess.run([os.path.join(PG_BIN, name + ('.exe' if os.name == 'nt' else '')), '-h', target.host,
                             '-p', str(target.port or 5432), '-U', target.username, *args],
                            env={**os.environ, 'PGPASSWORD': target.password or ''}, capture_output=True, text=True)
    if check:
        assert result.returncode == 0, f'{name} failed'
    return result.returncode


def reset(bind):
    with bind.begin() as connection:
        connection.exec_driver_sql('DROP SCHEMA public CASCADE')
        connection.exec_driver_sql('CREATE SCHEMA public')


def dump(url, path):
    tool('pg_dump', url, '-d', make_url(url).database, '-Fc', '--no-owner', '-f', str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore_into(bind, path, check=True):
    """Restore a backup into a database, replacing what is there (never the development DB)."""
    bind.dispose()
    reset(bind)
    return tool('pg_restore', bind.url.render_as_string(hide_password=False), '-d', bind.url.database, '--no-owner',
                '--single-transaction', '--exit-on-error', str(path), check=check)


class Recording:
    mode = 'test'

    def __init__(self):
        self.keys, self.lock = [], threading.Lock()

    def send(self, target, message, *, delivery_key):
        from app.services.notification_provider import SendOutcome
        with self.lock:
            self.keys.append(delivery_key)
        return SendOutcome.TEST_ONLY


@pytest.fixture
def target():
    bind = create_engine(RESTORE_URL)
    _loopback(RESTORE_URL)
    yield bind, sessionmaker(bind=bind, expire_on_commit=False)
    bind.dispose()
    reset(bind)
    bind.dispose()


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / 'delivery-ledger'
    monkeypatch.setattr(get_settings(), 'delivery_ledger_path', str(path))
    recovery._ledgers.clear()
    yield path
    recovery._ledgers.clear()


def admin(client):
    """Create the drill administrator BEFORE the backup so the restored copy contains it."""
    staff(client)
    from app.models import User
    from app.database import SessionLocal
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == 'admin@example.com'))


def subscribed(client, station, residents=1):  # noqa: F811
    for n in range(residents):
        access = resident(client, f'resident{n}@example.com')
        register(client, access, token=f'synthetic-push-token-{n}', installation=f'00000000-0000-4000-8000-0000000001{n:02d}')
    send(client, station, 1, 70)  # ADVISORY escalation -> one PENDING delivery per device


def escalate(factory, station_id, severity, depth):
    """A genuinely new escalation written straight into a (restored) database."""
    with factory() as db:
        alert = db.scalar(select(Alert).where(Alert.station_id == station_id, Alert.status == 'ACTIVE'))
        sequence = (db.scalar(select(func.max(Telemetry.sequence_no)).where(Telemetry.station_id == station_id)) or 0) + 1
        sample = Telemetry(station_id=station_id, sequence_no=sequence, sensor_quality='valid', device_uptime_ms=sequence * 1000,
                           water_depth_cm=depth)
        db.add(sample)
        db.flush()
        change = AlertTransition(alert_id=alert.id, station_id=station_id, telemetry_id=sample.id, sequence_no=sequence,
                                 previous_severity=alert.current_severity, new_severity=severity, water_depth_cm=depth,
                                 transitioned_at=utc_now())
        db.add(change)
        alert.current_severity = alert.highest_severity = severity
        db.flush()
        enqueue_transition(db, change)
        db.commit()


def states(factory):
    with factory() as db:
        return {row.id: row.state for row in db.scalars(select(NotificationDelivery))}


def declare_and_activate(factory, actor, *, decide=True):
    with factory() as db:
        number = recovery.declare(db, kind='restore', reason=REASON).generation
        db.commit()
    if decide:
        with factory() as db:
            for hold in db.scalars(select(DeliveryHold).where(DeliveryHold.decision.is_(None))).all():
                recovery.decide(db, hold.id, actor_id=actor, decision='outcome_unknown', evidence_kind='no_provider_record',
                                evidence_sha256='a' * 64, reason='No provider export covers the restore window',
                                expected_version=hold.version)
            db.commit()
    with factory() as db:
        recovery.activate(db, actor_id=actor, reason='Synthetic drill reconciled; reopen new-generation delivery',
                          allow_undecided=not decide)
        db.commit()
    return number


# --- Restored PENDING after the original system already sent it ----------------------------

def test_raw_restore_of_a_sent_pending_delivery_is_fenced_then_held(client, station, target, ledger, tmp_path):  # noqa: F811
    bind, factory = target
    actor = admin(client)
    subscribed(client, station)
    backup = tmp_path / 'before-send.dump'
    dump(str(engine.url.render_as_string(hide_password=False)), backup)          # 1. backup with PENDING
    with engine.connect() as c:                                                    # live system is ledger-anchored
        generation = c.execute(select(DeliveryGeneration).where(DeliveryGeneration.state == 'ACTIVE')).one()
    recovery.Ledger(ledger).anchor(generation.token, generation.claim_seq)
    original = Recording()
    assert process_pending(original) == 1 and len(original.keys) == 1             # 2. sent after the backup
    restore_into(bind, backup)                                                      # 3. restore the older backup
    assert set(states(factory).values()) == {'PENDING'}, 'restored row looks unsent'
    replay = Recording()
    with pytest.raises(recovery.DeliveryFenced, match='identity'):                 # 4. unmodified-looking worker
        process_pending(replay, session_factory=factory)
    with factory() as db:  # Even if identity were carried over (physical restore), the ledger refuses.
        db.execute(update(DeliveryGeneration).values(database_identity=recovery.database_identity(db)))
        db.commit()
    with pytest.raises(recovery.DeliveryFenced, match='behind the external ledger'):
        process_pending(replay, session_factory=factory)
    assert replay.keys == [] and set(states(factory).values()) == {'PENDING'}, 'refused claims rolled back'
    # Recovery: hold, reconcile, activate a distinct generation; old work never resent.
    number = declare_and_activate(factory, actor)
    with factory() as db:
        hold, = db.scalars(select(DeliveryHold)).all()
        assert (hold.generation, hold.original_state, hold.decision) == (number, 'PENDING', 'outcome_unknown')
        assert db.scalar(select(DeliveryGeneration.token).where(DeliveryGeneration.state == 'ACTIVE')) != generation.token
    assert process_pending(replay, session_factory=factory) == 0 and replay.keys == []
    escalate(factory, station, 'EVACUATE', 120)                                    # genuinely new alert
    assert process_pending(replay, session_factory=factory) == 1
    new_id = max(states(factory))
    assert replay.keys == [f'agapay-delivery-{new_id}'] and original.keys != replay.keys
    assert process_pending(replay, session_factory=factory) == 0 and len(replay.keys) == 1


def test_same_database_restore_is_caught_by_the_external_ledger(client, station, target, ledger, tmp_path):  # noqa: F811
    """Restoring into the SAME database keeps its identity; only the external ledger can tell."""
    bind, factory = target
    actor = admin(client)
    subscribed(client, station)
    first = tmp_path / 'source.dump'
    dump(str(engine.url.render_as_string(hide_password=False)), first)
    restore_into(bind, first)
    declare_and_activate(factory, actor)
    escalate(factory, station, 'WARNING', 90)
    second = tmp_path / 'same-db.dump'
    dump(RESTORE_URL, second)                     # backup while the WARNING delivery is PENDING
    provider = Recording()
    assert process_pending(provider, session_factory=factory) == 1
    restore_into(bind, second)                    # same database, same identity, older claim sequence
    with pytest.raises(recovery.DeliveryFenced, match='behind the external ledger'):
        process_pending(provider, session_factory=factory)
    assert len(provider.keys) == 1


def test_repeated_and_older_restores_after_a_newer_generation_are_fenced(client, station, target, ledger, tmp_path):  # noqa: F811
    bind, factory = target
    actor = admin(client)
    subscribed(client, station)
    backup = tmp_path / 'generation-1.dump'
    dump(str(engine.url.render_as_string(hide_password=False)), backup)
    restore_into(bind, backup)
    declare_and_activate(factory, actor)          # generation 2, ledger anchored to it
    escalate(factory, station, 'WARNING', 90)
    provider = Recording()
    assert process_pending(provider, session_factory=factory) == 1
    for attempt in range(2):                                         # the same older backup, twice
        restore_into(bind, backup)
        with pytest.raises(recovery.DeliveryFenced, match='identity'):
            process_pending(provider, session_factory=factory)
        with factory() as db:
            db.execute(update(DeliveryGeneration).values(database_identity=recovery.database_identity(db)))
            db.commit()
        with pytest.raises(recovery.DeliveryFenced, match='does not match the external ledger'):
            process_pending(provider, session_factory=factory)
    assert len(provider.keys) == 1


# --- Boundary states ----------------------------------------------------------------------

def test_boundary_states_are_held_or_left_terminal_and_nothing_is_resent(client, station, target, ledger, tmp_path):  # noqa: F811
    bind, factory = target
    actor = admin(client)
    subscribed(client, station, residents=6)
    from app.database import SessionLocal
    with SessionLocal() as db:
        ids = sorted(db.scalars(select(NotificationDelivery.id)))
        plan = dict(zip(ids, ('PENDING', 'PROCESSING', 'UNKNOWN', 'SENT', 'FAILED', 'SUPPRESSED')))
        for identity, state in plan.items():
            db.execute(update(NotificationDelivery).where(NotificationDelivery.id == identity).values(
                state=state, attempts=0 if state == 'PENDING' else 1, attempted_at=None if state == 'PENDING' else utc_now(),
                next_attempt_at=utc_now() if state == 'FAILED' else None))   # FAILED is retry-due
        db.commit()
    backup = tmp_path / 'boundary.dump'
    dump(str(engine.url.render_as_string(hide_password=False)), backup)
    restore_into(bind, backup)
    number = declare_and_activate(factory, actor, decide=False)
    with factory() as db:
        held = {int(h.delivery_id): (h.original_state, h.reason_code) for h in db.scalars(select(DeliveryHold))}
        events = list(db.scalars(select(DeliveryRecoveryEvent.action).where(DeliveryRecoveryEvent.generation == number)))
    assert held == {i: (s, recovery.REASONS[s]) for i, s in plan.items() if s in ('PENDING', 'PROCESSING', 'UNKNOWN', 'FAILED')}
    assert events == ['recovery_declared', 'recovery_activated']
    provider = Recording()
    assert process_pending(provider, session_factory=factory) == 0 and provider.keys == []
    assert states(factory) == plan, 'no restored row is rewritten, retried or resent'


def test_declaration_racing_live_claims_never_sends_a_held_row(client, station, target, ledger, tmp_path):  # noqa: F811
    bind, factory = target
    actor = admin(client)
    subscribed(client, station, residents=8)
    backup = tmp_path / 'race.dump'
    dump(str(engine.url.render_as_string(hide_password=False)), backup)
    restore_into(bind, backup)
    declare_and_activate(factory, actor)
    escalate(factory, station, 'WARNING', 90)     # 8 new PENDING deliveries in the active generation
    provider = Recording()
    go = threading.Barrier(5)

    def worker(_):
        go.wait()
        try:
            return process_pending(provider, limit=2, session_factory=factory)
        except recovery.DeliveryFenced:
            return 'fenced'

    def declarer():
        go.wait()
        with factory() as db:
            recovery.declare(db, kind='declared', reason='Operator declared recovery mid-batch', actor_id=actor)
            db.commit()
    with ThreadPoolExecutor(5) as pool:
        futures = [pool.submit(worker, n) for n in range(4)] + [pool.submit(declarer)]
        [f.result() for f in futures]
    with factory() as db:
        open_holds = {h.delivery_id for h in db.scalars(select(DeliveryHold).where(
            DeliveryHold.decision.is_(None), DeliveryHold.original_state == 'PENDING'))}
        rows = {str(r.id): (r.state, r.result_category) for r in db.scalars(select(NotificationDelivery))}
    sent = {key.rsplit('-', 1)[1] for key in provider.keys}
    assert not sent & open_holds, 'a delivery held as PENDING never reached the provider'
    assert all(rows[i][0] == 'TESTED' for i in sent), 'every send corresponds to a recorded, completed claim'
    assert all(state in ('TESTED', 'SUPPRESSED', 'PENDING') for state, _ in rows.values())
    assert len(sent) == len(provider.keys), 'no delivery sent twice'


# --- Exercise isolation on a restored database ----------------------------------------------

def test_restored_exercise_work_is_held_and_new_eligibility_is_rechecked(client, target, ledger, tmp_path, monkeypatch):
    from datetime import timedelta
    from app.exercise_models import ExerciseConsent, ExerciseDelivery, ExerciseRecipient, ExerciseSession
    from app.models import NotificationDevice, User
    from app.services.exercise_notifications import process_pending as exercise_process
    from app.database import SessionLocal
    bind, factory = target
    monkeypatch.setattr(get_settings(), 'exercise_notifications_enabled', True)
    now = utc_now()
    with SessionLocal() as db:
        boss = User(name='Synthetic Admin', email='admin@example.com', password_hash='x', role='admin')
        people = [User(name=f'Synthetic Resident {n}', email=f'ex{n}@example.invalid', password_hash='x', role='resident') for n in (1, 2)]
        db.add_all([boss, *people]); db.flush()
        devices = [NotificationDevice(user_id=p.id, installation_id=f'r2-ex-{n}', platform='android', session_hash='d' * 64, provider='fcm',
                                      provider_token=f'synthetic-ex-token-{n}', token_hash=str(n) * 64, enabled=True) for n, p in enumerate(people)]
        db.add_all(devices); db.flush()
        for device in devices:
            db.add(ExerciseConsent(device_id=device.id, user_id=device.user_id, device_revision=device.revision))
        live = ExerciseSession(created_by=boss.id, reason='R2 recovery drill', max_sends=10, expires_at=now + timedelta(hours=1))
        ended = ExerciseSession(created_by=boss.id, reason='R2 ended drill', max_sends=10, expires_at=now + timedelta(minutes=2))
        db.add_all([live, ended]); db.flush()
        for session in (live, ended):
            for device in devices:
                db.add(ExerciseRecipient(session_id=session.id, device_id=device.id, device_revision=device.revision, added_by=boss.id))
        restored = ExerciseDelivery(session_id=live.id, device_id=devices[0].id, device_revision=devices[0].revision,
                                    requested_by=boss.id, idempotency_key='r2-restored', state='PENDING', attempts=0)
        db.add(restored); db.commit()
        ids = dict(live=live.id, ended=ended.id, restored=restored.id, d0=devices[0].id, d1=devices[1].id, boss=boss.id,
                   revisions=[d.revision for d in devices])
    backup = tmp_path / 'exercise.dump'
    dump(str(engine.url.render_as_string(hide_password=False)), backup)
    restore_into(bind, backup)
    provider = Recording()
    with pytest.raises(recovery.DeliveryFenced):
        exercise_process(provider, session_factory=factory)
    declare_and_activate(factory, ids['boss'])
    with factory() as db:
        hold, = db.scalars(select(DeliveryHold)).all()
        assert (hold.kind, hold.delivery_id) == ('exercise_manual', ids['restored'])
        db.execute(update(ExerciseSession).where(ExerciseSession.id == ids['ended']).values(expires_at=now - timedelta(seconds=1)))
        db.execute(update(ExerciseConsent).where(ExerciseConsent.device_id == ids['d1']).values(revoked_at=now))
        for key, session, device, revision in (('new-live', ids['live'], ids['d0'], ids['revisions'][0]),
                                               ('new-ended', ids['ended'], ids['d0'], ids['revisions'][0]),
                                               ('new-revoked', ids['live'], ids['d1'], ids['revisions'][1])):
            db.add(ExerciseDelivery(session_id=session, device_id=device, device_revision=revision, requested_by=ids['boss'],
                                    idempotency_key=key, state='PENDING', attempts=0))
        db.commit()
    assert exercise_process(provider, session_factory=factory) == 3
    with factory() as db:
        outcome = {d.idempotency_key: (d.state, d.outcome) for d in db.scalars(select(ExerciseDelivery))}
        assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0, 'exercise never becomes operational'
    assert outcome == {'r2-restored': ('PENDING', None), 'new-live': ('TESTED', 'test_only'),
                       'new-ended': ('SUPPRESSED', 'session_expired'), 'new-revoked': ('SUPPRESSED', 'device_owner_not_opted_in')}
    assert len(provider.keys) == 1 and provider.keys[0].startswith('exercise:')


# --- Metadata failure, corruption and schema mismatch ---------------------------------------

def test_missing_recovery_metadata_fails_closed(client, station, target, tmp_path):  # noqa: F811
    bind, factory = target
    subscribed(client, station)
    backup = tmp_path / 'metadata.dump'
    dump(str(engine.url.render_as_string(hide_password=False)), backup)
    restore_into(bind, backup)
    provider = Recording()
    with factory() as db:
        db.execute(DeliveryGeneration.__table__.delete()); db.commit()
    with pytest.raises(recovery.DeliveryFenced, match='not initialized'):
        process_pending(provider, session_factory=factory)
    with bind.begin() as c:
        c.exec_driver_sql('DROP TABLE delivery_generations')
    with pytest.raises(recovery.DeliveryFenced, match='unavailable'):
        process_pending(provider, session_factory=factory)
    assert provider.keys == []


def test_corrupt_backup_restores_nothing_and_nothing_is_sent(client, station, target, tmp_path):  # noqa: F811
    from app.migrations import require_current
    bind, factory = target
    subscribed(client, station)
    backup = tmp_path / 'corrupt.dump'
    dump(str(engine.url.render_as_string(hide_password=False)), backup)
    data = backup.read_bytes()
    backup.write_bytes(data[:len(data) // 2])
    assert restore_into(bind, backup, check=False) != 0
    with pytest.raises(RuntimeError, match='Schema migration required'):
        require_current(bind)
    with pytest.raises(Exception):
        process_pending(Recording(), session_factory=factory)  # No schema at all: nothing to claim, nothing sent.


@pytest.mark.skipif(not MIGRATE_URL, reason='Schema-mismatch backup database not configured')
def test_pre_0008_backup_is_refused_by_schema_and_by_the_delivery_gate(target, tmp_path, monkeypatch):
    import app.migrations as migrations
    from app.migrations import require_current
    bind, factory = target
    old = create_engine(MIGRATE_URL)
    _loopback(MIGRATE_URL)
    try:
        reset(old)
        through = migrations.REVISIONS.index('0007_exercise_sensor_triggers') + 1
        monkeypatch.setattr(migrations, 'REVISIONS', migrations.REVISIONS[:through])
        monkeypatch.setattr(migrations, 'SNAPSHOTS', migrations.SNAPSHOTS[:through])
        migrations.upgrade(old)
        monkeypatch.undo()
        backup = tmp_path / 'pre-0008.dump'
        dump(MIGRATE_URL, backup)
    finally:
        old.dispose(); reset(old); old.dispose()
    restore_into(bind, backup)
    with pytest.raises(RuntimeError, match='Schema migration required'):
        require_current(bind)
    with pytest.raises(recovery.DeliveryFenced, match='unavailable'):
        process_pending(Recording(), session_factory=factory)


@pytest.mark.skipif(not PG_DATA, reason='PostgreSQL data directory not provided for the restart drill')
def test_server_restart_without_restore_keeps_delivering(client, station, ledger):  # noqa: F811
    from app.database import SessionLocal
    subscribed(client, station)
    with SessionLocal() as db:
        generation = db.scalar(select(DeliveryGeneration).where(DeliveryGeneration.state == 'ACTIVE'))
        recovery.Ledger(ledger).anchor(generation.token, generation.claim_seq)
    provider = Recording()
    assert process_pending(provider) == 1
    engine.dispose()
    subprocess.run([os.path.join(PG_BIN, 'pg_ctl' + ('.exe' if os.name == 'nt' else '')), '-D', PG_DATA, '-m', 'fast', '-w', 'restart',
                    '-l', os.path.join(PG_DATA, '..', 'postgres-restart.log')],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=120)
    engine.dispose()
    recovery._ledgers.clear()  # Workers restart with the server.
    send(client, station, 2, 105)
    assert process_pending(provider) == 1 and len(set(provider.keys)) == 2
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DeliveryHold)) == 0, 'a restart quarantines nothing'
