"""Operator-phone station tracking (portable station position, migration 0010).

Administrators grant one named resident phone account a time-limited session for one
station. During that session only, the phone posts GPS fixes. Fixes are validated and
stored separately; registry coordinates, commissioning, configuration and eligibility are
never changed by tracking.
"""
from datetime import datetime, timedelta, timezone
from math import isfinite

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, utc_now
from app.services.accounts import current_user, require_admin
from app.services.station_security import audit, commit_security, lock_station
from app.tracking_models import (MAX_ACCURACY_M, MAX_FIX_AGE_SECONDS, MAX_FUTURE_SKEW_SECONDS, MAX_SESSION_MINUTES,
                                 MIN_INTERVAL_SECONDS, StationTrackedPosition, StationTrackingSession)

admin_router = APIRouter(prefix="/api/stations", tags=["station tracking"])
tracker_router = APIRouter(prefix="/api/station-tracking", tags=["station tracking"])


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def is_active(session: StationTrackingSession, now: datetime | None = None) -> bool:
    now = now or utc_now()
    return session.ended_at is None and _utc(session.expires_at) > now


def session_contract(session: StationTrackingSession, db: Session) -> dict:
    tracker = db.get(User, session.tracker_user_id)
    return dict(id=session.id, station_id=session.station_id, tracker_email=tracker.email if tracker else None,
                reason=session.reason, created_at=_utc(session.created_at), expires_at=_utc(session.expires_at),
                ended_at=_utc(session.ended_at), end_reason=session.end_reason, active=is_active(session))


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tracker_email: EmailStr
    duration_minutes: int = Field(default=120, ge=5, le=MAX_SESSION_MINUTES)
    reason: str = Field(min_length=3, max_length=500)


class SessionEnd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=500)


class PositionFix(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(gt=0)
    captured_at: AwareDatetime


def _end_active(db: Session, station_id: str, actor: User, reason: str, now: datetime):
    for row in db.scalars(select(StationTrackingSession).where(
            StationTrackingSession.station_id == station_id, StationTrackingSession.ended_at.is_(None))):
        if _utc(row.expires_at) > now:
            row.ended_at, row.ended_by, row.end_reason = now, actor.id, reason


@admin_router.post("/{station_id}/tracking-sessions", status_code=201)
def start_session(station_id: str, payload: SessionCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    station = lock_station(db, station_id)
    tracker = db.scalar(select(User).where(User.email == str(payload.tracker_email)))
    if tracker is None or not tracker.is_active or tracker.role != "resident":
        raise HTTPException(422, "Tracking requires an active resident phone account.")
    now = utc_now()
    _end_active(db, station_id, admin, "Superseded by a new tracking session", now)   # one active session per station
    session = StationTrackingSession(station_id=station_id, tracker_user_id=tracker.id, created_by=admin.id,
                                     reason=payload.reason.strip(), created_at=now,
                                     expires_at=now + timedelta(minutes=payload.duration_minutes))
    db.add(session)
    db.flush()
    audit(db, station, admin, "tracking_session_started", payload.reason, {
        "after": {"session_id": session.id, "tracker_user_id": str(tracker.id), "expires_at": session.expires_at.isoformat()}})
    commit_security(db)
    return session_contract(session, db)


@admin_router.get("/{station_id}/tracking-sessions")
def list_sessions(station_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    rows = db.scalars(select(StationTrackingSession).where(StationTrackingSession.station_id == station_id)
                      .order_by(StationTrackingSession.created_at.desc()).limit(50))
    return [session_contract(row, db) for row in rows]


@admin_router.post("/{station_id}/tracking-sessions/{session_id}/end")
def end_session(station_id: str, session_id: str, payload: SessionEnd, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    station = lock_station(db, station_id)
    session = db.get(StationTrackingSession, session_id)
    if session is None or session.station_id != station_id:
        raise HTTPException(404, "Tracking session not found")
    if session.ended_at is None:
        session.ended_at, session.ended_by, session.end_reason = utc_now(), admin.id, payload.reason
        audit(db, station, admin, "tracking_session_ended", payload.reason, {"after": {"session_id": session.id}})
        commit_security(db)
    return session_contract(session, db)


def _own_active(db: Session, session_id: str, user: User) -> StationTrackingSession:
    session = db.get(StationTrackingSession, session_id, populate_existing=True)
    if session is None or session.tracker_user_id != user.id:
        raise HTTPException(404, "Tracking session not found")
    if not is_active(session):
        raise HTTPException(409, "Tracking session is not active")
    return session


@tracker_router.get("/active")
def my_active_sessions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    now = utc_now()
    rows = db.scalars(select(StationTrackingSession).where(
        StationTrackingSession.tracker_user_id == user.id, StationTrackingSession.ended_at.is_(None)))
    from app.models import Station
    result = []
    for row in rows:
        if _utc(row.expires_at) > now:
            station = db.scalar(select(Station).where(Station.station_id == row.station_id))
            result.append(dict(id=row.id, station_id=row.station_id, station_name=station.station_name if station else row.station_id,
                               expires_at=_utc(row.expires_at), min_interval_seconds=MIN_INTERVAL_SECONDS,
                               max_accuracy_m=MAX_ACCURACY_M))
    return result


@tracker_router.post("/{session_id}/positions", status_code=201)
def report_position(session_id: str, fix: PositionFix, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = _own_active(db, session_id, user)
    now = utc_now()
    captured = _utc(fix.captured_at)
    if not (isfinite(fix.latitude) and isfinite(fix.longitude)):
        raise HTTPException(422, "Position must be finite")
    if fix.accuracy_m > MAX_ACCURACY_M:
        raise HTTPException(422, f"GPS accuracy {fix.accuracy_m:.0f} m is worse than {MAX_ACCURACY_M:.0f} m; fix rejected")
    if captured < now - timedelta(seconds=MAX_FIX_AGE_SECONDS):
        raise HTTPException(422, "GPS fix is too old; rejected")
    if captured > now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
        raise HTTPException(422, "GPS fix is in the future; rejected")
    last = db.scalar(select(StationTrackedPosition).where(StationTrackedPosition.session_id == session.id)
                     .order_by(StationTrackedPosition.received_at.desc()).limit(1))
    if last is not None and (now - _utc(last.received_at)).total_seconds() < MIN_INTERVAL_SECONDS:
        raise HTTPException(429, "Position updates are limited to one every 2 seconds", headers={"Retry-After": "2"})
    if last is not None and captured <= _utc(last.captured_at):
        raise HTTPException(409, "GPS fix is not newer than the last accepted fix")
    row = StationTrackedPosition(session_id=session.id, station_id=session.station_id, latitude=fix.latitude,
                                 longitude=fix.longitude, accuracy_m=fix.accuracy_m, captured_at=captured, received_at=now)
    db.add(row)
    db.commit()
    return dict(accepted=True, position_id=row.id, station_id=session.station_id, received_at=now)


@tracker_router.post("/{session_id}/stop")
def stop_own_session(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = _own_active(db, session_id, user)
    session.ended_at, session.ended_by, session.end_reason = utc_now(), user.id, "Stopped by tracker"
    db.commit()
    return dict(id=session.id, active=False)
