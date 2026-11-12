"""R2: the monitoring snapshot reads all stations with a fixed number of queries.

On PostgreSQL 16 the previous per-station loop issued ~15 queries per station (601 for 40
stations) and, under concurrent ingestion, rebuilt slower than the 2 s read-model TTL, so
readers received 503s. The count must not grow with the number of stations."""
from uuid import uuid4

from sqlalchemy import event

from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import Station
from app.services.monitoring_service import monitoring_snapshot
from station_support import device_token
from test_alerts import send

BUDGET = 20


def _stations(client, count):
    ids = []
    for _ in range(count):
        sid = 'BUDGET_' + uuid4().hex[:10].upper()
        with SessionLocal() as db:
            db.add(Station(station_id=sid, station_name='Synthetic budget station'))
            db.commit()
        device_token(sid)
        for sequence, depth in enumerate((30, 70, 90), 1):
            send(client, sid, sequence, depth)
        ids.append(sid)
    return ids


def _queries(station_ids):
    seen = []
    listener = lambda *args, **kwargs: seen.append(1)  # noqa: E731
    event.listen(engine, 'before_cursor_execute', listener)
    try:
        with SessionLocal() as db:
            snapshot = monitoring_snapshot(db, stale_after_seconds=30, history_limit=20,
                                           settings=get_settings(), station_ids=station_ids)
    finally:
        event.remove(engine, 'before_cursor_execute', listener)
    assert {s.station_id for s in snapshot.stations} == set(station_ids)
    return len(seen), snapshot


def test_monitoring_query_count_does_not_grow_with_station_count(client):
    few = _stations(client, 3)
    many = few + _stations(client, 9)
    few_queries, _ = _queries(few)
    many_queries, snapshot = _queries(many)
    assert many_queries == few_queries, f'queries grew with stations: {few_queries} -> {many_queries}'
    assert many_queries <= BUDGET
    # Per-station values still come from each station's own rows.
    for station in snapshot.stations:
        assert station.station_id in many and station.latest_depth_cm == 90 and len(station.history) == 3
        assert station.active_hazard_tier == 'WARNING'
