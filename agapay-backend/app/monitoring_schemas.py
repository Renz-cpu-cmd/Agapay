from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


AlertTier = Literal["NORMAL", "ADVISORY", "WARNING", "EVACUATE"]
ConnectionState = Literal["online", "offline", "no_data", "inactive", "maintenance"]
TrendState = Literal["rising_rapidly", "rising", "stable", "falling"]
DataSource = Literal["simulator", "device", "none"]


class MonitoringSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_no: int
    water_depth_cm: float | None
    rainfall_mm: float
    sensor_quality: Literal["valid", "invalid"]
    device_uptime_ms: int
    recorded_at: datetime

    @field_validator("recorded_at", mode="after")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class MonitoringStation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: str
    station_name: str
    barangay: str | None
    municipality: str | None
    latitude: float | None
    longitude: float | None
    administrative_status: Literal["active", "inactive", "maintenance"]
    connection_status: ConnectionState
    is_online: bool
    is_stale: bool
    age_seconds: int | None
    alert_tier: AlertTier | None
    trend: TrendState
    current_depth_cm: float | None
    latest_depth_cm: float | None
    latest_rainfall_mm: float | None
    sensor_quality: Literal["valid", "invalid"] | None
    last_ping: datetime | None
    observed_at: datetime | None
    firmware_version: str | None
    source: DataSource
    threshold_advisory_cm: float
    threshold_warning_cm: float
    threshold_evacuate_cm: float
    history: list[MonitoringSample]

    @field_validator("last_ping", "observed_at", mode="after")
    @classmethod
    def optional_timestamp_is_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class MonitoringSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checked_at: datetime
    stale_after_seconds: int
    stations: list[MonitoringStation]

    @field_validator("checked_at", mode="after")
    @classmethod
    def checked_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
