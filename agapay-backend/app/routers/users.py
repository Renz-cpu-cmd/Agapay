from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_schemas import AdminCreateRequest, AdminUpdateRequest, UserRead
from app.database import get_db
from app.config import get_settings
from app.models import User
from app.services.accounts import commit_account, create_user, passwords, require_admin, revoke_sessions, lock_account, current_user, bearer

router = APIRouter(prefix="/api/users", tags=["user administration"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())))


@router.post("", response_model=UserRead, status_code=201)
def add_user(payload: AdminCreateRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin),
             credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    lock_account(db,admin.id);admin=current_user(credentials,db)
    if admin.role!='admin':raise HTTPException(403,'Administrator access required')
    if payload.role in ('admin','officer') and get_settings().environment=='production':
        raise HTTPException(409,'Production staff accounts require verified email invitation acceptance')
    return create_user(db, payload, payload.role, actor=admin, reason=payload.reason)


@router.patch("/{user_id}", response_model=UserRead)
def edit_user(user_id: int, payload: AdminUpdateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db),
              credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    for identity in sorted({admin.id,user_id}):lock_account(db,identity)
    admin=current_user(credentials,db)
    if admin.role!='admin':raise HTTPException(403,'Administrator access required')
    user = db.get(User, user_id,populate_existing=True)
    if user is None:
        raise HTTPException(404, "Account not found.")
    from app.services.identity_security import expected_version
    from app.services.mutation_audit import record,snapshot
    expected_version(user,payload.expected_version)
    before=snapshot(user)
    if user.id == admin.id and (payload.is_active is False or (payload.role is not None and payload.role != "admin")):
        raise HTTPException(409, "You cannot deactivate or remove administrator access from your own account.")
    changes = payload.model_dump(exclude_unset=True, exclude={"password", "current_password", "expected_version", "reason"})
    revoke = bool(payload.password) or (payload.role is not None and payload.role != user.role) or payload.is_active is False
    if payload.email is not None and payload.email!=user.email:user.email_verified_at=None
    for key, value in changes.items():
        setattr(user, key, value)
    if payload.password:
        user.password_hash = passwords.hash(payload.password)
    if revoke:
        revoke_sessions(db, user.id)
    user.version+=1
    record(db,admin,"account",user.id,"account_admin_updated",payload.reason,before,{**snapshot(user),"password_changed":bool(payload.password),"credentials_revoked":revoke})
    commit_account(db)
    db.refresh(user)
    return user
