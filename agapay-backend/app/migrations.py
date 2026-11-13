"""Offline ordered migrations. Serving processes only verify, never migrate or seed.

Stop all writers and take a tested backup before applying. Legacy SQLite upgrades
reuse the reviewed preservation scripts; PostgreSQL starts from the frozen schema.
There is deliberately no destructive downgrade or automatic legacy stamp command.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path

from sqlalchemy import Column, DateTime, MetaData, String, Table, inspect, select, text
from app.database import engine

ROOT = Path(__file__).parent
SNAPSHOT = ROOT / 'migrations/0001_schema.json'
LEGACY = ('station_security', 'telemetry_ordering', 'station_provenance',
          'alert_governance', 'history_index', 'interval_configuration',
          'operations_preferences', 'identity_security', 'sos_response', 'response_resources')
LEDGER = Table('schema_migrations', MetaData(),
               Column('revision', String(32), primary_key=True),
               Column('checksum', String(64), nullable=False),
               Column('applied_at', DateTime(timezone=True), nullable=False))
REVISIONS = ('0001_preserved_baseline', '0002_workflow_runtime', '0003_delivery_evidence', '0004_forecast_registry', '0005_privacy_recovery',
             '0006_exercise_notifications', '0007_exercise_sensor_triggers', '0008_delivery_recovery',
             '0009_location_precision', '0010_station_tracking')
SNAPSHOTS = (SNAPSHOT, ROOT / 'migrations/0002_runtime.json', ROOT / 'migrations/0003_delivery.json', ROOT / 'migrations/0004_forecasts.json', ROOT / 'migrations/0005_privacy.json',
             ROOT / 'migrations/0006_exercise_notifications.json', ROOT / 'migrations/0007_exercise_sensor_triggers.json',
             ROOT / 'migrations/0008_delivery_recovery.json', ROOT / 'migrations/0009_location_precision.json',
             ROOT / 'migrations/0010_station_tracking.json')


def checksum(revision=None):
    revision = revision or REVISIONS[-1]
    index = REVISIONS.index(revision)
    digest = hashlib.sha256(SNAPSHOTS[index].read_bytes().replace(b'\r\n', b'\n'))
    if index == 0:
        for name in LEGACY:
            digest.update((ROOT / f'migrate_{name}.py').read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()


def schema(bind, through=None):
    if bind.dialect.name not in ('sqlite', 'postgresql'):
        raise RuntimeError('Only reviewed SQLite and PostgreSQL migrations are supported')
    limit = REVISIONS.index(through)+1 if through else len(REVISIONS)
    return [table for path in SNAPSHOTS[:limit] for table in json.loads(path.read_text(encoding='utf-8'))[bind.dialect.name]]


def verified_rows(bind):
    if not inspect(bind).has_table(LEDGER.name): return []
    with bind.connect() as connection:
        rows=connection.execute(select(LEDGER).order_by(LEDGER.c.revision)).mappings().all()
    if tuple(row['revision'] for row in rows) != REVISIONS[:len(rows)] or any(row['checksum']!=checksum(row['revision']) for row in rows):
        raise RuntimeError('Schema migration revision/checksum mismatch; manual review required')
    return rows


def require_current(bind):
    inspector = inspect(bind)
    if not inspector.has_table(LEDGER.name):
        raise RuntimeError('Schema migration required: run python -m app.migrations offline')
    rows=verified_rows(bind)
    if len(rows)!=len(REVISIONS):
        raise RuntimeError('Schema migration required: run python -m app.migrations offline')
    validate_schema(bind)


def validate_schema(bind, through=None):
    # A ledger is not sufficient if tables/columns/indexes were manually altered.
    inspector = inspect(bind)
    for table in schema(bind, through):
        if not inspector.has_table(table['name']):
            raise RuntimeError(f"Schema missing table {table['name']}; restore/review required")
        columns = {c['name'] for c in inspector.get_columns(table['name'])}
        if not set(table['columns']).issubset(columns):
            raise RuntimeError(f"Schema drift in {table['name']}; restore/review required")
        for column in inspector.get_columns(table['name']):
            expected = table['column_contract'].get(column['name'])
            if not expected:
                raise RuntimeError(f"Unreviewed column in {table['name']}; migration required")
            actual_type = str(column['type'].compile(dialect=bind.dialect))
            if bind.dialect.name == 'sqlite' and actual_type == 'TIMESTAMP' and expected['type'] == 'DATETIME':
                actual_type = 'DATETIME' # Same SQLite affinity; reviewed additive legacy timestamp columns.
            if bind.dialect.name == 'postgresql' and actual_type == 'DOUBLE PRECISION' and expected['type'] == 'FLOAT':
                actual_type = 'FLOAT' # PostgreSQL reflects unqualified FLOAT as double precision.
            if actual_type != expected['type']:
                raise RuntimeError(f"Schema type drift in {table['name']}.{column['name']}")
            # The reviewed legacy migration backfills these public IDs and adds a
            # unique index; SQLite cannot add a NOT NULL column without rebuilding.
            compatible_legacy_nullability = (table['name'], column['name']) == ('auth_sessions','public_id')
            if column['nullable'] != expected['nullable'] and not compatible_legacy_nullability:
                raise RuntimeError(f"Schema nullability drift in {table['name']}.{column['name']}")
        indexes = {i['name'] for i in inspector.get_indexes(table['name'])}
        if not {i['name'] for i in table['indexes']}.issubset(indexes):
            raise RuntimeError(f"Schema index drift in {table['name']}; review required")
        uniques={tuple(item['column_names']) for item in inspector.get_unique_constraints(table['name'])}
        uniques.update(tuple(item['column_names']) for item in inspector.get_indexes(table['name']) if item.get('unique'))
        if not {tuple(item) for item in table['unique_contract']}.issubset(uniques):
            raise RuntimeError(f"Schema uniqueness drift in {table['name']}; review required")
        if tuple(inspector.get_pk_constraint(table['name'])['constrained_columns']) != tuple(table['primary_key']):
            raise RuntimeError(f"Schema primary key drift in {table['name']}; review required")
    from app.migrate_telemetry_ordering import require_ordering_schema
    require_ordering_schema(bind)


@contextmanager
def migration_lock(bind):
    if bind.dialect.name == 'postgresql':
        with bind.connect() as connection:
            connection.execute(text('SELECT pg_advisory_lock(7310042901)'))
            try:
                yield
            finally:
                connection.execute(text('SELECT pg_advisory_unlock(7310042901)'))
    else:
        path = bind.url.database
        if not path or path == ':memory:':
            yield
            return
        lock = Path(path).resolve().with_suffix('.migration.lock')
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise RuntimeError('Migration lock exists; check the owner before manually clearing a stale lock') from None
        try:
            os.write(descriptor, str(os.getpid()).encode())
            yield
        finally:
            os.close(descriptor)
            lock.unlink()


def upgrade(bind):
    """Explicit, ordered offline operation; applied revision checksums are immutable."""
    schema(bind)
    with migration_lock(bind):
        rows=verified_rows(bind)
        if len(rows)==len(REVISIONS):
            require_current(bind);return []
        existing=set(inspect(bind).get_table_names())-{LEDGER.name}
        if existing and not rows:
            if not {'stations','telemetry','users'}.issubset(existing):
                raise RuntimeError('Unrecognized partial legacy database; review before migration')
            for name in LEGACY:
                importlib.import_module(f'app.migrate_{name}').migrate(bind,apply=True)
        applied=[]
        for revision in REVISIONS[len(rows):]:
            with bind.begin() as connection:
                for table in schema(connection,revision):
                    inspector=inspect(connection)
                    if not inspector.has_table(table['name']):
                        connection.exec_driver_sql(table['sql'])
                    columns={c['name'] for c in inspect(connection).get_columns(table['name'])}
                    if not set(table['columns']).issubset(columns):
                        raise RuntimeError(f"Unrecognized legacy columns in {table['name']}; no revision recorded")
                    indexes={i['name'] for i in inspect(connection).get_indexes(table['name'])}
                    for index in table['indexes']:
                        if index['name'] not in indexes:connection.exec_driver_sql(index['sql'])
                if bind.dialect.name=='sqlite' and connection.exec_driver_sql('PRAGMA foreign_key_check').fetchone():
                    raise RuntimeError('Foreign-key integrity failed; no revision recorded')
                validate_schema(connection,revision)
                LEDGER.create(connection,checkfirst=True)
                connection.execute(LEDGER.insert().values(revision=revision,checksum=checksum(revision),applied_at=datetime.now(timezone.utc)))
            applied.append(revision)
        require_current(bind)
        return applied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--writers-stopped', action='store_true')
    parser.add_argument('--backup-confirmed', action='store_true')
    args = parser.parse_args()
    if args.apply:
        if not args.writers_stopped or not args.backup_confirmed:
            parser.error('--apply requires --writers-stopped and --backup-confirmed')
        print('Applied revisions:', upgrade(engine) or 'already current')
    else:
        require_current(engine)
        print('Schema current:', REVISIONS[-1])


if __name__ == '__main__':
    main()
