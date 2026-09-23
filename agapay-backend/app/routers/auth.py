from ipaddress import ip_address

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_schemas import LoginRequest, ProfileUpdate, RegisterRequest, SessionRead, SetupStatus, UserRead
from app.config import Settings, get_settings
from app.database import get_db
from app.models import User
from app.services.accounts import bearer, commit_account, create_user, current_user, issue_session, limiter, passwords, request_ip, revoke_session, revoke_sessions, token_digest, verify_password
from app.services.administrator_setup import create_first_administrator, setup_complete

router = APIRouter(prefix="/api/auth", tags=["accounts"])


def local_setup_access(request: Request, settings: Settings) -> bool:
    try:
        local_peer = request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:
        local_peer = False
    return settings.environment == "development" and settings.local_admin_setup_enabled and local_peer and request.url.hostname in ("localhost", "127.0.0.1", "::1")


@router.get("/setup", response_model=SetupStatus)
def setup_status(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not local_setup_access(request, settings):
        return SetupStatus(available=False, reason="Administrator registration is available only in local development.")
    if setup_complete(db):
        return SetupStatus(available=False, reason="Administrator setup is complete. Sign in or ask an administrator to create your staff account.")
    return SetupStatus(available=True, reason="Create the first administrator for this AGAPAY installation.")


@router.post("/setup", response_model=SessionRead, status_code=201)
def setup_administrator(payload: RegisterRequest, request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not local_setup_access(request, settings):
        raise HTTPException(403, "Administrator registration is available only in local development.")
    limiter.hit("setup:" + request_ip(request), 10, 3600)
    if setup_complete(db):
        raise HTTPException(409, "Administrator setup is complete. Sign in to manage accounts.")
    user = create_first_administrator(db, payload)
    return issue_session(db, user)


@router.post("/register", response_model=SessionRead, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    limiter.hit("register:" + request_ip(request), 20, 3600)
    user = create_user(db, payload)
    return issue_session(db, user)


@router.post("/login", response_model=SessionRead)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key = "login:" + str(payload.email)
    limiter.hit("login-ip:" + request_ip(request), 300)
    limiter.hit(key, 10)
    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if not verify_password(payload.password, user) or not user.is_active:
        raise HTTPException(401, "Email or password is incorrect.")
    if (payload.audience == "web" and user.role not in ("admin", "officer")) or (payload.audience == "mobile" and user.role != "resident"):
        raise HTTPException(403, "Use the resident mobile app for resident accounts, or the web command center for staff accounts.")
    limiter.clear(key)
    return issue_session(db, user)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserRead)
def update_profile(payload: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    changes = payload.model_dump(exclude_unset=True, exclude={"current_password", "password"})
    if payload.password or (payload.email is not None and payload.email != user.email):
        if not payload.current_password or not verify_password(payload.current_password, user):
            raise HTTPException(400, "Enter your current password to change your email or password.")
    for key, value in changes.items():
        setattr(user, key, value)
    if payload.password:
        user.password_hash = passwords.hash(payload.password)
        revoke_sessions(db, user.id)
    commit_account(db)
    db.refresh(user)
    return user


@router.post("/logout", status_code=204)
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if credentials and len(credentials.credentials) <= 256:
        revoke_session(db, token_digest(credentials.credentials))
        db.commit()
    return Response(status_code=204)
