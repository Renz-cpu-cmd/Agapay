from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Station
from app.schemas import StationCreate, StationRead


router = APIRouter(prefix="/api/stations", tags=["stations"])


@router.get("", response_model=list[StationRead])
def list_stations(db: Session = Depends(get_db)) -> list[Station]:
    return list(db.scalars(select(Station).order_by(Station.station_id)))


@router.get("/{station_id}", response_model=StationRead)
def get_station(station_id: str, db: Session = Depends(get_db)) -> Station:
    station = db.scalar(select(Station).where(Station.station_id == station_id))
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    return station


@router.post("", response_model=StationRead, status_code=status.HTTP_201_CREATED)
def create_station(
    payload: StationCreate, db: Session = Depends(get_db)
) -> Station:
    existing = db.scalar(
        select(Station).where(Station.station_id == payload.station_id)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Station already exists")

    station = Station(**payload.model_dump(), status="active")
    db.add(station)
    db.commit()
    db.refresh(station)
    return station
