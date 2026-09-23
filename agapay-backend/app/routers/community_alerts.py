from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alert_schemas import AlertStatus
from app.community_alert_schemas import (
    CommunityAlertDetail,
    CommunityAlertPage,
    CommunityAlertRead,
    CommunityAlertTransitionPage,
)
from app.database import get_db
from app.models import Alert, AlertTransition, Station
from app.services.accounts import current_user


# The existing active-account dependency admits residents, officers and admins.
# Operational /api/alerts keeps its own staff-only dependency unchanged.
router = APIRouter(
    prefix="/api/community-alerts", tags=["community alerts"],
    dependencies=[Depends(current_user)],
)


def community_alert(episode: Alert, station: Station) -> CommunityAlertRead:
    """Explicit allowlist: never serialize the operational model wholesale."""
    return CommunityAlertRead(
        id=episode.id, station_id=station.station_id,
        station_name=station.station_name, barangay=station.barangay,
        municipality=station.municipality, status=episode.status,
        severity=episode.current_severity if episode.status == "ACTIVE" else episode.highest_severity,
        source=episode.source, trigger_depth_cm=episode.trigger_depth_cm,
        latest_depth_cm=episode.latest_depth_cm, triggered_at=episode.triggered_at,
        last_transition_at=episode.last_transition_at, resolved_at=episode.resolved_at,
    )


def community_page(db: Session, station_id: str | None, status: AlertStatus | None,
                   limit: int, offset: int) -> CommunityAlertPage:
    conditions = [Alert.source == "sensor"]
    if station_id is not None:
        conditions.append(Alert.station_id == station_id)
    if status is not None:
        conditions.append(Alert.status == status)
    # Join registered station metadata only; profile geography and administrative
    # station status must not silently hide an existing sensor episode.
    join = Alert.station_id == Station.station_id
    total = db.scalar(select(func.count()).select_from(Alert).join(Station, join).where(*conditions))
    records = db.execute(select(Alert, Station).join(Station, join).where(*conditions)
                         .order_by(Alert.triggered_at.desc(), Alert.id.desc())
                         .offset(offset).limit(limit)).all()
    return CommunityAlertPage(items=[community_alert(episode, station) for episode, station in records], total=total)


@router.get("", response_model=CommunityAlertPage)
def list_community_alerts(station_id: str | None = None, status: AlertStatus | None = None,
                          limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                          db: Session = Depends(get_db)) -> CommunityAlertPage:
    return community_page(db, station_id, status, limit, offset)


@router.get("/active", response_model=CommunityAlertPage)
def active_community_alerts(station_id: str | None = None,
                            limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                            db: Session = Depends(get_db)) -> CommunityAlertPage:
    return community_page(db, station_id, "ACTIVE", limit, offset)


@router.get("/{alert_id}", response_model=CommunityAlertDetail)
def community_alert_detail(alert_id: int,
                            transition_limit: int = Query(50, ge=1, le=100),
                            transition_offset: int = Query(0, ge=0),
                            db: Session = Depends(get_db)) -> CommunityAlertDetail:
    record = db.execute(select(Alert, Station).join(Station, Alert.station_id == Station.station_id)
                        .where(Alert.id == alert_id, Alert.source == "sensor")).one_or_none()
    if record is None:
        raise HTTPException(404, "Community sensor alert not found.")
    condition = AlertTransition.alert_id == alert_id
    total = db.scalar(select(func.count()).select_from(AlertTransition).where(condition))
    # IDs follow the ingestion engine's serialized transition order, including
    # tied receive timestamps. They remain internal to this query.
    transitions = db.scalars(select(AlertTransition).where(condition)
                            .order_by(AlertTransition.id).offset(transition_offset)
                            .limit(transition_limit)).all()
    return CommunityAlertDetail(
        **community_alert(*record).model_dump(),
        transitions=CommunityAlertTransitionPage(items=transitions, total=total),
    )
