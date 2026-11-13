"""Separate rain snapshot contract; the existing telemetry contract is unchanged."""
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas import STATION_ID_PATTERN


class RainCounterEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal[1,2] = 1
    calibration_version: str = Field(default="legacy-unversioned",pattern=r"^(legacy-unversioned|[a-f0-9]{64})$")
    quality: Literal["valid"] = "valid"
    station_id: str = Field(pattern=STATION_ID_PATTERN)
    boot_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    packet_sequence: int = Field(ge=1, le=9007199254740991)
    cumulative_tip_count: int = Field(ge=0, le=9007199254740991)
    boot_start_tip_count: int = Field(ge=0, le=9007199254740991)
    interval_start_tip_count: int = Field(ge=0, le=9007199254740991)
    mm_per_tip: float = Field(gt=0, le=100)
    rainfall_increment_mm: float = Field(ge=0)
    device_uptime_ms: int = Field(ge=0, le=9007199254740991)
    last_tip_uptime_ms: int | None = Field(default=None, ge=0)
    interval_start_uptime_ms: int = Field(ge=0)
    counter_persisted: Literal[True]
    data_source: Literal["physical_rain_gauge", "simulated_rain_gauge"]
    firmware_version: str = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def consistent_counter(self):
        if self.schema_version==2 and self.calibration_version=="legacy-unversioned":
            raise ValueError("Rain v2 requires the applied calibration/configuration hash")
        if not self.boot_start_tip_count <= self.interval_start_tip_count <= self.cumulative_tip_count:
            raise ValueError("Counter baselines must not exceed the cumulative counter")
        if self.interval_start_uptime_ms > self.device_uptime_ms or (self.last_tip_uptime_ms is not None and self.last_tip_uptime_ms > self.device_uptime_ms):
            raise ValueError("Rain timing cannot exceed device uptime")
        expected=(self.cumulative_tip_count-self.interval_start_tip_count)*self.mm_per_tip
        if not math.isclose(self.rainfall_increment_mm,expected,rel_tol=1e-5,abs_tol=1e-5):
            raise ValueError("Reported increment does not match its explicit counter interval")
        if self.cumulative_tip_count > self.boot_start_tip_count and self.last_tip_uptime_ms is None:
            raise ValueError("A boot containing tips needs the last tip uptime")
        return self
