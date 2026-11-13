"""Per-process PostgreSQL pool defaults (R2 pool acceptance). See docs/database-capacity.md.

Every process owns an independent SQLAlchemy pool, so the server-wide connection count is
the sum over processes. Background workers run one tick at a time and need at most two
connections; they default to pool_size=2, max_overflow=1 unless the deployment sets
AGAPAY_DATABASE_POOL_SIZE / AGAPAY_DATABASE_MAX_OVERFLOW explicitly. Call BEFORE app.database
is imported (the engine is created on import).
"""
import os
import sys

BACKGROUND_POOL = {'AGAPAY_DATABASE_POOL_SIZE': '2', 'AGAPAY_DATABASE_MAX_OVERFLOW': '1'}


def background_defaults():
    if 'app.database' in sys.modules:
        raise RuntimeError('Set background pool defaults before the database engine is created')
    for key, value in BACKGROUND_POOL.items():
        os.environ.setdefault(key, value)
