from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alert_schemas import AlertPage, AlertRead, AlertStatus, AlertTransitionPage
from app.database import get_db
from app.models import Alert, AlertTransition, User
from app.monitoring_schemas import AlertTier
from app.services.accounts import current_user


def require_staff(user: User = Depends(current_user)) -> User:
    if user.role not in ("admin", "officer"):
        raise HTTPException(403, "Staff access is required to read sensor alert history.")
    return user


router = APIRouter(prefix="/api/alerts", tags=["sensor alerts"], dependencies=[Depends(require_staff)])


def alert_page(db: Session, station_id: str | None, status: AlertStatus | None,
               severity: AlertTier | None, limit: int, offset: int) -> AlertPage:
    conditions = []
    if station_id is not None:
        conditions.append(Alert.station_id == station_id)
    if status is not None:
        conditions.append(Alert.status == status)
    if severity is not None:
        conditions.append(Alert.current_severity == severity)
    total = db.scalar(select(func.count()).select_from(Alert).where(*conditions))
    items = db.scalars(select(Alert).where(*conditions)
        .order_by(Alert.triggered_at.desc(), Alert.id.desc()).offset(offset).limit(limit)).all()
    return AlertPage(items=items, total=total)


@router.get("", response_model=AlertPage)
def list_alerts(station_id: str | None = None, status: AlertStatus | None = None,
                severity: AlertTier | None = None, limit: int = Query(50, ge=1, le=100),
                offset: int = Query(0, ge=0), db: Session = Depends(get_db)) -> AlertPage:
    return alert_page(db, station_id, status, severity, limit, offset)


@router.get("/active", response_model=AlertPage)
def active_alerts(station_id: str | None = None, severity: AlertTier | None = None,
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db)) -> AlertPage:
    return alert_page(db, station_id, "ACTIVE", severity, limit, offset)


def require_alert(db: Session, alert_id: int) -> Alert:
    episode = db.get(Alert, alert_id)
    if episode is None:
        raise HTTPException(404, "Sensor alert not found.")
    return episode


@router.get("/{alert_id}", response_model=AlertRead)
def alert_detail(alert_id: int, db: Session = Depends(get_db)) -> Alert:
    return require_alert(db, alert_id)


@router.get("/{alert_id}/transitions", response_model=AlertTransitionPage)
def alert_transitions(alert_id: int, limit: int = Query(50, ge=1, le=100),
                      offset: int = Query(0, ge=0), db: Session = Depends(get_db)) -> AlertTransitionPage:
    require_alert(db, alert_id)
    condition = AlertTransition.alert_id == alert_id
    total = db.scalar(select(func.count()).select_from(AlertTransition).where(condition))
    items = db.scalars(select(AlertTransition).where(condition)
        .order_by(AlertTransition.id).offset(offset).limit(limit)).all()
    return AlertTransitionPage(items=items, total=total)
