import hashlib
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SosRequest, User, utc_now
from app.services.accounts import current_user
from app.sos_schemas import SosCreate, SosLocationUpdate, SosPage, SosRead, SosTransition, Status

router = APIRouter(prefix="/api/sos", tags=["SOS (practice)"])


def visible(db: Session, user: User, sos_id: int):
    item = db.get(SosRequest, sos_id)
    if item is None or (user.role == "resident" and item.user_id != user.id):
        raise HTTPException(404, "SOS request not found.")
    return item


@router.post("", response_model=SosRead, status_code=201)
def create(payload: SosCreate, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "resident":
        raise HTTPException(403, "Resident access is required to submit an SOS.")
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
        raise HTTPException(409, "Location sharing has ended because this SOS is resolved.")
    age = utc_now() - payload.location_recorded_at
    if age > timedelta(minutes=2) or age < -timedelta(minutes=1):
        raise HTTPException(422, "Refresh your GPS location before sharing it.")

    if item.location_recorded_at is not None:
        previous = item.location_recorded_at
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        else:
            previous = previous.astimezone(timezone.utc)
        if payload.location_recorded_at < previous:
            raise HTTPException(409, "A newer location has already been recorded.")
        if payload.location_recorded_at == previous:
            same_fix = (
                item.latitude == payload.latitude
                and item.longitude == payload.longitude
                and item.accuracy_m == payload.accuracy_m
            )
            if same_fix:
                return item
            raise HTTPException(409, "A different location was already recorded at this time.")

    item.latitude = payload.latitude
    item.longitude = payload.longitude
    item.accuracy_m = payload.accuracy_m
    item.location_recorded_at = payload.location_recorded_at
    item.location_source = "gps"
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
    expected = "ACTIVE" if payload.status == "ACKNOWLEDGED" else "ACKNOWLEDGED"
    if item.status != expected:
        raise HTTPException(409, "SOS status has changed. Refresh the request; acknowledge before resolving.")
    fields = {"status": payload.status}
    if payload.status == "ACKNOWLEDGED":
        fields.update(acknowledged_by=user.id, acknowledged_by_name=user.name, acknowledged_at=utc_now())
    else:
        fields.update(resolved_by=user.id, resolved_by_name=user.name, resolved_at=utc_now(), resolution_note=payload.resolution_note)
    result = db.execute(update(SosRequest).where(SosRequest.id == sos_id, SosRequest.status == expected).values(**fields))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Another officer updated this request. Refresh to see its current status.")
    db.commit()
    db.refresh(item)
    return item
