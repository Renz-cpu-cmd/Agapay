from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Station


def seed_demo_station(db: Session) -> Station:
    station = db.scalar(
        select(Station).where(Station.station_id == "STATION_001")
    )
    if station is not None:
        return station

    station = Station(
        station_id="STATION_001",
        station_name="AGAPAY Demo Station 1",
        barangay="DEMO_ONLY",
        municipality="Urdaneta City",
        latitude=None,
        longitude=None,
        sensor_height_cm=120.0,
        threshold_advisory_cm=60.0,
        threshold_warning_cm=85.0,
        threshold_evacuate_cm=100.0,
        status="active",
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station
