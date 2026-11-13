"""Upgrade an isolated SQLite backup and compare every original row/column.

Source is opened read-only. Destination must not exist. Never prints row contents.
"""
import argparse
from pathlib import Path
import sqlite3
from sqlalchemy import create_engine
from app.migrations import upgrade, require_current


def snapshot(connection):
    result = {}
    names = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for name in names:
        quoted = '"'+name.replace('"','""')+'"'
        columns = [row[1] for row in connection.execute(f'PRAGMA table_info({quoted})')]
        # This existing migration deliberately fills null session public IDs.
        if name == 'auth_sessions':
            columns = [column for column in columns if column != 'public_id']
        select = ','.join('"'+c.replace('"','""')+'"' for c in columns)
        result[name] = (columns, sorted(connection.execute(f'SELECT {select} FROM {quoted}').fetchall(), key=repr))
    return result


def verify(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists():
        raise ValueError('Copy destination must be new and distinct from source')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as original:
        with sqlite3.connect(destination) as copy:
            original.backup(copy)
            before = snapshot(copy)
    bind = create_engine('sqlite:///'+destination.as_posix())
    try:
        upgrade(bind)
        require_current(bind)
    finally:
        bind.dispose()
    with sqlite3.connect(destination) as copy:
        for name, (columns, rows) in before.items():
            if name == 'schema_migrations':
                continue
            quoted = '"'+name.replace('"','""')+'"'
            select = ','.join('"'+c.replace('"','""')+'"' for c in columns)
            after = sorted(copy.execute(f'SELECT {select} FROM {quoted}').fetchall(), key=repr)
            if after != rows:
                raise RuntimeError(f'Preservation mismatch in {name}; source untouched')
        if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or copy.execute('PRAGMA foreign_key_check').fetchone():
            raise RuntimeError('Copy integrity verification failed')
    return {name: len(rows) for name, (_, rows) in before.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--copy', type=Path, required=True)
    args = parser.parse_args()
    print('Preserved original rows by table:', verify(args.source, args.copy))
    print('Only the isolated copy was upgraded; source was opened read-only')
