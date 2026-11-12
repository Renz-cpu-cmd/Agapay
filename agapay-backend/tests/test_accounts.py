from datetime import timedelta

import pytest
from sqlalchemy import select

from app.account_schemas import RegisterRequest
from app.database import SessionLocal
from app.models import AdministratorSetup, AuthSession, SosRequest, User, utc_now
from app.services.accounts import create_user, limiter, token_digest


PASSWORD = "Account-test-password-2026"


def account(email="resident@example.com"):
    return dict(name="Test Resident", email=email, phone="+639123456789", barangay="San Vicente", password=PASSWORD)


@pytest.fixture(autouse=True)
def reset_accounts(clean_station_security):
    with SessionLocal() as db:
        db.query(AdministratorSetup).delete()
        db.query(SosRequest).delete()
        db.query(AuthSession).delete()
        db.query(User).delete()
        db.commit()
    limiter.reset()


def versioned(client, access, changes, user_id=None):
    if user_id is None:
        current=client.get('/api/auth/me',headers=access).json()
    else:
        with SessionLocal() as db:current={'version':db.get(User,user_id).version}
    return {'expected_version':current['version'],**({'reason':'Synthetic account administration review'} if user_id is not None else {}),**changes}


def sign_in(client, email, audience="mobile", password=PASSWORD):
    return client.post("/api/auth/login", json=dict(email=email, password=password, audience=audience))


def headers(response):
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def staff(client, role="admin"):
    with SessionLocal() as db:
        create_user(db, RegisterRequest(**account(role + "@example.com")), role)
    return headers(sign_in(client, role + "@example.com", "web"))


def test_mobile_signin_is_resident_only_and_staff_remains_on_web(client):
    client.post('/api/auth/register', json=account())
    assert sign_in(client, account()['email'], 'mobile').status_code == 200
    assert sign_in(client, account()['email'], 'web').status_code == 403
    assert sign_in(client, account()['email'], 'mobile_staff').status_code == 422
    for role in ('admin', 'officer'):
        staff(client, role)
        assert sign_in(client, role + '@example.com', 'mobile').status_code == 403
        assert sign_in(client, role + '@example.com', 'mobile_staff').status_code == 422
        assert sign_in(client, role + '@example.com', 'web').status_code == 200


def test_registration_normalization_hashing_and_no_role_injection(client):
    payload = account("  RESIDENT@EXAMPLE.COM ")
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "resident"
    assert response.json()["user"]["email"] == "resident@example.com"
    assert "password" not in response.text
    assert response.headers["cache-control"] == "no-store"
    with SessionLocal() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2")
        assert PASSWORD not in user.password_hash
        session = db.scalar(select(AuthSession))
        assert session.token_hash == token_digest(response.json()["access_token"])
        assert session.token_hash != response.json()["access_token"]
    assert client.post("/api/auth/register", json=account()).status_code == 409
    assert client.post("/api/auth/register", json={**account("other@example.com"), "role": "admin"}).status_code == 422


def test_invalid_inputs_do_not_echo_password(client):
    for changes in ({"password": "short"}, {"phone": "bad"}, {"name": " "}, {"email": "invalid"}):
        response = client.post("/api/auth/register", json={**account(), **changes})
        assert response.status_code == 422
        assert PASSWORD not in response.text
        assert '"input"' not in response.text


def test_login_roles_unknown_credentials_and_logout(client):
    token = headers(client.post("/api/auth/register", json=account()))
    assert sign_in(client, "resident@example.com", password="incorrect").status_code == 401
    assert sign_in(client, "missing@example.com").status_code == 401
    assert sign_in(client, "resident@example.com", "web").status_code == 403
    assert client.get("/api/users", headers=token).status_code == 403
    assert client.get("/api/users").status_code == 401
    assert client.patch("/api/auth/me", headers=token, json=versioned(client,token,{"role": "admin"})).status_code == 422
    assert client.get("/api/auth/me", headers=token).status_code == 200
    assert client.post("/api/auth/logout", headers=token).status_code == 204
    assert client.get("/api/auth/me", headers=token).status_code == 401
    assert client.post("/api/auth/logout", headers=token).status_code == 204


