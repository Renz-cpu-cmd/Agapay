"""Offline SQLite-copy -> empty PostgreSQL restore, with transactional row verification.

The source must already pass ordered migrations. Never run against a live source
or a populated target. Credentials are read from a protected environment variable.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from sqlalchemy import create_engine, func, inspect, select, text
from app.migrations import require_current, upgrade
from app.schema_catalog import metadata


def digest(rows):
    def convert(value):
        if isinstance(value, datetime):
            return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()
        raise TypeError('Unsupported restore value type')
    # Order-independent multiset fingerprint, bounded memory even for long history.
    total=count=0
    for row in rows:
        total=(total+int.from_bytes(hashlib.sha256(json.dumps(dict(row), sort_keys=True, default=convert,
                           separators=(',',':')).encode()).digest(),'big')) % (1<<256)
        count+=1
    return f'{total:064x}', count


def transfer(source, target):
    if source.dialect.name != 'sqlite' or target.dialect.name != 'postgresql':
        raise RuntimeError('Restore supports only a migrated SQLite copy into empty PostgreSQL')
    require_current(source)
    if set(inspect(source).get_table_names()) - set(metadata.tables) - {'schema_migrations'}:
        raise RuntimeError('Source copy contains unreviewed tables; a custom preserving restore is required')
    existing=set(inspect(target).get_table_names())
    if existing - set(metadata.tables) - {'schema_migrations'}:
        raise RuntimeError('Restore target has unrecognized tables; nothing imported')
    # Refuse a populated target BEFORE even applying a schema migration.
    with target.connect() as connection:
        for name in existing - {'schema_migrations'}:
            table=metadata.tables[name]
            if connection.scalar(select(func.count()).select_from(table)):
                raise RuntimeError('Restore target contains application data; no rows imported')
    upgrade(target)
    expected = {}
    # All original application rows are inserted in one PostgreSQL transaction.
    # The target migration ledger is its own deployment record, never copied.
    with source.connect() as reader, target.begin() as writer:
        reader.exec_driver_sql('BEGIN') # Consistent SQLite read snapshot across all tables.
        # SQLite stores naive UTC timestamps; PostgreSQL would interpret them in the server's
        # session time zone (e.g. Asia/Manila, +08:00) and shift every value. Pin UTC here.
        writer.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
        names=', '.join(writer.dialect.identifier_preparer.quote(table.name) for table in metadata.sorted_tables)
        writer.exec_driver_sql('LOCK TABLE '+names+' IN EXCLUSIVE MODE')
        for table in metadata.sorted_tables:
            if writer.scalar(select(func.count()).select_from(table)):
                raise RuntimeError('Restore target contains application data; no rows imported')
        for table in metadata.sorted_tables:
            total=count=0
            for rows in reader.execute(select(table)).mappings().partitions(200):
                part_hash,part_count=digest(rows)
                total=(total+int(part_hash,16)) % (1<<256);count+=part_count
                writer.execute(table.insert(), [dict(row) for row in rows])
            expected[table.name]=(f'{total:064x}',count)
            actual = digest(writer.execute(select(table).execution_options(stream_results=True)).mappings())
            if actual != expected[table.name]:
                raise RuntimeError(f'Restore verification failed for {table.name}; transaction rolled back')
        # Preserve explicit IDs and advance every generated sequence so the first
        # post-restore account/sample/event cannot collide with an imported row.
        for table in metadata.sorted_tables:
            for column in table.primary_key.columns:
                sequence = writer.scalar(text('SELECT pg_get_serial_sequence(:table, :column)'),
                                         {'table':table.name, 'column':column.name})
                if sequence:
                    maximum = writer.scalar(select(func.max(column)))
                    writer.execute(text('SELECT setval(CAST(:sequence AS regclass), :value, :called)'),
                        {'sequence':sequence,'value':max(1,maximum or 1),'called':maximum is not None})
    require_current(target)
    return {name: count for name, (_, count) in expected.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-copy', type=Path, required=True)
    parser.add_argument('--apply-to-reviewed-empty-target', action='store_true')
    args = parser.parse_args()
    if not args.apply_to_reviewed_empty_target:
        raise SystemExit('Inspection only. Review source copy, target and backup/restore plan before --apply-to-reviewed-empty-target')
    target_url = os.environ.get('AGAPAY_RESTORE_DATABASE_URL','')
    if not target_url.startswith('postgresql+psycopg://'):
        raise SystemExit('Set AGAPAY_RESTORE_DATABASE_URL privately to the reviewed empty PostgreSQL target')
    source_path=args.source_copy.resolve()
    if not source_path.is_file():
        raise SystemExit('Source copy does not exist')
    source=create_engine(f'sqlite:///{source_path.as_uri()}?mode=ro&uri=true')
    target=create_engine(target_url)
    try:
        print('Restored and verified rows by table:',transfer(source,target))
    except Exception:
        raise SystemExit('Restore failed; inspect privately. No row values or connection secrets are printed. Application import transaction was rolled back.') from None
    finally:
        source.dispose();target.dispose()


if __name__ == '__main__':
    main()
