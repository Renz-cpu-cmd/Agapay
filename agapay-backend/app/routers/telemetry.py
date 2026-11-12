from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import Settings, get_settings
from app.models import Station, Telemetry
from app.schemas import TelemetryCreate, TelemetryRead
from app.services.station_security import prepare_ingress
from app.services.telemetry_service import (
    ConflictingTelemetryError,
    DuplicateTelemetryError,
    UnknownStationError,
    ingest_telemetry,
    latest_telemetry,
    telemetry_history,
    telemetry_contracts,
)


router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])
station_bearer = HTTPBearer(auto_error=False, scheme_name="StationIngestToken")


def require_station(db: Session, station_id: str) -> None:
    station = db.scalar(select(Station.id).where(Station.station_id == station_id))
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")


@router.post("", response_model=TelemetryRead, status_code=status.HTTP_201_CREATED)
def create_telemetry(
    payload: TelemetryCreate, request: Request, db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(station_bearer),
    settings: Settings = Depends(get_settings),
    delivery_mode: str = Query(default="live", pattern="^(live|backfill)$"),
) -> Telemetry:
    try:
        if settings.environment != "development" and request.url.scheme != "https":
            raise HTTPException(400, "Station ingestion requires HTTPS outside development.")
        token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else ""
        credential = prepare_ingress(db, token, payload.station_id, "http", "telemetry", settings)
        row = ingest_telemetry(db, payload, credential_id=credential.id, transport="http", historical=delivery_mode=="backfill")
        return telemetry_contracts(db, [row])[0]
    except UnknownStationError as exc:
        raise HTTPException(status_code=404, detail="Station not found") from exc
    except ConflictingTelemetryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DuplicateTelemetryError as exc:
        if delivery_mode == "backfill":
            from app.services.depth_ack import acknowledged_duplicate
            row = acknowledged_duplicate(db, payload)
            return telemetry_contracts(db, [row])[0]
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{station_id}/latest", response_model=TelemetryRead)
def get_latest_telemetry(
    station_id: str, db: Session = Depends(get_db)
) -> Telemetry:
    require_station(db, station_id)
    telemetry = latest_telemetry(db, station_id)
    if telemetry is None:
        raise HTTPException(status_code=404, detail="No telemetry found")
    return telemetry_contracts(db, [telemetry])[0]


@router.get("/{station_id}", response_model=list[TelemetryRead])
def get_telemetry_history(
    station_id: str,
    limit: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[Telemetry]:
    require_station(db, station_id)
    return telemetry_contracts(db, telemetry_history(db, station_id, limit))
