"""R2: opt-in PostgreSQL migration acceptance (0001-0007). Never selects a deployment database.

Set AGAPAY_TEST_POSTGRES_ACCEPTANCE_URL to a loopback PostgreSQL database named agapay_test_*.
Each test RESETS that database's public schema, so it must be disposable.
"""
import os
import threading
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import migrations
from app.database import Base
from app.migrations import LEDGER, REVISIONS, checksum, require_current, upgrade
from app.models import AuthSession, NotificationDevice, SosRequest, Station, User, utc_now

URL = os.environ.get('AGAPAY_TEST_POSTGRES_ACCEPTANCE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='No disposable PostgreSQL acceptance database configured')


@pytest.fixture
def pg():
    target = make_url(URL)
    if target.host not in ('127.0.0.1', 'localhost', '::1') or not (target.database or '').startswith('agapay_test_'):
        pytest.fail('PostgreSQL acceptance target must be an explicit loopback agapay_test_* database')
    bind = create_engine(URL, pool_pre_ping=True)
    _reset(bind)
    yield bind
    _reset(bind)
    bind.dispose()


def _reset(bind):
    with bind.begin() as connection:
        connection.exec_driver_sql('DROP SCHEMA public CASCADE')
        connection.exec_driver_sql('CREATE SCHEMA public')


def _upgrade_through(bind, revision, monkeypatch):
    """Apply the real migration chain only up to ``revision`` (as an older release would)."""
    index = REVISIONS.index(revision) + 1
    with monkeypatch.context() as patched:
        patched.setattr(migrations, 'REVISIONS', REVISIONS[:index])
        patched.setattr(migrations, 'SNAPSHOTS', migrations.SNAPSHOTS[:index])
        return migrations.upgrade(bind)


def _ledger(bind):
    with bind.connect() as connection:
        return [tuple(row) for row in connection.execute(select(LEDGER.c.revision, LEDGER.c.checksum).order_by(LEDGER.c.revision))]


def _table_dump(bind, tables):
    dump = {}
    with bind.connect() as connection:
        for name in sorted(tables):
            columns = [c['name'] for c in inspect(connection).get_columns(name)]
            select_list = ', '.join(f'"{c}"' for c in columns)
            order = ', '.join(f'"{c}"::text' for c in columns)  # json has no ordering operator
            rows = connection.exec_driver_sql(f'SELECT {select_list} FROM "{name}" ORDER BY {order}').fetchall()
            dump[name] = [tuple(map(str, row)) for row in rows]
    return dump


def test_fresh_migration_applies_0001_through_0007_once_in_order(pg):
    assert upgrade(pg) == list(REVISIONS)
    assert _ledger(pg) == [(revision, checksum(revision)) for revision in REVISIONS]
    require_current(pg)
    assert upgrade(pg) == [], 'repeat execution is a verified no-op'
    assert len(_ledger(pg)) == len(REVISIONS), 'no duplicated ledger rows'


def test_upgrade_from_0005_preserves_existing_records(pg, monkeypatch):
    assert _upgrade_through(pg, '0005_privacy_recovery', monkeypatch) == list(REVISIONS[:5])
    with pytest.raises(RuntimeError, match='Schema migration required'):
        require_current(pg)
    now = utc_now()
    with Session(pg) as db:
        resident = User(name='Synthetic Resident', email='r2-resident@example.invalid', password_hash='x', role='resident')
        officer = User(name='Synthetic Officer', email='r2-officer@example.invalid', password_hash='x', role='officer')
        db.add_all([resident, officer, Station(station_id='R2_STATION', station_name='Synthetic R2 station', created_at=now)])
        db.flush()
        db.add_all([
            AuthSession(token_hash='a' * 64, user_id=resident.id, expires_at=now + timedelta(days=1)),
            # Disabled device: ck_notification_token requires a token only for enabled devices.
            NotificationDevice(user_id=resident.id, installation_id='r2-install', platform='android', session_hash='b' * 64,
                               enabled=False),
            SosRequest(user_id=resident.id, request_id='00000000-0000-4000-8000-000000000001', payload_hash='c' * 64,
                       resident_name='Synthetic Resident', phone='+639000000000', barangay='Synthetic', location='Practice only',
                       location_source='manual'),
        ])
        db.commit()
    existing = set(inspect(pg).get_table_names()) - {LEDGER.name}
    before = _table_dump(pg, existing)
    assert upgrade(pg) == list(REVISIONS[5:]), '0006 and 0007 applied on top of 0005'
    require_current(pg)
    assert _table_dump(pg, existing) == before, 'every pre-existing row is byte-identical after upgrade'
    # New exercise tables reference the preserved rows through real foreign keys.
    with pg.begin() as connection:
        officer_id = connection.execute(text("SELECT id FROM users WHERE email='r2-officer@example.invalid'")).scalar_one()
        columns = {c['name']: c for c in inspect(connection).get_columns('exercise_sessions')}
        assert 'created_by' in columns or any(fk['referred_table'] == 'users' for fk in inspect(connection).get_foreign_keys('exercise_sessions'))
        assert officer_id


def test_concurrent_migrators_serialize_on_the_advisory_lock(pg):
    barrier, results, errors = threading.Barrier(2), [], []

    def migrate():
        engine = create_engine(URL)
        try:
            barrier.wait()
            results.append(upgrade(engine))
        except Exception as error:  # noqa: BLE001
            errors.append(error)
        finally:
            engine.dispose()

    workers = [threading.Thread(target=migrate) for _ in range(2)]
    [worker.start() for worker in workers]
    [worker.join(120) for worker in workers]
    assert errors == []
    assert sorted(map(len, results)) == [0, len(REVISIONS)], 'exactly one migrator applies the chain'
    assert _ledger(pg) == [(revision, checksum(revision)) for revision in REVISIONS]


@pytest.mark.parametrize('damage,message', [
    ('DROP INDEX ix_exercise_sensor_triggers_session_id', 'index drift'),
    ('ALTER TABLE exercise_sensor_deliveries DROP COLUMN outcome', 'Schema drift'),
    ('DROP TABLE exercise_sensor_deliveries', 'Schema missing table'),
    ('ALTER TABLE exercise_sessions ADD COLUMN unreviewed_note TEXT', 'Unreviewed column'),
    ("UPDATE schema_migrations SET checksum = repeat('0', 64) WHERE revision = '0007_exercise_sensor_triggers'", 'checksum mismatch'),
    (f"DELETE FROM schema_migrations WHERE revision = '{REVISIONS[-1]}'", 'Schema migration required'),  # the latest one
])
def test_damaged_or_drifted_schema_is_detected(pg, damage, message):
    upgrade(pg)
    with pg.begin() as connection:
        connection.exec_driver_sql(damage)
    with pytest.raises(RuntimeError, match=message):
        require_current(pg)


def test_unrecognized_partial_database_is_refused(pg):
    with pg.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE stray_table (id INTEGER PRIMARY KEY)')
    with pytest.raises(RuntimeError, match='Unrecognized partial legacy database'):
        upgrade(pg)
    assert not inspect(pg).has_table(LEDGER.name), 'nothing recorded'


def _constraints(bind):
    inspector = inspect(bind)
    fks, checks = set(), {}
    for table in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table):
            fks.add((table, tuple(fk['constrained_columns']), fk['referred_table'], tuple(fk['referred_columns'])))
        checks[table] = len(inspector.get_check_constraints(table))
    return fks, checks


