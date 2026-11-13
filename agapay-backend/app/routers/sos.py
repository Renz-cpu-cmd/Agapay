import hashlib
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SosRequest, User, utc_now
from app.services.accounts import current_user
from app.sos_response_models import SosDrillResponse
from app.services.sos_concurrency import claim, conflict
from app.sos_schemas import SosCreate, SosLocationUpdate, SosPage, SosRead, SosTransition, Status

router = APIRouter(prefix="/api/sos", tags=["SOS (practice)"])


def replay_fix(db, item, payload, user_id):
    """Serialize duplicate acknowledgement with resolution and newer fixes."""
    result = db.execute(update(SosRequest).where(
        SosRequest.id == item.id, SosRequest.user_id == user_id,
        SosRequest.status != 'RESOLVED', SosRequest.location_recorded_at == payload.location_recorded_at,
        SosRequest.latitude == payload.latitude, SosRequest.longitude == payload.longitude,
        SosRequest.accuracy_m == payload.accuracy_m,
    ).values(version=SosRequest.version).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    db.refresh(item)
    return True


def visible(db: Session, user: User, sos_id: int):
    item = db.get(SosRequest, sos_id)
    if item is None or (user.role == "resident" and item.user_id != user.id):
        raise HTTPException(404, "SOS request not found.")
    return item


@router.post("", response_model=SosRead, status_code=201)
def create(payload: SosCreate, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "resident":
        raise HTTPException(403, "Resident access is required to submit an SOS.")
    from app.services.accounts import lock_account
    lock_account(db, user.id); db.refresh(user)
    if not user.is_active or user.role != 'resident':
        raise HTTPException(403, 'Resident account is no longer authorized')
    digest = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    lookup = select(SosRequest).where(SosRequest.user_id == user.id, SosRequest.request_id == str(payload.request_id))

    def replay(item):
        if item.payload_hash != digest:
            raise HTTPException(409, "This request reference was already used with different details.")
        response.status_code = 200
        return item

    existing = db.scalar(lookup)
    if existing:
        return replay(existing)
    if payload.location_recorded_at is not None:
        age = utc_now() - payload.location_recorded_at
        if age > timedelta(minutes=10) or age < -timedelta(minutes=1):
            raise HTTPException(422, "Refresh your GPS location before sending, or enter the location manually.")
    data = payload.model_dump(exclude={"request_id"})
    item = SosRequest(**data, request_id=str(payload.request_id), payload_hash=digest,
                      user_id=user.id, resident_name=user.name, phone=user.phone, barangay=user.barangay,
                      practice=True)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(lookup)
        if existing:
            return replay(existing)
        raise
    db.refresh(item)
    return item


@router.get("", response_model=SosPage)
def list_requests(status: Status | None = None, limit: int = Query(50, ge=1, le=100),
                  offset: int = Query(0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    scope = [SosRequest.user_id == user.id] if user.role == "resident" else []
    counts = {s: 0 for s in ("ACTIVE", "ACKNOWLEDGED", "RESOLVED")}
    counts.update(dict(db.execute(select(SosRequest.status, func.count()).where(*scope).group_by(SosRequest.status)).all()))
    conditions = scope + ([SosRequest.status == status] if status else [])
    total = sum(counts.values()) if status is None else counts[status]
    items = db.scalars(select(SosRequest).where(*conditions).order_by(SosRequest.id.desc()).offset(offset).limit(limit)).all()
    return SosPage(items=items, total=total, counts=counts)


@router.post('/receipt')
def receipt(payload:SosCreate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    """Read-only exact-payload receipt lookup; never creates or re-sends an SOS."""
    if user.role!='resident':raise HTTPException(403,'Resident access required')
    item=db.scalar(select(SosRequest).where(SosRequest.user_id==user.id,SosRequest.request_id==str(payload.request_id)))
    if item is None:return {'receipt':'unseen','item':None}
    if item.payload_hash!=hashlib.sha256(payload.model_dump_json().encode()).hexdigest():
        return {'receipt':'conflict','item':None,'message':'Reference exists with different submitted details. Refresh and manually review; do not overwrite.'}
    return {'receipt':'received','item':SosRead.model_validate(item)}


@router.get("/{sos_id}", response_model=SosRead)
def get_request(sos_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return visible(db, user, sos_id)


@router.patch("/{sos_id}/location", response_model=SosRead)
def update_location(sos_id: int, payload: SosLocationUpdate,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Replace an open request's last known fix with a newer owner-supplied fix."""
    item = visible(db, user, sos_id)
    if user.role != "resident":
        raise HTTPException(403, "Only the resident who submitted this SOS can share its location.")
    if item.status == "RESOLVED":
        conflict(db, item, "Location sharing has ended because this SOS is resolved. Refresh the request.")

    if item.location_recorded_at is not None:
        previous = item.location_recorded_at
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        else:
            previous = previous.astimezone(timezone.utc)
        if payload.location_recorded_at < previous:
            conflict(db, item, "A newer location has already been recorded. Refresh the request.")
        if payload.location_recorded_at == previous:
            same_fix = (
                item.latitude == payload.latitude
                and item.longitude == payload.longitude
                and item.accuracy_m == payload.accuracy_m
            )
            if same_fix:
                if not replay_fix(db, item, payload, user.id):
                    conflict(db, item)
                return item
            conflict(db, item, "A different location was already recorded at this time. Refresh the request.")
    age = utc_now() - payload.location_recorded_at
    if age > timedelta(minutes=2) or age < -timedelta(minutes=1):
        raise HTTPException(422, "Refresh your GPS location before sharing it.")
    try:
        claim(db, item, payload.expected_version, conditions=(
            SosRequest.user_id == user.id, SosRequest.status != "RESOLVED",
            or_(SosRequest.location_recorded_at.is_(None), SosRequest.location_recorded_at < payload.location_recorded_at),
        ), fields=dict(latitude=payload.latitude, longitude=payload.longitude, accuracy_m=payload.accuracy_m,
                       location_recorded_at=payload.location_recorded_at, location_source='gps'))
    except HTTPException as exc:
        if exc.status_code == 409 and replay_fix(db, item, payload, user.id):
            return item
        raise
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{sos_id}", response_model=SosRead)
def transition(sos_id: int, payload: SosTransition, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in ("admin", "officer"):
        raise HTTPException(403, "Staff access is required to update SOS status.")
    item = visible(db, user, sos_id)
    if item.status == payload.status:
        return item  # Retrying never rewrites the original officer or timestamp.
    if payload.status == 'RESOLVED' and db.get(SosDrillResponse, item.id):
        conflict(db, item, 'This request has a response drill. Record closure with a reason and evidence in its drill workflow.')
    expected = "ACTIVE" if payload.status == "ACKNOWLEDGED" else "ACKNOWLEDGED"
    if item.status != expected:
        conflict(db, item, "SOS status has changed. Refresh the request; acknowledge before resolving.")
    fields = {"status": payload.status}
    if payload.status == "ACKNOWLEDGED":
        fields.update(acknowledged_by=user.id, acknowledged_by_name=user.name, acknowledged_at=utc_now())
    else:
        fields.update(resolved_by=user.id, resolved_by_name=user.name, resolved_at=utc_now(), resolution_note=payload.resolution_note)
    claim(db, item, payload.expected_version, conditions=(SosRequest.status == expected,), fields=fields)
    db.commit()
    db.refresh(item)
    return item
