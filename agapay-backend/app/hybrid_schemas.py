from datetime import datetime
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class BasinInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    contributing_area_m2: float = Field(default=2, ge=0, le=1000000)
    basin_surface_area_m2: float = Field(default=.1, gt=0, le=1000000)
    runoff_coefficient: float = Field(default=.8, ge=0, le=1)
    outflow_m3_per_hour: float = Field(default=0, ge=0, le=1000000)
    maximum_depth_cm: float = Field(default=100, gt=0, le=1000)
    parameter_basis: dict[str, Literal["assumed", "estimated", "measured"]] = Field(default_factory=lambda: {
        key: "assumed" for key in ("contributing_area_m2", "basin_surface_area_m2", "runoff_coefficient", "outflow_m3_per_hour", "maximum_depth_cm")})


class HybridProjectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mode: Literal["historical_context", "live"] = "historical_context"
    controlled_basin_confirmed: Literal[True]
    depth_source: Literal["manual", "sensor"] = "manual"
    manual_depth_cm: float = Field(default=20, ge=0, le=1000)
    initialization_at: AwareDatetime | None = None
    context_at: AwareDatetime = datetime.fromisoformat("2025-07-01T12:00:00+00:00")
    rain_source: Literal["physical_rain_gauge", "simulated_rain_gauge"] = "physical_rain_gauge"
    basin: BasinInput = Field(default_factory=BasinInput)

    @model_validator(mode="after")
    def initialization_mode(self):
        if self.mode == "historical_context" and self.depth_source != "manual":
            raise ValueError("Historical-context demonstration requires explicitly manual depth")
        return self


class HybridPoint(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    horizon_minutes:Literal[30,60,90]
    target_at:AwareDatetime
    depth_cm:float=Field(ge=0,le=1000)
    rainfall_mm:float=Field(ge=0)
    inflow_m3:float=Field(ge=0)
    outflow_m3:float=Field(ge=0)
    overflow_m3:float=Field(ge=0)
    unmet_outflow_m3:float=Field(ge=0)

class Balance(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    depth_cm:float=Field(ge=0,le=1000)
    inflow_m3:float=Field(ge=0)
    outflow_m3:float=Field(ge=0)
    overflow_m3:float=Field(ge=0)
    unmet_outflow_m3:float=Field(ge=0)

class RainHour(BaseModel):
    model_config=ConfigDict(extra='ignore',allow_inf_nan=False)
    timestamp_utc:AwareDatetime
    rainfall_mm:float|None=Field(default=None,ge=0)
    interval_seconds:Literal[3600]
    valid:bool
    interval_start:AwareDatetime|None=None
    interval_end:AwareDatetime|None=None
    quality:str|None=None
    calibration_versions:list[str]=Field(default_factory=list,max_length=10000)

class RainActivity(BaseModel):
    model_config=ConfigDict(extra='ignore',allow_inf_nan=False)
    station_id:str
    data_source:Literal['physical_rain_gauge','simulated_rain_gauge']
    connected:bool
    status:str='no_data'
    checked_at:AwareDatetime
    last_received_at:AwareDatetime|None=None
    current_hour_start:AwareDatetime|None=None
    incomplete_hour_mm:float|None=Field(default=None,ge=0)
    completed_hours:list[RainHour]=Field(default_factory=list,max_length=24)
    current_hour_product:dict|None=None
    ml_ready:bool=False
    source_trusted:bool=False
    source_class:str='unverified'
    calibration_version:str|None=None
    mm_per_tip:float|None=Field(default=None,gt=0)
    product_version:int|None=None
    boot_session_tip_count:int|None=None
    latest_tip_event_id:int|None=None
    events:list[dict]=Field(default_factory=list,max_length=100)

class HybridProjectionResponse(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    workspace:Literal['private_experiment']='private_experiment'
    station_id:str
    status:Literal['available','unavailable']
    reason:str
    notice:str
    advisory_only:Literal[True]
    checked_at:AwareDatetime
    generated_at:AwareDatetime|None=None
    valid_until:AwareDatetime|None=None
    mode:Literal['live','historical_context']|None=None
    initialization_at:AwareDatetime|None=None
    initial_depth_cm:float|None=Field(default=None,ge=0,le=1000)
    initial_source:str|None=None
    model_version:str|None=None
    rainfall_source:str|None=None
    rainfall_origin:AwareDatetime|None=None
    rainfall_context_at:AwareDatetime|None=None
    rainfall_hourly_mm:list[float]|None=None
    rainfall_history:list[RainHour]|None=None
    observed_rainfall_since_initialization_mm:float|None=Field(default=None,ge=0)
    adjusted:Balance|None=None
    parameters:BasinInput|None=None
    assumption:str|None=None
    points:list[HybridPoint]=Field(max_length=3)
    rain_snapshot:RainActivity|None=None
    rain_activity:RainActivity|None=None
    setup_label:str|None=None
    @model_validator(mode='after')
    def available_values(self):
        if self.status=='available':
            if not self.valid_until or self.valid_until<=self.checked_at or not self.model_version or not self.adjusted or tuple(p.horizon_minutes for p in self.points)!=(30,60,90):raise ValueError('Incomplete experimental response')
        elif self.points:raise ValueError('Unavailable experiment cannot contain projections')
        return self

class RainActivityResponse(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    workspace:Literal['observations_only']='observations_only'
    station_id:str
    status:Literal['unavailable']='unavailable'
    reason:str='Rain observations only; published water-depth forecasts use the prediction product.'
    notice:str='Observed rainfall is independent of forecasting'
    advisory_only:Literal[True]=True
    checked_at:AwareDatetime
    points:list=Field(default_factory=list,max_length=0)
    rain_activity:RainActivity|None=None
