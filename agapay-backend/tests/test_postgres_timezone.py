"""R2 UTC policy on real PostgreSQL (suite mode only; synthetic data).

Every timestamp column is timestamptz. The application forces TimeZone=UTC per connection, so
a non-UTC server or database default cannot shift what AGAPAY reads or renders. Other clients
in other zones see the same instants and the same ordering.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, text

from app.database import SessionLocal, engine
from app.models import AlertTransition, Telemetry, utc_now
from test_accounts import reset_accounts, staff  # noqa: F401
from test_alerts import send, station  # noqa: F401

pytestmark = pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='PostgreSQL timezone behaviour')
ZONES = ('Asia/Manila', 'Pacific/Kiritimati', 'America/Adak', 'America/New_York')


@pytest.fixture
def foreign():
    """A plain client engine that does NOT force UTC (like psql or a reporting tool)."""
    bind = create_engine(engine.url)
    yield bind
    bind.dispose()


def epochs(bind, zone, sql, **params):
    with bind.connect() as c:
        c.exec_driver_sql(f"SET TIME ZONE '{zone}'")
        return [row[0] for row in c.execute(text(sql), params)]


def test_application_sessions_are_utc_regardless_of_server_and_database_defaults(foreign):
    database = engine.url.database
    with foreign.connect() as c:
        server_default = c.execute(text('SHOW TimeZone')).scalar()
    try:
        with foreign.begin() as c:
            c.exec_driver_sql(f'ALTER DATABASE "{database}" SET TimeZone = \'Asia/Manila\'')
        probe = create_engine(engine.url)
        with probe.connect() as c:
            assert c.execute(text('SHOW TimeZone')).scalar() == 'Asia/Manila', 'database-level default applies to plain clients'
        probe.dispose()
        engine.dispose()
        with engine.connect() as c:
            assert c.execute(text('SHOW TimeZone')).scalar() == 'UTC', 'the application connection overrides it'
        with SessionLocal() as db:
            assert db.scalar(text('SELECT now()')).utcoffset() == timedelta(0)
    finally:
        with foreign.begin() as c:
            c.exec_driver_sql(f'ALTER DATABASE "{database}" RESET TimeZone')
        engine.dispose()
    assert server_default  # recorded server default (Asia/Kuala_Lumpur on the drill instance)


def test_ingested_timestamps_are_the_same_instants_and_order_in_every_zone(client, station, foreign):  # noqa: F811
    for sequence, depth in enumerate((30, 70, 90, 105, 50), start=1):
        send(client, station, sequence, depth)
    with SessionLocal() as db:
        rows = db.execute(select(Telemetry.id, Telemetry.recorded_at, Telemetry.received_at)
                          .where(Telemetry.station_id == station).order_by(Telemetry.recorded_at, Telemetry.id)).all()
        transitions = db.execute(select(AlertTransition.id, AlertTransition.transitioned_at)
                                 .where(AlertTransition.station_id == station).order_by(AlertTransition.id)).all()
    assert all(r.recorded_at.utcoffset() == timedelta(0) for r in rows), 'application reads are rendered in UTC'
    expected_ids = [r.id for r in rows]
    expected_epochs = [r.received_at.timestamp() for r in rows]
    for zone in ZONES:
        assert epochs(foreign, zone, 'SELECT id FROM telemetry WHERE station_id = :s ORDER BY recorded_at, id', s=station) == expected_ids
        assert epochs(foreign, zone, 'SELECT extract(epoch FROM received_at)::float8 FROM telemetry WHERE station_id = :s ORDER BY recorded_at, id',
                      s=station) == pytest.approx(expected_epochs)
        assert epochs(foreign, zone, 'SELECT id FROM alert_transitions WHERE station_id = :s ORDER BY transitioned_at, id',
                      s=station) == sorted(t.id for t in transitions)


@pytest.mark.parametrize('instant', [
    datetime(2026, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc),   # UTC year boundary
    datetime(2026, 11, 12, 16, 0, 0, tzinfo=timezone.utc),              # local midnight in Manila / Kuala Lumpur
    datetime(2026, 11, 1, 5, 30, 0, tzinfo=timezone.utc),               # inside the New York DST fold (01:30 occurs twice)
    datetime(2026, 3, 8, 7, 30, 0, tzinfo=timezone.utc),                # inside the New York DST gap (02:30 does not exist)
])
def test_boundary_instants_round_trip_unchanged_through_foreign_sessions(instant, foreign):
    from app.runtime_models import SharedReadModel
    key = 'tz-boundary:' + instant.isoformat()[:40]
    with SessionLocal() as db:
        db.merge(SharedReadModel(key=key, generation='g', payload={}, checked_at=instant, expires_at=instant + timedelta(seconds=2)))
        db.commit()
    try:
        for zone in ZONES:
            with foreign.connect() as c:
                c.exec_driver_sql(f"SET TIME ZONE '{zone}'")
                value, epoch = c.execute(text('SELECT checked_at, extract(epoch FROM checked_at)::float8 FROM shared_read_models '
                                              'WHERE key = :k'), {'k': key}).one()
                assert epoch == pytest.approx(instant.timestamp()), 'the stored instant is unchanged'
                if zone == 'America/New_York' and (instant.month, instant.day) == (11, 1):
                    # Client-side hazard, not a storage fault: a DST-fold wall time from a local-zone
                    # session never compares equal across zones in Python (PEP 495). UTC sessions avoid it.
                    assert value != instant
                else:
                    assert value == instant
                # A foreign-zone writer that supplies an explicit offset stores the same instant.
                c.execute(text('UPDATE shared_read_models SET expires_at = :v WHERE key = :k'), {'v': instant, 'k': key})
                c.commit()
        with SessionLocal() as db:
            assert db.get(SharedReadModel, key, populate_existing=True).expires_at == instant
    finally:
        with SessionLocal() as db:
            db.query(SharedReadModel).filter(SharedReadModel.key == key).delete()
            db.commit()


def test_naive_literal_shift_is_exactly_the_risk_utc_sessions_remove(foreign):
    """A naive timestamp literal is interpreted in the session zone; UTC sessions remove the offset."""
    with foreign.connect() as c:
        c.exec_driver_sql("SET TIME ZONE 'Asia/Manila'")
        shifted = c.execute(text("SELECT '2026-11-13 00:00:00'::timestamptz")).scalar()
    with engine.connect() as c:
        exact = c.execute(text("SELECT '2026-11-13 00:00:00'::timestamptz")).scalar()
    assert exact == datetime(2026, 11, 13, tzinfo=timezone.utc)
    assert exact - shifted == timedelta(hours=8)


def test_expiry_decisions_and_recovery_generation_times_are_zone_independent(client, foreign, monkeypatch):
    from app.exercise_models import ExerciseSession
    from app.models import User
    from app.recovery_models import DeliveryGeneration
    from app.services.exercise_notifications import session_problem
    staff(client)
    now = utc_now()
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == 'admin@example.com'))
        expired = ExerciseSession(created_by=admin.id, reason='TZ drill expired', max_sends=1, expires_at=now - timedelta(seconds=1))
        live = ExerciseSession(created_by=admin.id, reason='TZ drill live', max_sends=1, expires_at=now + timedelta(minutes=5))
        db.add_all([expired, live]); db.commit()
        ids = (expired.id, live.id)
    for zone in ZONES:   # write the same instants again from a foreign zone, then decide in the app
        with foreign.begin() as c:
            c.exec_driver_sql(f"SET TIME ZONE '{zone}'")
            c.execute(text('UPDATE exercise_sessions SET expires_at = :v WHERE id = :i'), {'v': now - timedelta(seconds=1), 'i': ids[0]})
            c.execute(text('UPDATE exercise_sessions SET expires_at = :v WHERE id = :i'), {'v': now + timedelta(minutes=5), 'i': ids[1]})
        with SessionLocal() as db:
            assert session_problem(db, db.get(ExerciseSession, ids[0], populate_existing=True), now) == 'session_expired'
            assert session_problem(db, db.get(ExerciseSession, ids[1], populate_existing=True), now) is None
    with SessionLocal() as db:
        generation = db.scalar(select(DeliveryGeneration).where(DeliveryGeneration.state == 'ACTIVE'))
        assert generation.activated_at.utcoffset() == timedelta(0)
        for zone in ZONES:
            assert epochs(foreign, zone, 'SELECT extract(epoch FROM activated_at)::float8 FROM delivery_generations WHERE generation = :g',
                          g=generation.generation) == pytest.approx([generation.activated_at.timestamp()])
    with SessionLocal() as db:
        db.query(ExerciseSession).filter(ExerciseSession.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
