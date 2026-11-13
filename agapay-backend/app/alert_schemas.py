from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.monitoring_schemas import AlertTier

AlertStatus = Literal["ACTIVE", "RESOLVED"]


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    station_id: str
    current_severity: AlertTier
    highest_severity: Literal["ADVISORY", "WARNING", "EVACUATE"]
    status: AlertStatus
    source: Literal["sensor"]
    trigger_telemetry_id: int
    latest_telemetry_id: int
    trigger_sequence_no: int
    latest_sequence_no: int
    trigger_depth_cm: float
    latest_depth_cm: float
    triggered_at: datetime
    last_transition_at: datetime
    resolved_at: datetime | None

    @field_validator("triggered_at", "last_transition_at", "resolved_at", mode="after")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class AlertTransitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    station_id: str
    telemetry_id: int
    sequence_no: int
    previous_severity: AlertTier
    new_severity: AlertTier
    water_depth_cm: float
    transitioned_at: datetime

    @field_validator("transitioned_at", mode="after")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class AlertPage(BaseModel):
    items: list[AlertRead]
    total: int


class AlertTransitionPage(BaseModel):
    items: list[AlertTransitionRead]
    total: int
