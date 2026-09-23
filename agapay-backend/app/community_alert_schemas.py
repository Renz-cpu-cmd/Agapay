"""Resident-safe projections, deliberately independent of operational schemas."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.alert_schemas import AlertStatus
from app.monitoring_schemas import AlertTier


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


UtcTimestamp = Annotated[datetime, AfterValidator(as_utc)]


class CommunityAlertRead(BaseModel):
    id: int
    station_id: str
    station_name: str
    barangay: str | None
    municipality: str | None
    status: AlertStatus
    severity: Literal["ADVISORY", "WARNING", "EVACUATE"] = Field(
        description="Current severity while ACTIVE; highest incident severity while RESOLVED. Not an official evacuation order."
    )
    source: Literal["sensor"] = Field(
        description="Telemetry-generated episode. Historical device/simulator origin is not stored; this does not establish physical validation."
    )
    trigger_depth_cm: float = Field(description="First alert reading, not peak depth.")
    latest_depth_cm: float = Field(
        description="Last valid episode depth while ACTIVE; final NORMAL recovery depth while RESOLVED. May be stale; invalid readings do not update it."
    )
    triggered_at: UtcTimestamp
    last_transition_at: UtcTimestamp
    resolved_at: UtcTimestamp | None


class CommunityAlertPage(BaseModel):
    items: list[CommunityAlertRead]
    total: int


class CommunityAlertTransitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    previous_severity: AlertTier
    new_severity: AlertTier
    water_depth_cm: float
    transitioned_at: UtcTimestamp


class CommunityAlertTransitionPage(BaseModel):
    items: list[CommunityAlertTransitionRead]
    total: int


class CommunityAlertDetail(CommunityAlertRead):
    transitions: CommunityAlertTransitionPage
