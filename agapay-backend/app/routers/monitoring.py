from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime
from pydantic import AwareDatetime
from typing import Literal
from app.services.history_report import build_history_report
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
    station_id: list[str] | None = Query(None,max_length=20),
) -> MonitoringSnapshot:
    from app.services.read_models import snapshot
    return snapshot(db,settings,history_limit=history_limit,station_ids=station_id)


@router.get("/history")
def station_history(start_at: AwareDatetime | None = None, end_at: AwareDatetime | None = None,
    station_id: list[str] | None = Query(None, max_length=20), event_id: int | None = Query(None, ge=1),
    timezone: Literal["UTC", "Asia/Manila"] = "Asia/Manila", bucket_seconds: int = Query(60, ge=30, le=3600),
    db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role not in ("admin", "officer"):
        raise HTTPException(403, "Staff report access required")
    return build_history_report(db, start_at=start_at, end_at=end_at, station_ids=station_id,
        event_id=event_id, timezone_name=timezone, bucket_seconds=bucket_seconds)
