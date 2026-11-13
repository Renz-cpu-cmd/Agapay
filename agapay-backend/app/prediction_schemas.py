from datetime import datetime, timezone,timedelta
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

ForecastStatus = Literal["not_trained", "unavailable", "insufficient_data", "stale_data", "invalid_data", "available", "service_error"]
InputStatus = Literal["usable", "insufficient_data", "stale_data", "invalid_data"]
HORIZONS = (30, 60, 90)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PredictionSample(Contract):
    recorded_at: AwareDatetime
    water_depth_cm: float | None = Field(ge=0, le=1000)
    rainfall_mm: float | None = Field(default=None, ge=0, le=1000)
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
    lower_depth_cm: float | None = Field(default=None, ge=0, le=1000)
    upper_depth_cm: float | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode='after')
    def interval(self):
        if (self.lower_depth_cm is None)!=(self.upper_depth_cm is None):raise ValueError('Supply both interval bounds')
        if self.lower_depth_cm is not None and (self.water_depth_cm is None or not self.lower_depth_cm<=self.water_depth_cm<=self.upper_depth_cm):raise ValueError('Interval must contain the point estimate')
        return self


class ForecastUncertainty(Contract):
    method:Literal['calibration_event_max_absolute_residual_all_horizons']
    nominal_coverage:float=Field(ge=.8,le=.99)
    withheld_event_coverage:float=Field(ge=0,le=1)
    calibration_events:int=Field(ge=1)
    test_events:int=Field(ge=1)
    policy_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    display_resolution_cm:float=Field(gt=0,le=100)
    notice:Literal['Event-calibrated local-depth interval; coverage can fail under drift']='Event-calibrated local-depth interval; coverage can fail under drift'


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
    forecast_id: str | None = None
    deployment_version: int | None = None
    configuration_hash: str | None = None
    reference_datum: str | None = None
    model_card_id: str | None = None
    data_cutoff: AwareDatetime | None = None
    measurement_source: Literal['registry_verified_physical_device'] | None = None
    ingress_identity: str | None = None
    registry_version: int | None = None
    uncertainty:ForecastUncertainty|None=None

    @field_validator("checked_at", "generated_at", "valid_until", "input_window_start", "input_last_recorded_at","data_cutoff")
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
        elif any(p.water_depth_cm is not None or p.target_at is not None or p.lower_depth_cm is not None or p.upper_depth_cm is not None for p in self.forecasts):
            raise ValueError("Unavailable forecasts must use null, never zero or cached predictions.")
        if self.source == "simulated" and self.model_version is not None:
            raise ValueError("Simulated previews cannot claim a trained model version.")
        return self


class PublishedPredictionResponse(PredictionResponse):
    status:Literal['available']='available'
    source:Literal['model']='model'
    forecast_id:str=Field(pattern=r'^[a-f0-9-]{36}$')
    deployment_version:int=Field(ge=1)
    configuration_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    reference_datum:str=Field(min_length=3,max_length=200)
    model_card_id:str=Field(pattern=r'^[a-f0-9]{64}$')
    data_cutoff:AwareDatetime
    measurement_source:Literal['registry_verified_physical_device']
    ingress_identity:str=Field(min_length=1,max_length=200)
    registry_version:int=Field(ge=1)
    uncertainty:ForecastUncertainty

    @model_validator(mode='after')
    def publication_identity(self):
        if any(p.lower_depth_cm is None or p.upper_depth_cm is None for p in self.forecasts):raise ValueError('Published predictions require calibrated intervals')
        if self.data_cutoff!=self.input_last_recorded_at or self.timestamp_basis!='device_measured' or self.model_card_id!=self.model_version:raise ValueError('Published model/source/cutoff mismatch')
        if not self.generated_at or not self.input_last_recorded_at<=self.generated_at<=self.checked_at:raise ValueError('Published inputs and generation cannot be in the future')
        if any(p.target_at!=self.data_cutoff+timedelta(minutes=p.horizon_minutes) for p in self.forecasts):raise ValueError('Target timestamps must follow the measured cutoff')
        return self
