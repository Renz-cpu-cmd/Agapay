from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator, model_validator

from app.schemas import StationCreate, TelemetryCreate
from app.rain_schemas import RainCounterEvent

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class Commissioning(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    device_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,80}$")
    state: Literal["pending", "commissioned", "decommissioned"] = "pending"
    coordinates_verified: bool = False
    reference_datum: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    calibration_note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]
    reason: Reason
    source_class: Literal["physical_device", "simulator", "unverified"] = "unverified"
    stream: Literal["operational", "exercise"] = "exercise"
    provenance_evidence: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)] = "Not physically verified"

    @model_validator(mode="after")
    def source_policy(self):
        if self.stream == "operational" and self.source_class != "physical_device":
            raise ValueError("Operational streams require a reviewed physical device")
        if self.source_class == "physical_device" and self.provenance_evidence == "Not physically verified":
            raise ValueError("Physical source designation requires explicit review evidence")
        return self


class StationProvisionRequest(StationCreate):
    commissioning: Commissioning


class CommissionRequest(Commissioning):
    expected_version: int = Field(ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (("latitude" in self.model_fields_set) != ("longitude" in self.model_fields_set)
                or (self.latitude is None) != (self.longitude is None)):
            raise ValueError("Supply both coordinates together, or omit both to retain the current location")
        return self


class StationReadContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("commissioned_at", "created_at", "expires_at", "revoked_at", check_fields=False)
    @classmethod
    def utc_dates(cls, value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class CommissionRead(StationReadContract):
    station_id: str
    device_id: str
    state: str
    coordinates_verified: bool
    reference_datum: str
    calibration_note: str
    version: int
    commissioned_at: datetime | None
    source_class: Literal["physical_device", "simulator", "unverified"] = "unverified"
    stream: Literal["operational", "exercise"] = "exercise"
    provenance_evidence: str = "Not physically verified"


class CredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    transport: Literal["http", "mqtt", "both"] = "both"
    expires_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    reason: Reason

    @model_validator(mode="after")
    def bounded_expiry(self):
        remaining = self.expires_at - datetime.now(timezone.utc)
        if not timedelta(seconds=0) < remaining <= timedelta(days=366):
            raise ValueError("Credential expiry must be in the future and within 366 days")
        return self


class CredentialRead(StationReadContract):
    id: str
    station_id: str
    identity_version: int
    label: str
    transport: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class CredentialIssued(CredentialRead):
    # Returned once to the administrator; never persisted or included in list/audit views.
    ingest_token: str = Field(repr=False)


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason


class StationAuditRead(StationReadContract):
    id: int
    station_id: str
    actor_id: int
    actor_name: str
    action: str
    reason: str
    details: dict
    created_at: datetime


class MqttTelemetryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingest_token: SecretStr = Field(min_length=47, max_length=47)
    telemetry: TelemetryCreate
    delivery_mode: Literal["live", "backfill"] = "live"


class MqttRainEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingest_token: SecretStr = Field(min_length=47, max_length=47)
    rain: RainCounterEvent
