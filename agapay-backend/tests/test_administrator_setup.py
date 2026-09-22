from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.account_schemas import RegisterRequest
from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models import AdministratorSetup, User
from app.services.accounts import create_user
from app.services.administrator_setup import create_first_administrator, setup_complete
from test_accounts import PASSWORD, account, reset_accounts  # noqa: F401


@pytest.fixture()
def local_client():
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        yield client


def test_first_administrator_receives_session_and_setup_closes(local_client):
    assert local_client.get("/api/auth/setup").json()["available"] is True
    created = local_client.post("/api/auth/setup", json=account("admin@example.com"))
    assert created.status_code == 201
    assert created.json()["user"]["role"] == "admin"
    assert PASSWORD not in created.text and "password_hash" not in created.text
    assert created.headers["cache-control"] == "no-store"
    headers = {"Authorization": "Bearer " + created.json()["access_token"]}
    assert local_client.get("/api/users", headers=headers).status_code == 200
    assert local_client.get("/api/auth/setup").json()["available"] is False
    assert local_client.post("/api/auth/setup", json=account("second@example.com")).status_code == 409
    # Changing the administrator's role cannot reopen a completed bootstrap.
    with SessionLocal() as db:
        user = db.scalar(select(User))
        user.role = "officer"
        db.commit()
    assert local_client.get("/api/auth/setup").json()["available"] is False


@pytest.mark.parametrize("setting,value", [("environment", "production"), ("local_admin_setup_enabled", False)])
def test_setup_disabled_by_configuration(local_client, monkeypatch, setting, value):
    monkeypatch.setattr(get_settings(), setting, value)
    assert local_client.get("/api/auth/setup").json()["available"] is False
    assert local_client.post("/api/auth/setup", json=account()).status_code == 403


@pytest.mark.parametrize("host,peer", [("http://127.0.0.1", "192.0.2.20"), ("http://example.com", "127.0.0.1")])
def test_setup_rejects_remote_peers_and_nonlocal_hosts(host, peer):
    with TestClient(app, base_url=host, client=(peer, 50000)) as client:
        # Client-supplied forwarding headers do not grant access.
        headers = {"X-Forwarded-For": "127.0.0.1", "X-Forwarded-Host": "localhost"}
        assert client.get("/api/auth/setup", headers=headers).json()["available"] is False
        assert client.post("/api/auth/setup", headers=headers, json=account()).status_code == 403


def test_existing_inactive_administrator_closes_setup(local_client):
    with SessionLocal() as db:
        user = create_user(db, RegisterRequest(**account()), "admin")
        user.is_active = False
        db.commit()
    assert local_client.get("/api/auth/setup").json()["available"] is False
    assert local_client.post("/api/auth/setup", json=account("new@example.com")).status_code == 409


def test_invalid_and_duplicate_attempts_do_not_consume_setup(local_client):
    for changes in ({"password": "short"}, {"phone": "invalid"}, {"role": "admin"}):
        response = local_client.post("/api/auth/setup", json={**account(), **changes})
        assert response.status_code == 422
        assert PASSWORD not in response.text and '"input"' not in response.text
    resident = local_client.post("/api/auth/register", json=account())
    assert resident.status_code == 201
    assert local_client.post("/api/auth/setup", json=account()).status_code == 409
    with SessionLocal() as db:
        assert db.get(AdministratorSetup, 1) is None
        assert db.scalar(select(User)).role == "resident"
    assert local_client.post("/api/auth/setup", json=account("new-admin@example.com")).status_code == 201


def test_concurrent_setup_creates_only_one_administrator(local_client):
    barrier = Barrier(2)

    def attempt(index):
        with SessionLocal() as db:
            assert not setup_complete(db)
            barrier.wait(timeout=5)
            try:
                create_first_administrator(db, RegisterRequest(**account(f"admin{index}@example.com")))
                return 201
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, (1, 2))) == [201, 409]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) == 1
        assert db.scalar(select(func.count()).select_from(AdministratorSetup)) == 1


def test_setup_does_not_change_resident_registration(local_client):
    assert local_client.post("/api/auth/setup", json=account("admin@example.com")).status_code == 201
    response = local_client.post("/api/auth/register", json=account())
    assert response.status_code == 201 and response.json()["user"]["role"] == "resident"
    assert local_client.post("/api/auth/register", json={**account("bad@example.com"), "role": "admin"}).status_code == 422
