"""One-time administrator creation shared by the local screen and CLI."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.account_schemas import RegisterRequest
from app.models import AdministratorSetup, User
from app.services.accounts import passwords


def setup_complete(db: Session) -> bool:
    # Inactive administrators also close setup; this is not account recovery.
    return db.get(AdministratorSetup, 1) is not None or db.scalar(
        select(User.id).where(User.role == "admin").limit(1)
    ) is not None


def create_first_administrator(db: Session, payload: RegisterRequest) -> User:
    password_hash = passwords.hash(payload.password)
    claimed = False
    try:
        # A unique, persistent row serializes competing submissions across workers.
        # Claim and account are committed together; invalid attempts release the claim.
        db.add(AdministratorSetup(id=1))
        db.flush()
        claimed = True
        if db.scalar(select(User.id).where(User.role == "admin").limit(1)) is not None:
            db.rollback()
            raise HTTPException(409, "Administrator setup is complete. Sign in to manage accounts.")
        user = User(**payload.model_dump(exclude={"password"}), role="admin", password_hash=password_hash)
        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = "An account with this email already exists. Use a different email." if claimed else "Administrator setup is complete. Sign in to manage accounts."
        raise HTTPException(409, message) from exc
    db.refresh(user)
    return user
