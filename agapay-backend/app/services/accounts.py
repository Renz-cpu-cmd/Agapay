import hashlib
import secrets
import threading
import time
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.account_schemas import RegisterRequest, SessionRead, UserRead
from app.config import get_settings
from app.database import get_db
from app.models import AuthSession, User, utc_now

passwords = PasswordHash.recommended()
_dummy_hash = passwords.hash(secrets.token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(password: str, user: User | None) -> bool:
    return passwords.verify(password, user.password_hash if user else _dummy_hash) and user is not None


def create_user(db: Session, payload: RegisterRequest, role: str = "resident") -> User:
    user = User(**payload.model_dump(exclude={"password", "role"}), role=role, password_hash=passwords.hash(payload.password))
    db.add(user)
    commit_account(db)
    db.refresh(user)
    return user


def commit_account(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from exc


def revoke_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


def issue_session(db: Session, user: User) -> SessionRead:
    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(days=get_settings().session_days)
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= utc_now()))
    db.add(AuthSession(token_hash=token_digest(token), user_id=user.id, expires_at=expires_at))
    db.commit()
    return SessionRead(access_token=token, expires_at=expires_at, user=UserRead.model_validate(user))


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    error = HTTPException(401, "Your session has expired. Please sign in again.", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None or credentials.scheme.lower() != "bearer" or len(credentials.credentials) > 256:
        raise error
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(credentials.credentials), AuthSession.expires_at > utc_now()))
    user = db.get(User, session.user_id) if session else None
    if user is None or not user.is_active:
        raise error
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator access is required.")
    return user


class AuthLimiter:
    """Bounded per-process abuse protection; use a shared gateway limit for multiple workers."""
    def __init__(self):
        self.entries: dict[str, tuple[int, float]] = {}
        self.lock = threading.Lock()

    def hit(self, key: str, limit: int, window: int = 900):
        with self.lock:
            now = time.monotonic()
            self.entries = {k: v for k, v in self.entries.items() if v[1] > now}
            count, reset = self.entries.get(key, (0, now + window))
            if count >= limit or (key not in self.entries and len(self.entries) >= 10000):
                raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": str(max(1, int(reset - now)))})
            self.entries[key] = (count + 1, reset)

    def clear(self, key: str):
        with self.lock:
            self.entries.pop(key, None)


limiter = AuthLimiter()


def request_ip(request: Request) -> str:
    # Do not trust arbitrary client-supplied forwarding headers.
    return request.client.host if request.client else "unknown"
