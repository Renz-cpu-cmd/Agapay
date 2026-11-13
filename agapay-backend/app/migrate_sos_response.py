"""Add SOS concurrency and drill tables without converting any request to operational mode."""
import argparse
from sqlalchemy import inspect, text
from app.database import engine
from app.sos_response_models import TABLES


def needed(bind):
    inspector = inspect(bind)
    return inspector.has_table('sos_requests') and (
        'version' not in {c['name'] for c in inspector.get_columns('sos_requests')}
        or any(not inspector.has_table(t.name) for t in TABLES))


def require_schema(bind):
    if needed(bind):
        raise RuntimeError('SOS migration required. Stop writers, back up, then run python -m app.migrate_sos_response --apply')


def migrate(bind, *, apply=False):
    inspector = inspect(bind)
    if not inspector.has_table('sos_requests'):
        raise RuntimeError('Initialize a fresh schema with the offline administrator bootstrap first')
    add_version = 'version' not in {c['name'] for c in inspector.get_columns('sos_requests')}
    missing = [t.name for t in TABLES if not inspector.has_table(t.name)]
    if apply:
        with bind.begin() as connection:
            if add_version: connection.execute(text('ALTER TABLE sos_requests ADD COLUMN version INTEGER NOT NULL DEFAULT 1'))
        for table in TABLES:
            table.create(bind, checkfirst=True)
            for index in table.indexes: index.create(bind, checkfirst=True)
    return {'add_version': add_version, 'tables': missing, 'apply': apply, 'operational_enabled': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    print(migrate(engine, apply=parser.parse_args().apply))
