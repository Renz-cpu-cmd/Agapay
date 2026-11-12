"""Add empty response registry tables; never seed or verify real-world resources."""
import argparse
from sqlalchemy import inspect
from app.database import engine
from app.resource_models import TABLES


def missing(bind):return [t.name for t in TABLES if not inspect(bind).has_table(t.name)]


def require_schema(bind):
    if inspect(bind).has_table('users') and missing(bind):
        raise RuntimeError('Response registry migration required. Back up and stop writers, then run python -m app.migrate_response_resources --apply')


def migrate(bind,*,apply=False):
    plan=missing(bind)
    if apply:
        for table in TABLES:
            table.create(bind,checkfirst=True)
            for index in table.indexes:index.create(bind,checkfirst=True)
    return dict(tables=plan,apply=apply,records_seeded=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    print(migrate(engine,apply=parser.parse_args().apply))
