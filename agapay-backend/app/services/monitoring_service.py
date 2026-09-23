from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Station, Telemetry
from app.monitoring_schemas import MonitoringSample, MonitoringSnapshot, MonitoringStation
from app.services.alert_classifier import classify_depth


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _trend(valid: list[Telemetry]) -> str:
    if len(valid) < 2:
        return "stable"
    delta = valid[0].water_depth_cm - valid[1].water_depth_cm
    if delta >= 4:
        return "rising_rapidly"
    if delta >= 0.5:
        return "rising"
    if delta <= -0.5:
        return "falling"
    return "stable"


def _connection(station: Station, has_data: bool, stale: bool) -> str:
    if station.status in ("inactive", "maintenance"):
        return station.status
    if not has_data:
        return "no_data"
    return "offline" if stale else "online"


def monitoring_snapshot(
    db: Session,
    *,
    stale_after_seconds: int,
    history_limit: int,
    now: datetime | None = None,
) -> MonitoringSnapshot:
    checked_at = _utc(now) or datetime.now(timezone.utc)
    result: list[MonitoringStation] = []

    for station in db.scalars(select(Station).order_by(Station.station_id)):
        readings = list(
            db.scalars(
                select(Telemetry)
                .where(Telemetry.station_id == station.station_id)
                .order_by(desc(Telemetry.recorded_at), desc(Telemetry.id))
                .limit(history_limit)
            )
        )
        latest = readings[0] if readings else None
        valid = [
            reading
            for reading in readings
            if reading.sensor_quality == "valid" and reading.water_depth_cm is not None
        ]
        last_valid = valid[0] if valid else None
        last_ping = _utc(station.last_ping)
        age_seconds = (
            max(0, int((checked_at - last_ping).total_seconds()))
            if last_ping is not None
            else None
        )
        stale = age_seconds is not None and age_seconds > stale_after_seconds
        connection = _connection(station, latest is not None, stale)
        source = (
            "simulator"
            if station.firmware_version and "simulator" in station.firmware_version.lower()
            else "device"
            if latest is not None
            else "none"
        )
        history = [
            MonitoringSample(
                sequence_no=reading.sequence_no,
                water_depth_cm=reading.water_depth_cm,
                rainfall_mm=reading.rainfall_mm,
                sensor_quality=reading.sensor_quality,
                device_uptime_ms=reading.device_uptime_ms,
                recorded_at=reading.recorded_at,
            )
            for reading in reversed(readings)
        ]
        result.append(
            MonitoringStation(
                station_id=station.station_id,
                station_name=station.station_name,
                barangay=station.barangay,
                municipality=station.municipality,
                latitude=station.latitude,
                longitude=station.longitude,
                administrative_status=station.status,
                connection_status=connection,
                is_online=connection == "online",
                is_stale=connection == "offline",
                age_seconds=age_seconds,
                alert_tier=classify_depth(
                    station,
                    last_valid.water_depth_cm if last_valid is not None else None,
                ),
                trend=_trend(valid),
                current_depth_cm=(
                    last_valid.water_depth_cm if last_valid is not None else None
                ),
                latest_depth_cm=(latest.water_depth_cm if latest is not None else None),
                latest_rainfall_mm=(latest.rainfall_mm if latest is not None else None),
                sensor_quality=(latest.sensor_quality if latest is not None else None),
                last_ping=last_ping,
                observed_at=_utc(latest.recorded_at) if latest is not None else None,
                firmware_version=station.firmware_version,
                source=source,
                threshold_advisory_cm=station.threshold_advisory_cm,
                threshold_warning_cm=station.threshold_warning_cm,
                threshold_evacuate_cm=station.threshold_evacuate_cm,
                history=history,
            )
        )

    return MonitoringSnapshot(
        checked_at=checked_at,
        stale_after_seconds=stale_after_seconds,
        stations=result,
    )
