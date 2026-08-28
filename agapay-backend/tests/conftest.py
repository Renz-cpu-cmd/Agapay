import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DATABASE = Path(__file__).with_name("agapay_test.db").resolve()
os.environ["AGAPAY_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ["AGAPAY_MQTT_ENABLED"] = "false"

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def clean_database():
    if TEST_DATABASE.exists():
        TEST_DATABASE.unlink()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DATABASE.exists():
        TEST_DATABASE.unlink()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
