from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


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


class RainfallInterval(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    interval_start: AwareDatetime
    interval_end: AwareDatetime
    tip_count: int = Field(ge=0, le=9007199254740991)
    mm_per_tip: float = Field(gt=0, le=100)
    calibration_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    quality: Literal["valid", "partial", "invalid"]
    source: Literal["physical_rain_gauge", "simulated_rain_gauge"]

    @model_validator(mode="after")
    def bounded_interval(self):
        seconds = (self.interval_end-self.interval_start).total_seconds()
        if not 0 < seconds <= 86400:
            raise ValueError("Rainfall interval must be positive and at most one day")
        return self


class TelemetryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    station_id: str = Field(pattern=STATION_ID_PATTERN)
    schema_version: Literal[2, 3]
    config_version: int = Field(ge=1, le=2147483647)
    source_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,80}$")
    boot_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,80}$")
    # Durably incremented before transmitting after boot; never an arrival ordinal.
    boot_sequence: int = Field(ge=1, le=9223372036854775807)
    measured_at: AwareDatetime | None
    sequence_no: int = Field(ge=1, le=9223372036854775807)
    water_depth_cm: float | None = Field(default=None, ge=0, le=1000)
    rainfall_mm: float | None = Field(default=None, ge=0, le=1000, json_schema_extra={"deprecated": True})
    rainfall_interval: RainfallInterval | None = None
    applied_config_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    sensor_fault: Literal["none", "blind_zone", "no_echo", "out_of_range", "insufficient_echoes", "configuration_invalid"] = "none"
    local_alert_profile: Literal["depth", "cardboard_bench"] = "depth"
    sensor_quality: Literal["valid", "invalid"]
    device_uptime_ms: int = Field(ge=0, le=9223372036854775807)
    firmware_version: str = Field(
        min_length=1, max_length=50, pattern=SEMVER_PATTERN
    )

    @model_validator(mode="after")
    def quality_matches_measurement(self) -> "TelemetryCreate":
        import math
        if self.schema_version == 2:
            if self.rainfall_mm is None or self.rainfall_interval is not None or self.applied_config_hash is not None or self.sensor_fault != "none" or self.local_alert_profile!="depth":
                raise ValueError("Legacy v2 requires its deprecated rainfall field and cannot claim v3 metadata")
        else:
            if not self.applied_config_hash:
                raise ValueError("V3 requires the applied commissioning configuration hash")
            if self.rainfall_interval:
                interval = self.rainfall_interval
                if self.measured_at is None or interval.interval_end > self.measured_at:
                    raise ValueError("Rainfall interval must end no later than the measured timestamp")
                if self.rainfall_mm is None or not math.isclose(self.rainfall_mm,interval.tip_count*interval.mm_per_tip,abs_tol=1e-5,rel_tol=1e-5):
                    raise ValueError("Rainfall amount must conserve interval tips times calibration")
            elif self.rainfall_mm is not None:
                raise ValueError("V3 rainfall without explicit interval metadata is forbidden; use null and the rain journal")
            if self.sensor_quality == "valid" and self.sensor_fault != "none":
                raise ValueError("A valid depth cannot carry a sensor fault")
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
    schema_version: int
    config_version: int
    source_id: str
    boot_id: str
    boot_sequence: int
    measured_at: datetime | None
    received_at: datetime
    eligible_for_current: bool
    disposition: str
    source_class: Literal["physical_device", "simulator", "unverified"] = "unverified"
    source_trusted: bool = False
    stream: Literal["operational", "exercise"] = "operational"
    ingress_identity: str | None = None
    ingress_transport: str = "legacy"
    water_depth_cm: float | None
    rainfall_mm: float | None
    rainfall_interval: RainfallInterval | None = None
    applied_config_hash: str | None = None
    sensor_fault: str = "none"
    local_alert_profile: str = "depth"
    sensor_quality: str
    device_uptime_ms: int
    recorded_at: datetime

    @field_validator("recorded_at", "measured_at", "received_at", mode="after")
    @classmethod
    def timestamp_is_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
