"""Add identity columns and workflow tables without deleting accounts or sessions."""
import argparse
from uuid import uuid4
from sqlalchemy import inspect, text
from app.database import engine
from app.identity_models import TABLES

ADDITIONS={
    'users':{'version':'INTEGER NOT NULL DEFAULT 1','email_verified_at':'TIMESTAMP NULL'},
    'auth_sessions':{'public_id':'VARCHAR(36) NULL','audience':"VARCHAR(12) NOT NULL DEFAULT 'legacy'",'mfa_verified_at':'TIMESTAMP NULL'},
}


def missing(bind):
    inspector=inspect(bind);result=[]
    for table,columns in ADDITIONS.items():
        if inspector.has_table(table):
            present={c['name'] for c in inspector.get_columns(table)}
            result.extend(f'{table}.{key}' for key in columns if key not in present)
    return result


def require_schema(bind):
    inspector=inspect(bind)
    absent=inspector.has_table("users") and any(not inspector.has_table(table.name) for table in TABLES)
    if missing(bind) or absent:raise RuntimeError('Identity migration required. Stop writers, back up, then run python -m app.migrate_identity_security --apply')


def migrate(bind,*,apply=False):
    plan=missing(bind)
    absent=[t.name for t in TABLES if not inspect(bind).has_table(t.name)]
    if apply:
        with bind.begin() as db:
            for item in plan:
                table,column=item.split('.')
                db.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ADDITIONS[table][column]}'))
            if inspect(bind).has_table('auth_sessions'):
                hashes=db.execute(text('SELECT token_hash FROM auth_sessions WHERE public_id IS NULL')).scalars().all()
                for digest in hashes:db.execute(text('UPDATE auth_sessions SET public_id=:id WHERE token_hash=:hash'),{'id':str(uuid4()),'hash':digest})
                db.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_auth_sessions_public_id ON auth_sessions(public_id)'))
        for table in TABLES:
            table.create(bind,checkfirst=True)
            for index in table.indexes:index.create(bind,checkfirst=True)
    return {'columns':plan,'tables':absent}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();print(migrate(engine,apply=args.apply))
