from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


STATION_ID_PATTERN = r"^[A-Z0-9_-]{3,50}$"
SEMVER_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$"


class StationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: str = Field(pattern=STATION_ID_PATTERN)
    station_name: str = Field(min_length=1, max_length=255)
    barangay: str | None = Field(default=None, max_length=255)
    municipality: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    sensor_height_cm: float = Field(default=120.0, gt=0, le=1000)
    threshold_advisory_cm: float = Field(default=60.0, ge=0, le=1000)
    threshold_warning_cm: float = Field(default=85.0, ge=0, le=1000)
    threshold_evacuate_cm: float = Field(default=100.0, ge=0, le=1000)

    @model_validator(mode="after")
    def thresholds_are_ordered(self) -> "StationCreate":
        if not (
            self.threshold_advisory_cm
            < self.threshold_warning_cm
            < self.threshold_evacuate_cm
        ):
            raise ValueError(
                "Thresholds must be ordered: advisory < warning < evacuate"
            )
        return self


class StationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    station_id: str
    station_name: str
    barangay: str | None
    municipality: str | None
    latitude: float | None
    longitude: float | None
    sensor_height_cm: float
    threshold_advisory_cm: float
    threshold_warning_cm: float
    threshold_evacuate_cm: float
    status: str
    last_ping: datetime | None
    firmware_version: str | None
    created_at: datetime

    @field_validator("last_ping", "created_at", mode="after")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class TelemetryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: str = Field(pattern=STATION_ID_PATTERN)
    sequence_no: int = Field(ge=1)
    water_depth_cm: float | None = Field(default=None, ge=0, le=1000)
    rainfall_mm: float = Field(ge=0, le=1000)
    sensor_quality: Literal["valid", "invalid"]
    device_uptime_ms: int = Field(ge=0)
    firmware_version: str = Field(
        min_length=1, max_length=50, pattern=SEMVER_PATTERN
    )

    @model_validator(mode="after")
    def quality_matches_measurement(self) -> "TelemetryCreate":
        if self.sensor_quality == "valid" and self.water_depth_cm is None:
            raise ValueError("A valid sensor sample requires water_depth_cm")
        if self.sensor_quality == "invalid" and self.water_depth_cm is not None:
            raise ValueError("An invalid sensor sample must use water_depth_cm=null")
        return self


class TelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    station_id: str
    sequence_no: int
    water_depth_cm: float | None
    rainfall_mm: float
    sensor_quality: str
    device_uptime_ms: int
    recorded_at: datetime

    @field_validator("recorded_at", mode="after")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
