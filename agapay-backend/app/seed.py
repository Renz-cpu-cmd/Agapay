from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Station


def seed_demo_station(db: Session) -> Station:
    station = db.scalar(
        select(Station).where(Station.station_id == "STATION_001")
    )
    if station is not None:
        if station.barangay == "DEMO_ONLY" and station.latitude is None:
            station.station_name = "UCU Irrigation Canal Station"
            station.barangay = "San Vicente West"
            station.municipality = "Urdaneta City"
            station.latitude = 15.98165
            station.longitude = 120.560573
            db.commit()
            db.refresh(station)
        return station

    station = Station(
        station_id="STATION_001",
        station_name="UCU Irrigation Canal Station",
        barangay="San Vicente West",
        municipality="Urdaneta City",
        latitude=15.98165,
        longitude=120.560573,
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