def test_foreign_keys_and_checks_match_sqlite_and_the_orm(pg, tmp_path):
    upgrade(pg)
    lite = create_engine('sqlite:///' + (tmp_path / 'parity.db').as_posix())
    upgrade(lite)
    pg_fks, pg_checks = _constraints(pg)
    lite_fks, lite_checks = _constraints(lite)
    lite.dispose()
    assert pg_fks == lite_fks, 'foreign keys are identical on both engines'
    assert {t: n for t, n in pg_checks.items() if n} == {t: n for t, n in lite_checks.items() if n}, 'CHECK constraints per table'
    model_fks = {(t.name, tuple(c.parent.name for c in fk.elements), fk.elements[0].column.table.name,
                  tuple(c.column.name for c in fk.elements))
                 for t in Base.metadata.sorted_tables for fk in t.foreign_key_constraints if t.name in inspect(pg).get_table_names()}
    assert model_fks - pg_fks == set(), 'every ORM foreign key exists in the migrated PostgreSQL schema'
    exercise = {fk for fk in pg_fks if fk[0].startswith('exercise_')}
    assert ('exercise_sensor_triggers', ('telemetry_id',), 'telemetry', ('id',)) in exercise
    assert sum(n for t, n in pg_checks.items() if t.startswith('exercise_')) >= 15


# --- Backup / restore with outstanding exercise deliveries --------------------------------
RESTORE_URL = os.environ.get('AGAPAY_TEST_POSTGRES_RESTORE_URL')
PG_BIN = os.environ.get('AGAPAY_TEST_PG_BIN')


class _CountingProvider:
    """In-process stand-in: records attempts, never contacts a network service."""
    mode = 'test'

    def __init__(self):
        self.keys = []

    def send(self, target, message, *, delivery_key):
        from app.services.notification_provider import SendOutcome
        self.keys.append(delivery_key)
        return SendOutcome.TEST_ONLY


