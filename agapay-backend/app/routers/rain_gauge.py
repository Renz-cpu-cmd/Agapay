from pathlib import Path
from datetime import datetime
import sqlite3
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.config import Settings,get_settings
from app.database import get_db
from app.models import Station,User
from app.schemas import STATION_ID_PATTERN
from app.services.accounts import current_user
from app.services.rain_gauge_service import RainGaugeStore

router=APIRouter(prefix="/api/rain-gauge",tags=["rain-gauge demonstration"])


@router.get("/{station_id}")
def snapshot(station_id: str,source: str=Query("physical_rain_gauge",pattern="^(physical_rain_gauge|simulated_rain_gauge)$"),
             since_id: int=Query(0,ge=0),anchor_at: datetime|None=None,db: Session=Depends(get_db),settings: Settings=Depends(get_settings),user: User=Depends(current_user)):
    import re
    if user.role not in ("admin","officer"):
        raise HTTPException(403,"Staff access required")
    if not re.fullmatch(STATION_ID_PATTERN,station_id) or db.query(Station).filter(Station.station_id==station_id).first() is None:
        raise HTTPException(404,"Unknown station")
    if not settings.rain_gauge_enabled:
        raise HTTPException(503,"Rain-gauge event feed is disabled")
    if source=="simulated_rain_gauge" and not settings.rain_gauge_allow_simulator:
        raise HTTPException(403,"Test simulator is disabled")
    if anchor_at is not None and anchor_at.tzinfo is None:
        raise HTTPException(422,"Initialization timestamp must include timezone")
    try:
        result=RainGaugeStore(Path(settings.rain_gauge_store_path),read_only=True,raw_retention_days=settings.rain_raw_retention_days).snapshot(station_id,source,since_id=since_id,anchor_at=anchor_at)
    except (sqlite3.Error,OSError,ValueError):
        raise HTTPException(503,'Independent rain journal unavailable; inspect operations diagnostics') from None
    from app.device_config import current_configuration
    configuration=current_configuration(db,station_id)
    if configuration and result.get('calibration_version')!=configuration.config_hash:
        result.update(connected=False,status="configuration_mismatch",ml_ready=False)
    return result
