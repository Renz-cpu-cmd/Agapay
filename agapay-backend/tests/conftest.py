import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DATABASE = Path(__file__).with_name("agapay_test.db").resolve()
# R2: opt-in real PostgreSQL run of the whole suite. Only an explicit loopback
# agapay_test_* database is accepted, and its public schema is reset before and after.
TEST_POSTGRES_URL = os.environ.get("AGAPAY_TEST_SUITE_POSTGRES_URL")
if TEST_POSTGRES_URL:
    from sqlalchemy.engine import make_url
    _target = make_url(TEST_POSTGRES_URL)
    if (_target.get_backend_name() != "postgresql" or _target.host not in ("127.0.0.1", "localhost", "::1")
            or not (_target.database or "").startswith("agapay_test_")):
        raise RuntimeError("AGAPAY_TEST_SUITE_POSTGRES_URL must be a loopback PostgreSQL agapay_test_* database")
    os.environ["AGAPAY_DATABASE_URL"] = TEST_POSTGRES_URL
else:
    os.environ["AGAPAY_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ["AGAPAY_MQTT_ENABLED"] = "false"
os.environ["AGAPAY_READ_MODEL_CACHE_ENABLED"] = "false"
os.environ["AGAPAY_OBSERVABILITY_ENABLED"] = "false"
# R4: legacy fixtures use synthetic stations without a field_reviewed configuration and
# only fake providers. This relaxation is honoured solely because the provider stays
# "disabled"; tests/test_operational_eligibility.py exercises the default-deny policy.
os.environ["AGAPAY_OPERATIONAL_REVIEW_REQUIRED"] = "false"

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


def _reset_postgres_schema():
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")


@pytest.fixture(scope="session", autouse=True)
def clean_database():
    if TEST_POSTGRES_URL:
        _reset_postgres_schema()
    if TEST_DATABASE.exists():
        TEST_DATABASE.unlink()
    from app.migrations import upgrade
    upgrade(engine)
    yield
    from app.migrations import LEDGER
    LEDGER.drop(engine, checkfirst=True)
    Base.metadata.drop_all(bind=engine)
    if TEST_POSTGRES_URL:
        _reset_postgres_schema()
    engine.dispose()
    if TEST_DATABASE.exists():
        TEST_DATABASE.unlink()


@pytest.fixture()
def client():
    from app.database import SessionLocal
    from app.seed import seed_demo_station
    with SessionLocal() as db:
        seed_demo_station(db)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_station_security():
    from app.database import SessionLocal
    from app.forecast_models import TABLES as FORECAST_TABLES
    from app.exercise_models import TABLES as EXERCISE_TABLES
    with SessionLocal() as db:
        # Exercise rows reference devices and users; remove them before either.
        for table in EXERCISE_TABLES:db.execute(table.delete())
        db.commit()
    with SessionLocal() as db:
        for table in reversed(FORECAST_TABLES):db.execute(table.delete())
        db.commit()
    from app.privacy_models import TABLES as PRIVACY_TABLES
    with SessionLocal() as db:
        for table in reversed(PRIVACY_TABLES):db.execute(table.delete())
        db.commit()
    from app.delivery_models import TABLES as DELIVERY_TABLES
    with SessionLocal() as db:
        for table in reversed(DELIVERY_TABLES):db.execute(table.delete())
        db.commit()
    from app.runtime_models import TABLES as RUNTIME_TABLES
    with SessionLocal() as db:
        for table in RUNTIME_TABLES:db.execute(table.delete())
        db.commit()
    from app.models import StationAuditEvent, StationCredential, StationIdentity, StationIngressBudget, StationTelemetryState, TelemetryBoot, StationSourceRegistry, TelemetryProvenance, ExerciseTelemetry
    from app.device_config import StationConfiguration
    from station_support import _measurement_origins
    _measurement_origins.clear()
    with SessionLocal() as db:
        for model in (StationConfiguration, TelemetryProvenance, ExerciseTelemetry, StationSourceRegistry, StationTelemetryState, TelemetryBoot, StationIngressBudget, StationCredential, StationAuditEvent, StationIdentity):
            db.query(model).delete()
        db.commit()


def reset_delivery_recovery():
    """R2 P0: each test starts with one fresh ACTIVE delivery generation and no holds.

    Holds key on delivery ids, which SQLite reuses after deletes, so stale holds must not
    leak between tests. Bulk deletes bypass the ORM append-only guard on purpose (test only)."""
    from app.database import SessionLocal
    from app.models import utc_now
    from app.recovery_models import TABLES as RECOVERY_TABLES, DeliveryGeneration
    from app.services.delivery_recovery import database_identity
    from uuid import uuid4
    with SessionLocal() as db:
        for table in reversed(RECOVERY_TABLES):db.execute(table.delete())
        db.add(DeliveryGeneration(generation=1, token=str(uuid4()), state='ACTIVE', kind='initialize',
                                  reason='Test database with no delivery history', claim_seq=0,
                                  database_identity=database_identity(db), activated_at=utc_now()))
        db.commit()


@pytest.fixture(autouse=True)
def delivery_generation(clean_notifications):
    reset_delivery_recovery()
    yield


@pytest.fixture(autouse=True)
def clean_notifications(clean_station_security):
    # Explicit dependency: autouse fixtures otherwise run alphabetically, deleting devices
    # before the exercise rows that reference them (enforced by PostgreSQL foreign keys).
    # New dependent tables must be isolated before account/station fixtures.
    from app.database import SessionLocal
    from app.forecast_models import TABLES as FORECAST_TABLES
    with SessionLocal() as db:
        for table in reversed(FORECAST_TABLES):db.execute(table.delete())
        db.commit()
    from app.models import NotificationDelivery, NotificationEvent, NotificationDevice
    from app.governance_models import TABLES
    from app.operations_models import TABLES as OPERATIONS_TABLES
    with SessionLocal() as db:
        from app.delivery_models import TABLES as DELIVERY_TABLES
        for table in reversed(DELIVERY_TABLES):db.execute(table.delete())
        from app.identity_models import TABLES as IDENTITY_TABLES
        from app.sos_response_models import TABLES as SOS_TABLES
        from app.resource_models import TABLES as RESOURCE_TABLES
        for table in reversed(RESOURCE_TABLES):db.execute(table.delete())
        for table in reversed(SOS_TABLES):db.execute(table.delete())
        for table in reversed(IDENTITY_TABLES):db.execute(table.delete())
        for table in reversed(OPERATIONS_TABLES):db.execute(table.delete())
        for table in reversed(TABLES):
            db.execute(table.delete())
        for model in (NotificationDelivery, NotificationEvent, NotificationDevice):
            db.query(model).delete()
        db.commit()
