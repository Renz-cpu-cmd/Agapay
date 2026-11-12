from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import Field, field_validator, model_validator
from app.account_schemas import AccountInput
from app.identity_schemas import Reason


class DutyShift(AccountInput):
    user_id: int = Field(ge=1)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode='after')
    def interval(self):
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError('Duty hours require timezone-aware timestamps')
        if self.ends_at <= self.starts_at or (self.ends_at-self.starts_at).days > 31:
            raise ValueError('Duty shift must be positive and at most 31 days')
        self.starts_at = self.starts_at.astimezone(timezone.utc)
        self.ends_at = self.ends_at.astimezone(timezone.utc)
        return self


class FallbackContact(AccountInput):
    label: str = Field(min_length=3, max_length=100)
    channel: Literal['phone', 'radio', 'in_person']
    contact: str = Field(min_length=3, max_length=150)


class DrillPolicyWrite(AccountInput):
    expected_version: int = Field(ge=0)
    reason: Reason
    coordinator_id: int = Field(ge=1)
    timezone: str = 'Asia/Manila'
    assignment_seconds: int = Field(default=120, ge=5, le=86400)
    acceptance_seconds: int = Field(default=180, ge=5, le=86400)
    departure_seconds: int = Field(default=300, ge=5, le=86400)
    arrival_seconds: int = Field(default=900, ge=5, le=86400)
    review_seconds: int = Field(default=300, ge=5, le=86400)
    shifts: list[DutyShift] = Field(min_length=1, max_length=50)
    fallback_contacts: list[FallbackContact] = Field(min_length=1, max_length=10)

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        try: ZoneInfo(value)
        except (KeyError, ValueError): raise ValueError('Unknown IANA timezone') from None
        return value

    @model_validator(mode='after')
    def has_coordinator(self):
        if self.coordinator_id not in {s.user_id for s in self.shifts}:
            raise ValueError('Coordinator needs explicit duty hours')
        return self


class StartDrill(AccountInput):
    expected_version: int = Field(ge=1)
    policy_version: int = Field(ge=1)
    reason: Reason


class ResponseAction(AccountInput):
    expected_version: int = Field(ge=1)
    action: Literal['assign', 'contact_attempt', 'accept', 'depart', 'arrive', 'handoff', 'unavailable', 'close', 'correlate', 'review_escalation']
    reason: Reason
    responder_id: int | None = Field(default=None, ge=1)
    incident_id: int | None = Field(default=None, ge=1)
    reference: str | None = Field(default=None, min_length=3, max_length=150)
    channel: Literal['phone', 'radio', 'in_person'] | None = None
    outcome: Literal['connected', 'no_answer', 'failed'] | None = None
    closure_reason: Literal['assistance_completed', 'cancelled_by_resident', 'duplicate_correlated', 'unable_to_contact', 'exercise_complete'] | None = None


class IncidentCreate(AccountInput):
    label: str = Field(min_length=3, max_length=120)
    reason: Reason
