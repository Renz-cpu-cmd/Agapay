from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NotificationDevice, User, utc_now
from app.notification_schemas import DeviceRegistration, NotificationDeviceRead
from app.services.accounts import bearer, current_user, lock_account, token_digest
from app.services.notification_service import device_is_eligible, disable_device

router = APIRouter(prefix="/api/notification-devices", tags=["notification devices"])


def resident(user: User = Depends(current_user)) -> User:
    if user.role != "resident":
        raise HTTPException(403, "Resident mobile access is required.")
    return user


@router.post("", response_model=NotificationDeviceRead)
def register_device(payload: DeviceRegistration, user: User = Depends(resident),
                    credentials: HTTPAuthorizationCredentials = Depends(bearer),
                    db: Session = Depends(get_db)):
    # Authentication may have succeeded before a concurrent logout/security
    # revocation acquired its lock. Recheck after waiting, before authorizing push.
    lock_account(db, user.id)
    db.refresh(user)
    current_user(credentials, db)
    if user.role != "resident":
        raise HTTPException(403, "Resident mobile access is required.")
    raw_token = payload.provider_token.get_secret_value()
    digest = token_digest(raw_token)
    session_hash = token_digest(credentials.credentials)
    installation = str(payload.installation_id)
    device = db.scalar(select(NotificationDevice).where(
        NotificationDevice.user_id == user.id, NotificationDevice.installation_id == installation))
    occupied = db.scalar(select(NotificationDevice).where(NotificationDevice.token_hash == digest))
    if occupied is not None and (device is None or occupied.id != device.id):
        if occupied.user_id == user.id and occupied.enabled:
            # A retried/reinstalled app with the same token reuses its one row.
            if device is not None:
                raise HTTPException(409, "Device registration conflicts with an existing registration.")
            device = occupied
            device.installation_id = installation
        elif not device_is_eligible(db, occupied):
            disable_device(occupied)
            db.flush()  # Release token uniqueness before creating another row.
        else:
            raise HTTPException(409, "Device registration conflicts with an existing registration.")
    if device is None:
        device = NotificationDevice(user_id=user.id, installation_id=installation, revision=1)
        db.add(device)
    elif device.token_hash != digest or device.session_hash != session_hash or not device.enabled:
        device.revision += 1
    device.platform = payload.platform
    device.provider = payload.provider
    device.provider_token = raw_token
    device.token_hash = digest
    device.session_hash = session_hash
    device.enabled = True
    device.last_seen_at = utc_now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Do not include DB exception parameters (which contain provider tokens).
        raise HTTPException(409, "Device registration changed concurrently. Retry registration.") from None
    return device


@router.delete("/{device_id}", status_code=204)
def remove_device(device_id: str, user: User = Depends(resident), db: Session = Depends(get_db)):
    device = db.scalar(select(NotificationDevice).where(
        NotificationDevice.id == device_id, NotificationDevice.user_id == user.id))
    if device is None:
        raise HTTPException(404, "Device registration not found.")
    disable_device(device)
    db.commit()
    return Response(status_code=204)
