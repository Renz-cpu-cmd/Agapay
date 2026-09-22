from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

ForecastStatus = Literal["not_trained", "insufficient_data", "stale_data", "invalid_data", "available", "service_error"]
InputStatus = Literal["usable", "insufficient_data", "stale_data", "invalid_data"]
HORIZONS = (30, 60, 90)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PredictionSample(Contract):
    recorded_at: AwareDatetime
    water_depth_cm: float | None = Field(ge=0, le=1000)
    rainfall_mm: float = Field(ge=0, le=1000)
    # Null means the existing telemetry contract does not define the rainfall period.
    rainfall_interval_seconds: int | None = Field(default=None, ge=1, le=86400)
    sensor_quality: Literal["valid", "invalid"]

    @model_validator(mode="after")
    def quality_matches_depth(self):
        if (self.sensor_quality == "valid") != (self.water_depth_cm is not None):
            raise ValueError("Valid samples require a depth; invalid samples require null.")
        return self


class PredictionInput(Contract):
    schema_version: Literal["1.0"] = "1.0"
    station_id: str = Field(pattern=r"^[A-Z0-9_-]{3,50}$")
    as_of: AwareDatetime
    timestamp_basis: Literal["server_received", "device_measured", "synthetic"]
    samples: list[PredictionSample] = Field(max_length=3600)

    @model_validator(mode="after")
    def chronological_history(self):
        times = [s.recorded_at for s in self.samples]
        if any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError("Input timestamps must be strictly increasing.")
        if times and times[-1] > self.as_of:
            raise ValueError("Input samples cannot be in the future.")
        return self


class ModelForecast(Contract):
    horizon_minutes: Literal[30, 60, 90]
    water_depth_cm: float = Field(ge=0, le=1000)


class ModelOutput(Contract):
    forecasts: list[ModelForecast]

    @model_validator(mode="after")
    def exact_horizons(self):
        if tuple(p.horizon_minutes for p in self.forecasts) != HORIZONS:
            raise ValueError("Return exactly the 30, 60 and 90 minute horizons in order.")
        return self


class ForecastPoint(Contract):
    horizon_minutes: Literal[30, 60, 90]
    target_at: AwareDatetime | None = None
    water_depth_cm: float | None = Field(default=None, ge=0, le=1000)


class PredictionResponse(Contract):
    schema_version: Literal["1.0"] = "1.0"
    station_id: str
    status: ForecastStatus
    reason: str
    source: Literal["none", "model", "simulated"]
    advisory_only: Literal[True] = True
    checked_at: AwareDatetime
    generated_at: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    model_version: str | None = None
    input_status: InputStatus
    input_window_start: AwareDatetime | None = None
    input_last_recorded_at: AwareDatetime | None = None
    sample_count: int = Field(ge=0)
    valid_sample_count: int = Field(ge=0)
    timestamp_basis: Literal["server_received", "device_measured", "synthetic"]
    rainfall_interval_seconds: int | None = None
    preview_allowed: bool
    forecasts: list[ForecastPoint]

    @field_validator("checked_at", "generated_at", "valid_until", "input_window_start", "input_last_recorded_at")
    @classmethod
    def utc_times(cls, value):
        return value.astimezone(timezone.utc) if value is not None else None

    @model_validator(mode="after")
    def enforce_availability(self):
        if tuple(p.horizon_minutes for p in self.forecasts) != HORIZONS:
            raise ValueError("Every response must contain all three horizons.")
        if self.status == "available":
            if self.source == "none" or self.generated_at is None or self.valid_until is None or self.input_last_recorded_at is None:
                raise ValueError("Available forecasts require source and time metadata.")
            if self.valid_until <= self.checked_at:
                raise ValueError("Available forecasts must not be expired.")
            if any(p.water_depth_cm is None or p.target_at is None for p in self.forecasts):
                raise ValueError("Available forecasts need numeric values and target times.")
            if self.source == "model" and not self.model_version:
                raise ValueError("Model forecasts require a version.")
        elif any(p.water_depth_cm is not None or p.target_at is not None for p in self.forecasts):
            raise ValueError("Unavailable forecasts must use null, never zero or cached predictions.")
        if self.source == "simulated" and self.model_version is not None:
            raise ValueError("Simulated previews cannot claim a trained model version.")
        return self
