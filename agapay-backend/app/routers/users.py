from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_schemas import AdminCreateRequest, AdminUpdateRequest, UserRead
from app.database import get_db
from app.models import User
from app.services.accounts import commit_account, create_user, passwords, require_admin, revoke_sessions

router = APIRouter(prefix="/api/users", tags=["user administration"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())))


@router.post("", response_model=UserRead, status_code=201)
def add_user(payload: AdminCreateRequest, db: Session = Depends(get_db)):
    return create_user(db, payload, payload.role)


@router.patch("/{user_id}", response_model=UserRead)
def edit_user(user_id: int, payload: AdminUpdateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Account not found.")
    if user.id == admin.id and (payload.is_active is False or (payload.role is not None and payload.role != "admin")):
        raise HTTPException(409, "You cannot deactivate or remove administrator access from your own account.")
    changes = payload.model_dump(exclude_unset=True, exclude={"password", "current_password"})
    revoke = bool(payload.password) or (payload.role is not None and payload.role != user.role) or payload.is_active is False
    for key, value in changes.items():
        setattr(user, key, value)
    if payload.password:
        user.password_hash = passwords.hash(payload.password)
    if revoke:
        revoke_sessions(db, user.id)
    commit_account(db)
    db.refresh(user)
    return user
