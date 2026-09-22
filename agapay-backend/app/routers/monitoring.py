from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import User
from app.monitoring_schemas import MonitoringSnapshot
from app.services.accounts import current_user
from app.services.monitoring_service import monitoring_snapshot


router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/stations", response_model=MonitoringSnapshot)
def station_snapshot(
    history_limit: int = Query(default=60, ge=2, le=500),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _user: User = Depends(current_user),
) -> MonitoringSnapshot:
    return monitoring_snapshot(
        db,
        stale_after_seconds=settings.telemetry_stale_after_seconds,
        history_limit=history_limit,
    )