def test_profile_persists_and_email_password_changes_require_password(client):
    token = headers(client.post("/api/auth/register", json=account()))
    updated = client.patch("/api/auth/me", headers=token, json=versioned(client,token,{"name": "Updated Resident", "barangay": "Catablan", "phone": "09123456780"}))
    assert updated.status_code == 200
    assert client.get("/api/auth/me", headers=token).json()["barangay"] == "Catablan"
    assert client.patch("/api/auth/me", headers=token, json=versioned(client,token,{"email": "new@example.com"})).status_code == 400
    assert client.patch("/api/auth/me", headers=token, json=versioned(client,token,{"name": None})).status_code == 422
    assert client.patch("/api/auth/me", headers=token, json=versioned(client,token,{"email": "new@example.com", "current_password": PASSWORD})).status_code == 200
    second = headers(sign_in(client, "new@example.com"))
    new_password = PASSWORD + "-changed"
    assert client.patch("/api/auth/me", headers=token, json=versioned(client,token,{"password": new_password, "current_password": PASSWORD})).status_code == 200
    assert client.get("/api/auth/me", headers=second).status_code == 401
    assert client.get("/api/auth/me", headers=token).status_code == 401
    assert sign_in(client, "new@example.com").status_code == 401
    assert sign_in(client, "new@example.com", password=new_password).status_code == 200


def test_expired_invalid_and_disabled_sessions(client):
    response = client.post("/api/auth/register", json=account())
    token = headers(response)
    with SessionLocal() as db:
        session = db.scalar(select(AuthSession))
        session.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/auth/me", headers=token).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer made-up"}).status_code == 401
    fresh = headers(sign_in(client, "resident@example.com"))
    with SessionLocal() as db:
        user = db.scalar(select(User))
        user.is_active = False
        db.commit()
    assert client.get("/api/auth/me", headers=fresh).status_code == 401
    assert sign_in(client, "resident@example.com").status_code == 401


def test_admin_management_revokes_access_and_prevents_self_lockout(client):
    admin = staff(client)
    me = client.get("/api/auth/me", headers=admin).json()
    response = client.post("/api/users", headers=admin, json={"reason":"Synthetic staff provisioning test",**account("officer@example.com"), "role": "officer"})
    assert response.status_code == 201
    user_id = response.json()["id"]
    officer = headers(sign_in(client, "officer@example.com", "web"))
    assert sign_in(client, "officer@example.com", "mobile").status_code == 403
    assert client.get("/api/users", headers=officer).status_code == 403
    assert client.post("/api/users", headers=officer, json={"reason":"Synthetic staff provisioning test",**account("bad@example.com"), "role": "admin"}).status_code == 403
    assert client.patch(f"/api/users/{user_id}", headers=officer, json=versioned(client,officer,{"role": "admin"},user_id)).status_code == 403
    assert client.patch(f"/api/users/{me['id']}", headers=admin, json=versioned(client,admin,{"is_active": False},me['id'])).status_code == 409
    assert client.patch(f"/api/users/{me['id']}", headers=admin, json=versioned(client,admin,{"role": "resident"},me['id'])).status_code == 409
    assert client.patch(f"/api/users/{user_id}", headers=admin, json=versioned(client,admin,{"role": "resident"},user_id)).status_code == 200
    assert client.get("/api/auth/me", headers=officer).status_code == 401
    resident = headers(sign_in(client, "officer@example.com"))
    assert client.patch(f"/api/users/{user_id}", headers=admin, json=versioned(client,admin,{"is_active": False},user_id)).status_code == 200
    assert client.get("/api/auth/me", headers=resident).status_code == 401
    assert client.patch(f"/api/users/{user_id}", headers=admin, json=versioned(client,admin,{"is_active": True},user_id)).status_code == 200
    assert sign_in(client, "officer@example.com").status_code == 200
    assert client.patch(f"/api/users/{user_id}", headers=admin, json=versioned(client,admin,{"email": me['email']},user_id)).status_code == 409


def test_login_throttling(client):
    for _ in range(10):
        assert sign_in(client, "nobody@example.com").status_code == 401
    response = sign_in(client, "nobody@example.com")
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
