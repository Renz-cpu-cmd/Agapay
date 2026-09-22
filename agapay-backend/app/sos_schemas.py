from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Status = Literal["ACTIVE", "ACKNOWLEDGED", "RESOLVED"]


class SosCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    request_id: UUID
    location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_source: Literal["gps", "manual"] = "manual"
    accuracy_m: float | None = Field(default=None, ge=0, le=100000)
    location_recorded_at: datetime | None = None

    @model_validator(mode="after")
    def validate_location(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or leave both empty.")
        if self.location_source == "gps":
            if self.latitude is None or self.accuracy_m is None or self.location_recorded_at is None:
                raise ValueError("GPS locations require coordinates, accuracy and capture time.")
            if self.location_recorded_at.tzinfo is None:
                raise ValueError("GPS capture time must include a timezone.")
            self.location_recorded_at = self.location_recorded_at.astimezone(timezone.utc)
        elif self.accuracy_m is not None or self.location_recorded_at is not None:
            raise ValueError("Manual locations cannot claim GPS accuracy or capture time.")
        return self


class SosTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ACKNOWLEDGED", "RESOLVED"]
    resolution_note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""


class SosLocationUpdate(BaseModel):
    """A fresh device fix uploaded by the resident while an SOS is open."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(ge=0, le=100000)
    location_recorded_at: datetime

    @field_validator("location_recorded_at")
    @classmethod
    def utc_capture_time(cls, value: datetime):
        if value.tzinfo is None:
            raise ValueError("GPS capture time must include a timezone.")
        return value.astimezone(timezone.utc)


class SosRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    request_id: str
    resident_name: str
    phone: str
    barangay: str
    location: str
    message: str
    latitude: float | None
    longitude: float | None
    location_source: str
    accuracy_m: float | None
    location_recorded_at: datetime | None
    practice: bool
    status: Status
    created_at: datetime
    acknowledged_by_name: str | None
    acknowledged_at: datetime | None
    resolved_by_name: str | None
    resolved_at: datetime | None
    resolution_note: str | None

    @field_validator("created_at", "location_recorded_at", "acknowledged_at", "resolved_at")
    @classmethod
    def utc_dates(cls, value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class SosPage(BaseModel):
    items: list[SosRead]
    total: int
    counts: dict[str, int]
