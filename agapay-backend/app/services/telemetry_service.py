from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Station, Telemetry
from app.schemas import TelemetryCreate


class UnknownStationError(Exception):
    pass


class DuplicateTelemetryError(Exception):
    pass


def ingest_telemetry(db: Session, payload: TelemetryCreate) -> Telemetry:
    station = db.scalar(
        select(Station).where(Station.station_id == payload.station_id)
    )
    if station is None:
        raise UnknownStationError(payload.station_id)

    duplicate = db.scalar(
        select(Telemetry).where(
            Telemetry.station_id == payload.station_id,
            Telemetry.sequence_no == payload.sequence_no,
        )
    )
    if duplicate is not None:
        raise DuplicateTelemetryError(
            f"Duplicate telemetry: {payload.station_id}/{payload.sequence_no}"
        )

    telemetry = Telemetry(
        station_id=payload.station_id,
        sequence_no=payload.sequence_no,
        water_depth_cm=payload.water_depth_cm,
        rainfall_mm=payload.rainfall_mm,
        sensor_quality=payload.sensor_quality,
        device_uptime_ms=payload.device_uptime_ms,
    )
    station.last_ping = datetime.now(timezone.utc)
    station.firmware_version = payload.firmware_version

    db.add(telemetry)
    db.commit()
    db.refresh(telemetry)
    return telemetry


def latest_telemetry(db: Session, station_id: str) -> Telemetry | None:
    return db.scalar(
        select(Telemetry)
        .where(Telemetry.station_id == station_id)
        .order_by(desc(Telemetry.recorded_at), desc(Telemetry.id))
        .limit(1)
    )


def telemetry_history(
    db: Session, station_id: str, limit: int
) -> list[Telemetry]:
    return list(
        db.scalars(
            select(Telemetry)
            .where(Telemetry.station_id == station_id)
            .order_by(desc(Telemetry.recorded_at), desc(Telemetry.id))
            .limit(limit)
        )
    )
