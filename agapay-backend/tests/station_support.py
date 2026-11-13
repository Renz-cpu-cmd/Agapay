"""Synthetic station identities for tests of existing domain behavior only.

Security/provisioning acceptance tests use the real admin endpoints instead.
"""
import base64
import hashlib
from datetime import timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.governance_models import HazardPolicy
from app.models import Station, StationCredential, StationIdentity, StationSourceRegistry, utc_now
from app.services.station_security import digest

_measurement_origins = {}


def ordering_fields(station_id, sequence):
    """Deterministic measurement times make exact retries genuinely identical."""
    if station_id not in _measurement_origins:
        _measurement_origins[station_id] = (utc_now() - timedelta(seconds=2), sequence)
    origin, first = _measurement_origins[station_id]
    with SessionLocal() as db:
        identity = db.get(StationIdentity, station_id)
        source = identity.device_id if identity else "TEST_" + station_id
        version = identity.version if identity else 1
    return dict(schema_version=2, config_version=version, source_id=source,
                boot_id="TEST_BOOT_001", boot_sequence=1,
                measured_at=(origin + timedelta(milliseconds=50*(sequence-first))).isoformat())


def device_token(station_id):
    token = "agi_" + base64.urlsafe_b64encode(hashlib.sha256(("test-only:" + station_id).encode()).digest()).decode().rstrip("=")
    with SessionLocal() as db:
        if db.scalar(select(Station.id).where(Station.station_id == station_id)) is None:
            return token  # Unknown stations deliberately receive no authorized identity.
        identity = db.get(StationIdentity, station_id)
        if identity is None:
            db.add(StationIdentity(station_id=station_id, device_id="TEST_" + station_id,
                state="commissioned", coordinates_verified=True, reference_datum="Synthetic test datum",
                calibration_note="Synthetic fixture; not physical calibration", version=1, commissioned_at=utc_now()))
            db.flush()
        if db.scalar(select(StationCredential.id).where(StationCredential.token_hash == digest(token))) is None:
            db.add(StationCredential(station_id=station_id, identity_version=1, token_hash=digest(token),
                label="Synthetic fixture", transport="both", expires_at=utc_now() + timedelta(days=1)))
        if db.get(StationSourceRegistry, (station_id, identity.version if identity else 1)) is None:
            db.add(StationSourceRegistry(station_id=station_id, config_version=identity.version if identity else 1,
                device_id=identity.device_id if identity else "TEST_" + station_id,
                source_class="physical_device", stream="operational", evidence="Synthetic trusted fixture; no physical proof"))
        # Explicit instantaneous synthetic policy keeps transaction/history
        # fixtures independent of the new recovery-domain acceptance tests.
        if db.get(HazardPolicy, station_id) is None:
            db.add(HazardPolicy(station_id=station_id, version=1,
                evidence="Synthetic instantaneous fixture, not approved physical policy",
                rules=dict(advisory_hysteresis_cm=0, warning_hysteresis_cm=0,
                    evacuate_hysteresis_cm=0, recovery_samples=1, recovery_seconds=0,
                    max_sample_gap_seconds=3600, max_change_cm_per_second=10000)))
        db.commit()
    return token


def device_headers(station_id):
    return {"Authorization": "Bearer " + device_token(station_id)}


def command_queue_rows(client, access, scope):
    """Every row of one command-queue scope, by walking the endpoint's own default
    pagination. The shared test database retains ACTIVE episodes from earlier tests
    (cleanup removes their provenance, not the episodes), and the queue orders by
    severity before age, so membership must never be asserted on the first page only."""
    rows, offset, total = [], 0, None
    while True:
        response = client.get('/api/alerts/command-queue', headers=access, params={'scope': scope, 'offset': offset})
        assert response.status_code == 200, response.text
        page = response.json()
        assert page['scope'] == scope and (total is None or page['total'] == total), 'queue changed while paging'
        total = page['total']
        rows += page['items']
        offset += len(page['items'])
        if not page['items'] or offset >= total:
            break
    ids = [row['id'] for row in rows]
    assert len(ids) == len(set(ids)) == total, 'pagination must be complete and duplicate-free'
    return rows


def ingest_authenticated(db, payload):
    """Supply the same authenticated boundary context as real network ingestion."""
    from app.services.telemetry_service import ingest_telemetry
    credential = db.scalar(select(StationCredential).where(StationCredential.station_id == payload.station_id))
    return ingest_telemetry(db, payload, credential_id=credential.id, transport="mqtt")


def purge_station(db, station_id):
    """Delete a synthetic station and everything that references it, children first.

    Walks the ORM foreign-key graph with SQL subqueries, so it stays correct when new
    tables reference stations/telemetry/alerts. PostgreSQL enforces these foreign keys;
    SQLite here does not, which is how out-of-order cleanup previously went unnoticed.
    """
    from sqlalchemy import delete, tuple_
    from app.database import Base

    tables = Base.metadata.sorted_tables

    def purge(table, condition, depth=0):
        if depth > 12:
            raise RuntimeError('Foreign-key graph unexpectedly deep')
        for child in tables:
            for fk in child.foreign_key_constraints:
                if fk.elements[0].column.table is not table or child is table:
                    continue
                local = [element.parent for element in fk.elements]
                remote = [element.column for element in fk.elements]
                parents = select(*remote).where(condition)
                purge(child, (local[0].in_(parents) if len(local) == 1 else tuple_(*local).in_(parents)), depth + 1)
        db.execute(delete(table).where(condition))

    station = Station.__table__
    purge(station, station.c.station_id == station_id)
