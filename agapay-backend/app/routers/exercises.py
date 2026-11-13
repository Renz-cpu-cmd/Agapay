from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import Settings, get_settings
from app.database import get_db
from app.schemas import TelemetryCreate, TelemetryRead
from app.routers.telemetry import station_bearer, require_station
from app.services.station_security import prepare_ingress
from app.services.telemetry_service import DuplicateTelemetryError
from app.services.exercise_telemetry import ingest_exercise, exercise_read, exercise_history

router = APIRouter(prefix="/api/exercises/telemetry", tags=["exercise telemetry (no operational effects)"])


@router.post("", response_model=TelemetryRead, status_code=201)
def create(payload: TelemetryCreate, request: Request, db: Session = Depends(get_db),
           credentials: HTTPAuthorizationCredentials | None = Depends(station_bearer),
           settings: Settings = Depends(get_settings)):
    if settings.environment != "development" and request.url.scheme != "https":
        raise HTTPException(400, "Station ingestion requires HTTPS outside development.")
    token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else ""
    credential = prepare_ingress(db, token, payload.station_id, "http", "telemetry", settings)
    try:
        return exercise_read(ingest_exercise(db, payload, credential_id=credential.id, transport="http"))
    except DuplicateTelemetryError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/{station_id}/latest", response_model=TelemetryRead)
def latest(station_id: str, db: Session = Depends(get_db)):
    require_station(db, station_id)
    rows = exercise_history(db, station_id, 1)
    if not rows:
        raise HTTPException(404, "No exercise telemetry found")
    return exercise_read(rows[0])


@router.get("/{station_id}", response_model=list[TelemetryRead])
def history(station_id: str, limit: int = Query(20, ge=1, le=500), db: Session = Depends(get_db)):
    require_station(db, station_id)
    return [exercise_read(row) for row in exercise_history(db, station_id, limit)]
