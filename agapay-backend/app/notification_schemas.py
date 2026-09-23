from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class DeviceRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["fcm"]
    platform: Literal["android", "ios"]
    installation_id: UUID
    provider_token: SecretStr = Field(min_length=16, max_length=4096)

    @field_validator("provider_token")
    @classmethod
    def token_has_no_whitespace(cls, value: SecretStr) -> SecretStr:
        if any(c.isspace() for c in value.get_secret_value()):
            raise ValueError("Provider token must not contain whitespace")
        return value


class NotificationDeviceRead(BaseModel):
    """Explicit allowlist: never serialize token, hash, session or user ID."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    platform: Literal["android", "ios"]
    provider: Literal["fcm"]
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime

    @field_validator("created_at", "updated_at", "last_seen_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
