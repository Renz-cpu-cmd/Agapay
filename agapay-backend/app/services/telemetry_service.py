from datetime import datetime, timezone

from sqlalchemy import desc, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Station, Telemetry
from app.schemas import TelemetryCreate
from app.services.alert_service import process_sensor_alert


class UnknownStationError(Exception):
    pass


class DuplicateTelemetryError(Exception):
    pass


def ingest_telemetry(db: Session, payload: TelemetryCreate) -> Telemetry:
    try:
        # Acquire the database write lock BEFORE reading an active episode.
        # SQLite serializes writers; PostgreSQL locks this station row. This
        # coordinates HTTP/MQTT workers without process-local Python locks.
        locked = db.execute(update(Station).where(
            Station.station_id == payload.station_id,
        ).values(last_ping=Station.last_ping))
        if locked.rowcount != 1:
            raise UnknownStationError(payload.station_id)
        station = db.scalar(select(Station).where(Station.station_id == payload.station_id))
        observed_at = datetime.now(timezone.utc)
        telemetry = Telemetry(
            station_id=payload.station_id, sequence_no=payload.sequence_no,
            water_depth_cm=payload.water_depth_cm, rainfall_mm=payload.rainfall_mm,
            sensor_quality=payload.sensor_quality, device_uptime_ms=payload.device_uptime_ms,
            recorded_at=observed_at,
        )
        station.last_ping = observed_at
        station.firmware_version = payload.firmware_version
        db.add(telemetry)
        db.flush()  # Enforce the existing station/sequence uniqueness first.
        process_sensor_alert(db, station, telemetry)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        duplicate = db.scalar(select(Telemetry.id).where(
            Telemetry.station_id == payload.station_id,
            Telemetry.sequence_no == payload.sequence_no,
        ))
        if duplicate is not None:
            raise DuplicateTelemetryError(
                f"Duplicate telemetry: {payload.station_id}/{payload.sequence_no}"
            ) from exc
        raise
    except Exception:
        db.rollback()
        raise
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