def _pg_tool(name, url, *args):
    import subprocess
    target = make_url(url)
    env = {**os.environ, 'PGPASSWORD': target.password or ''}
    command = [os.path.join(PG_BIN, name), '-h', target.host, '-p', str(target.port or 5432),
               '-U', target.username, *args]
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f'{name} failed: {result.stderr[-400:]}'


@pytest.mark.skipif(not (RESTORE_URL and PG_BIN), reason='Restore target or PostgreSQL client tools not configured')
def test_restore_preserves_evidence_and_never_replays_attempted_deliveries(pg, tmp_path, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.config import get_settings
    from app.exercise_models import ExerciseConsent, ExerciseDelivery, ExerciseRecipient, ExerciseSession
    from app.services.exercise_notifications import process_pending
    restore = make_url(RESTORE_URL)
    assert restore.host in ('127.0.0.1', 'localhost', '::1') and (restore.database or '').startswith('agapay_test_')
    upgrade(pg)
    now = utc_now()
    with Session(pg) as db:  # The live source has an active delivery generation bound to its identity.
        from app.services.delivery_recovery import initialize_empty
        initialize_empty(db)
        db.commit()
    with Session(pg) as db:
        admin = User(name='Synthetic Admin', email='r2-admin@example.invalid', password_hash='x', role='admin')
        resident = User(name='Synthetic Resident', email='r2-resident@example.invalid', password_hash='x', role='resident')
        db.add_all([admin, resident]); db.flush()
        device = NotificationDevice(user_id=resident.id, installation_id='r2-restore', platform='android', session_hash='d' * 64,
                                    provider='fcm', provider_token='synthetic-token-not-real', token_hash='e' * 64, enabled=True)
        db.add(device); db.flush()
        db.add(ExerciseConsent(device_id=device.id, user_id=resident.id, device_revision=device.revision))
        live = ExerciseSession(created_by=admin.id, reason='R2 restore', max_sends=10, expires_at=now + timedelta(hours=1))
        expired = ExerciseSession(created_by=admin.id, reason='R2 expired', max_sends=10, expires_at=now - timedelta(minutes=1))
        db.add_all([live, expired]); db.flush()
        for session in (live, expired):
            db.add(ExerciseRecipient(session_id=session.id, device_id=device.id, device_revision=device.revision, added_by=admin.id))
        states = {'PENDING': live, 'PROCESSING': live, 'UNKNOWN': live, 'TESTED': live, 'SUPPRESSED': live, 'EXPIRED_PENDING': expired}
        ids = {}
        for label, session in states.items():
            state = 'PENDING' if label == 'EXPIRED_PENDING' else label
            row = ExerciseDelivery(session_id=session.id, device_id=device.id, device_revision=device.revision,
                                   requested_by=admin.id, idempotency_key='r2-' + label.lower(), state=state,
                                   attempts=0 if state == 'PENDING' else 1)
            db.add(row); db.flush(); ids[label] = row.id
        db.commit()
    tables = set(inspect(pg).get_table_names())
    original = _table_dump(pg, tables)
    dump = tmp_path / 'agapay.dump'
    _pg_tool('pg_dump.exe' if os.name == 'nt' else 'pg_dump', URL, '-d', make_url(URL).database, '-Fc', '--no-owner', '-f', str(dump))
    target = create_engine(RESTORE_URL)
    try:
        _reset(target)
        _pg_tool('pg_restore.exe' if os.name == 'nt' else 'pg_restore', RESTORE_URL, '-d', restore.database, '--no-owner',
                 '--exit-on-error', str(dump))
        require_current(target)
        assert _table_dump(target, tables) == original, 'restored copy is row-for-row identical'
        # Resume processing on the restored copy (in-process provider, exercise mode for this test only).
        monkeypatch.setenv('AGAPAY_EXERCISE_NOTIFICATIONS_ENABLED', 'true')
        get_settings.cache_clear()
        provider = _CountingProvider()
        factory = sessionmaker(bind=target, expire_on_commit=False)
        # R2 P0: before this fix the restored PENDING delivery was sent again here. A raw
        # restore is now detected (database identity) and nothing is attempted.
        from app.services.delivery_recovery import DeliveryFenced, activate, declare
        with pytest.raises(DeliveryFenced, match='identity'):
            process_pending(provider, limit=50, session_factory=factory)
        with factory() as db:  # Declared recovery holds the uncertain rows; activation reopens new work only.
            declare(db, kind='restore', reason='R2 acceptance restore drill (synthetic)')
            db.commit()
        with factory() as db:
            activate(db, actor_id=db.scalar(select(User.id).where(User.role == 'admin')), allow_undecided=True,
                     reason='R2 acceptance drill: holds deferred, never resent')
            db.commit()
        assert process_pending(provider, limit=50, session_factory=factory) == 0
        assert provider.keys == [], 'no restored delivery reaches the provider'
        with factory() as db:
            state = {label: db.get(ExerciseDelivery, ident).state for label, ident in ids.items()}
        assert state == {'PENDING': 'PENDING', 'PROCESSING': 'PROCESSING', 'UNKNOWN': 'UNKNOWN', 'TESTED': 'TESTED',
                         'SUPPRESSED': 'SUPPRESSED', 'EXPIRED_PENDING': 'PENDING'}, 'restored evidence is never rewritten'
    finally:
        get_settings.cache_clear()
        _reset(target)
        target.dispose()


def test_exercise_evidence_blocks_deleting_referenced_telemetry_and_stations(pg):
    """Exercise triggers keep their telemetry/station evidence: PostgreSQL refuses a purge that
    would orphan them, leaves the evidence intact, and allows it once the evidence is removed."""
    from sqlalchemy.exc import IntegrityError
    from app.exercise_models import ExerciseSensorTrigger, ExerciseSession, ExerciseStationArm
    from app.models import Telemetry
    upgrade(pg)
    now = utc_now()
    with Session(pg) as db:
        admin = User(name='Synthetic Admin', email='r2-evidence@example.invalid', password_hash='x', role='admin')
        db.add_all([admin, Station(station_id='R2_EVIDENCE', station_name='Synthetic evidence station', created_at=now)])
        db.flush()
        reading = Telemetry(station_id='R2_EVIDENCE', sequence_no=1, sensor_quality='valid', device_uptime_ms=1000,
                            recorded_at=now, water_depth_cm=90)
        session = ExerciseSession(created_by=admin.id, reason='R2 evidence', max_sends=1, expires_at=now + timedelta(hours=1))
        db.add_all([reading, session]); db.flush()
        db.add(ExerciseStationArm(session_id=session.id, station_id='R2_EVIDENCE', armed_by=admin.id, baseline_tier='NORMAL',
                                  baseline_telemetry_id=reading.id, cursor_telemetry_id=reading.id))
        db.add(ExerciseSensorTrigger(session_id=session.id, station_id='R2_EVIDENCE', telemetry_id=reading.id,
                                     source_class='physical_device', ingress_identity='SYNTH', ingress_transport='http',
                                     registry_version=1, credential_id='synthetic', measured_at=now, received_at=now,
                                     water_depth_cm=90, previous_tier='NORMAL', current_tier='WARNING', status='NO_RECIPIENTS'))
        db.commit()
        telemetry_id = reading.id
    for statement in (f'DELETE FROM telemetry WHERE id = {telemetry_id}', "DELETE FROM stations WHERE station_id = 'R2_EVIDENCE'"):
        with pytest.raises(IntegrityError, match='ForeignKeyViolation|violates foreign key'):
            with pg.begin() as connection:
                connection.exec_driver_sql(statement)
    with pg.connect() as connection:
        assert connection.exec_driver_sql('SELECT count(*) FROM exercise_sensor_triggers').scalar() == 1
        assert connection.exec_driver_sql(f'SELECT count(*) FROM telemetry WHERE id = {telemetry_id}').scalar() == 1
    with pg.begin() as connection:  # deliberate, ordered evidence removal is still possible
        for table in ('exercise_sensor_triggers', 'exercise_station_arms'):
            connection.exec_driver_sql(f'DELETE FROM {table}')
        connection.exec_driver_sql(f'DELETE FROM telemetry WHERE id = {telemetry_id}')


def test_sqlite_transfer_is_independent_of_the_server_time_zone(pg, tmp_path):
    """A Philippine-hosted server (Asia/Manila, +08:00) must not shift naive SQLite UTC
    timestamps. Before the fix the row digest caught an 8-hour shift and refused the restore."""
    from datetime import datetime, timezone
    from app.transfer_database import transfer
    source = create_engine('sqlite:///' + (tmp_path / 'tz-source.db').as_posix())
    manila = create_engine(URL, connect_args={'options': '-c timezone=Asia/Manila'})
    try:
        upgrade(source)
        with source.begin() as db:
            db.exec_driver_sql("INSERT INTO stations (station_id,station_name,sensor_height_cm,threshold_advisory_cm,"
                               "threshold_warning_cm,threshold_evacuate_cm,status,created_at) VALUES "
                               "('PG_TZ','Synthetic time-zone fixture',120,60,85,100,'maintenance','2026-10-22 06:30:00')")
        with manila.connect() as connection:
            assert connection.exec_driver_sql('SHOW timezone').scalar() == 'Asia/Manila'
        assert transfer(source, manila)['stations'] == 1
        with manila.connect() as connection:
            stored = connection.exec_driver_sql("SELECT created_at FROM stations WHERE station_id='PG_TZ'").scalar()
        assert stored.astimezone(timezone.utc) == datetime(2026, 10, 22, 6, 30, tzinfo=timezone.utc)
    finally:
        source.dispose(); manila.dispose()
