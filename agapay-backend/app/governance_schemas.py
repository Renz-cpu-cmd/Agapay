from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class PolicyRules(StrictModel):
    advisory_hysteresis_cm: float = Field(ge=0, le=100)
    warning_hysteresis_cm: float = Field(ge=0, le=100)
    evacuate_hysteresis_cm: float = Field(ge=0, le=100)
    recovery_samples: int = Field(ge=1, le=1000)
    recovery_seconds: int = Field(ge=0, le=86400)
    max_sample_gap_seconds: int = Field(ge=1, le=3600)
    max_change_cm_per_second: float = Field(gt=0, le=10000)


class PolicyWrite(StrictModel):
    expected_version: int = Field(ge=0)
    rules: PolicyRules
    validation_evidence: str = Field(min_length=20, max_length=2000)
    reason: str = Field(min_length=10, max_length=1000)


class AreaWrite(StrictModel):
    area_class: Literal["geographic", "application"] = "geographic"
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,50}$")
    name: str = Field(min_length=3, max_length=200)
    identifier_scheme: str = Field(min_length=3, max_length=80)
    evidence: str = Field(min_length=20, max_length=2000)
    reason: str = Field(min_length=10, max_length=1000)


class AuthorityWrite(StrictModel):
    authority_class: Literal["app_operator", "public_authority"] = "app_operator"
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,50}$")
    name: str = Field(min_length=3, max_length=200)
    evidence: str = Field(min_length=20, max_length=2000)
    reason: str = Field(min_length=10, max_length=1000)


class GrantWrite(StrictModel):
    expected_revision: int = Field(ge=0)
    station_ids: list[str] = Field(default_factory=list, max_length=100)
    user_id: int
    area_ids: list[str] = Field(max_length=100)
    citywide: bool = False
    active: bool = True
    reason: str = Field(min_length=10, max_length=1000)


class AreaBinding(StrictModel):
    expected_revisions: dict[str,int] = Field(default_factory=dict, max_length=100)
    area_ids: list[str] = Field(max_length=100)
    reason: str = Field(min_length=10, max_length=1000)


class SubscriptionWrite(StrictModel):
    kind: Literal["station", "area"]
    target_id: str = Field(min_length=1, max_length=50)
    enabled: bool
    expected_revision: int = Field(ge=0)


class ReviewWrite(StrictModel):
    expected_telemetry_id: int = Field(ge=1)
    authority_id: str
    action: Literal["confirmed", "investigate", "request_escalation"]
    requested_severity: Literal["ADVISORY", "WARNING", "EVACUATE"] | None = None
    reason: str = Field(min_length=10, max_length=1000)


class NoticeWrite(StrictModel):
    authority_id: str
    area_ids: list[str] = Field(min_length=1, max_length=100)
    message_type: Literal["Alert", "Update", "Cancel"]
    reference_id: str | None = None
    category: Literal["advisory", "action"]
    status: Literal["Actual", "Exercise", "Test"]
    urgency: Literal["Immediate", "Expected", "Future", "Past", "Unknown"]
    severity: Literal["Extreme", "Severe", "Moderate", "Minor", "Unknown"]
    certainty: Literal["Observed", "Likely", "Possible", "Unlikely", "Unknown"]
    headline: str = Field(min_length=5, max_length=200)
    instruction: str = Field(min_length=10, max_length=4000)
    reason: str = Field(min_length=10, max_length=1000)
    effective_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def lifecycle(self):
        if (self.message_type == "Alert") != (self.reference_id is None):
            raise ValueError("Updates/cancellations must reference a notice; initial alerts must not")
        if self.expires_at <= self.effective_at:
            raise ValueError("Expiry must follow effective time")
        return self


class CitywideWrite(StrictModel):
    authority_id: str
    reason: str = Field(min_length=20, max_length=1000)
    expires_at: AwareDatetime


class RevokeBinding(StrictModel):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=1000)
