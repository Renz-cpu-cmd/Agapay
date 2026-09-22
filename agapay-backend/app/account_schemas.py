from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

Role = Literal["admin", "officer", "resident"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Barangay = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=7, max_length=30, pattern=r"^\+?[0-9 ()-]+$")]
Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class RegisterRequest(AccountInput):
    name: Name
    email: EmailStr = Field(max_length=254)
    password: Password
    phone: Phone
    barangay: Barangay


class SetupStatus(BaseModel):
    available: bool
    reason: str


class LoginRequest(AccountInput):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)
    audience: Literal["web", "mobile"]


class AdminCreateRequest(RegisterRequest):
    role: Role = "officer"


class ProfileUpdate(AccountInput):
    name: Name | None = None
    email: EmailStr | None = Field(default=None, max_length=254)
    phone: Phone | None = None
    barangay: Barangay | None = None
    current_password: str | None = Field(default=None, max_length=128)
    password: Password | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for key in self.model_fields_set:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self


class AdminUpdateRequest(ProfileUpdate):
    role: Role | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    phone: str
    barangay: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_dates(cls, value: datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class SessionRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead
