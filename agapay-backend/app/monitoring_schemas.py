from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


AlertTier = Literal["NORMAL", "ADVISORY", "WARNING", "EVACUATE"]
ConnectionState = Literal["online", "offline", "no_data", "inactive", "maintenance"]
TrendState = Literal["rising_rapidly", "rising", "stable", "falling", "unknown"]
DataSource = Literal["simulator", "device", "unverified", "none"]


class HealthChannel(BaseModel):
    state: Literal["healthy", "stale", "invalid", "no_data", "unverified", "disabled", "unknown", "disconnected"]
    reason: str
    observed_at: datetime | None = None
    age_seconds: float | None = None
    value: float | None = None
    unit: str | None = None
    increment_mm: float | None = None
    mm_per_tip: float | None = None
    source_trusted: bool | None = None
    ingress_transport: str | None = None
    connection_state: str | None = None
    connection_observed_at: datetime | None = None
    observer_scope: str | None = None


class CalibrationHealth(BaseModel):
    state: Literal["documented", "unconfigured"]
    reason: str
    water_note: str | None = None
    reference_datum: str | None = None
    rain_configured_mm_per_tip: float | None = None
    physical_validation: Literal["pending"] = "pending"


class StationChannelHealth(BaseModel):
    device_heartbeat: HealthChannel
    water_sensor: HealthChannel
    rain_counter: HealthChannel
    broker_ingestion: HealthChannel
    calibration: CalibrationHealth


class MonitoringSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_no: int
    water_depth_cm: float | None
    rainfall_mm: float | None
    sensor_quality: Literal["valid", "invalid"]
    device_uptime_ms: int
    recorded_at: datetime
    measured_at: datetime | None = None
    received_at: datetime | None = None

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
    coordinate_status: Literal["verified", "unverified", "missing", "invalid"] = Field(
        default="missing",
        description="Registry location state. 'verified': a finite, in-range pair confirmed at commissioning. "
                    "'unverified': a recorded pair without commissioning confirmation. 'missing'/'invalid': "
                    "latitude/longitude are null and no map position may be shown or inferred. Independent of "
                    "installation-configuration review.")
    coordinate_precision_m: int | None = Field(
        default=None,
        description="Recorded radius (metres) within which the true installation point lies. Null when the "
                    "precision was never recorded, or when there is no mappable pair. A confirmed pair is not "
                    "an exact point unless this is small and coordinate_basis is 'surveyed'.")
    coordinate_basis: Literal["surveyed", "owner_confirmed", "estimated"] | None = Field(
        default=None,
        description="How the position was obtained. Null when not recorded or when there is no mappable pair. "
                    "Independent of device authentication and of installation-configuration review.")
    administrative_status: Literal["active", "inactive", "maintenance"]
    connection_status: ConnectionState
    is_online: bool
    is_stale: bool
    age_seconds: int | None
    heartbeat_at: datetime | None
    heartbeat_age_seconds: int | None
    heartbeat_fresh: bool
    latest_sample_at: datetime | None
    latest_sample_age_seconds: int | None
    last_valid_depth_at: datetime | None
    depth_age_seconds: int | None
    depth_fresh: bool
    depth_status: Literal["fresh", "retained", "stale", "missing"]
    rainfall_observed_at: datetime | None
    rainfall_age_seconds: int | None
    rainfall_fresh: bool
    hazard_state: Literal["observed", "unresolved", "none", "unknown"]
    active_hazard_tier: AlertTier | None
    active_alert_id: int | None
    observation_tier: AlertTier | None = None
    hazard_policy_state: Literal["provisional", "station_reviewed"] = "provisional"
    hazard_decision: str | None = None
    hazard_review_required: bool = False
    alert_tier: AlertTier | None
    channel_health: StationChannelHealth | None = None
    rainfall_product: dict | None = None
    configuration: dict | None = None
    lifecycle: dict | None = None
    rise_rate_cm_per_minute: float | None = None
    rise_rate_lower: float | None = None
    rise_rate_upper: float | None = None
    trend_window_start: datetime | None = None
    trend_window_end: datetime | None = None
    trend_sample_count: int = 0
    trend_bin_count: int = 0
    trend_coverage: float = 0
    trend_reason: str = "Insufficient coverage"
    trend_method: str = "Median pairwise slope"
    trend: TrendState
    current_depth_cm: float | None
    latest_depth_cm: float | None
    latest_rainfall_mm: float | None
    sensor_quality: Literal["valid", "invalid"] | None
    last_ping: datetime | None
    observed_at: datetime | None
    firmware_version: str | None
    source: DataSource
    source_class: Literal["physical_device", "simulator", "unverified"]
    source_trusted: bool
    depth_source_class: Literal["physical_device", "simulator", "unverified"]
    depth_source_trusted: bool
    depth_source_id: str | None
    stream: Literal["operational"] = "operational"
    threshold_advisory_cm: float
    threshold_warning_cm: float
    threshold_evacuate_cm: float
    history: list[MonitoringSample]

    @field_validator("last_ping", "observed_at", "heartbeat_at", "latest_sample_at", "last_valid_depth_at", "rainfall_observed_at", mode="after")
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
    service_health: dict | None = None

    @field_validator("checked_at", mode="after")
    @classmethod
    def checked_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
