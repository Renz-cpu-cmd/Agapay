from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Station, Telemetry
from app.schemas import TelemetryCreate, TelemetryRead
from app.services.telemetry_service import (
    DuplicateTelemetryError,
    UnknownStationError,
    ingest_telemetry,
    latest_telemetry,
    telemetry_history,
)


router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


def require_station(db: Session, station_id: str) -> None:
    station = db.scalar(select(Station.id).where(Station.station_id == station_id))
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")


@router.post("", response_model=TelemetryRead, status_code=status.HTTP_201_CREATED)
def create_telemetry(
    payload: TelemetryCreate, db: Session = Depends(get_db)
) -> Telemetry:
    try:
        return ingest_telemetry(db, payload)
    except UnknownStationError as exc:
        raise HTTPException(status_code=404, detail="Station not found") from exc
    except DuplicateTelemetryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{station_id}/latest", response_model=TelemetryRead)
def get_latest_telemetry(
    station_id: str, db: Session = Depends(get_db)
) -> Telemetry:
    require_station(db, station_id)
    telemetry = latest_telemetry(db, station_id)
    if telemetry is None:
        raise HTTPException(status_code=404, detail="No telemetry found")
    return telemetry


@router.get("/{station_id}", response_model=list[TelemetryRead])
def get_telemetry_history(
    station_id: str,
    limit: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[Telemetry]:
    require_station(db, station_id)
    return telemetry_history(db, station_id, limit)
