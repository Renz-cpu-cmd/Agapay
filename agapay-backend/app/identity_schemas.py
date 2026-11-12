from typing import Annotated, Literal
from pydantic import Field, StringConstraints
from app.account_schemas import AccountInput, EmailStr, Name, Password, Phone, Barangay, Role

Reason=Annotated[str,StringConstraints(strip_whitespace=True,min_length=3,max_length=500)]
Token=Annotated[str,StringConstraints(min_length=40,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')]


class RecoveryRequest(AccountInput):
    email: EmailStr = Field(max_length=254)
    purpose: Literal['password_reset','verify_email'] = 'password_reset'


class RecoveryComplete(AccountInput):
    token: Token
    password: Password | None = None


class InvitationRequest(AccountInput):
    email: EmailStr = Field(max_length=254)
    name: Name
    phone: Phone
    barangay: Barangay
    role: Role = 'officer'
    reason: Reason


class MfaVerify(AccountInput):
    challenge_token: Token
    code: str = Field(min_length=6,max_length=64)


class MfaStart(AccountInput):
    current_password: str = Field(min_length=1,max_length=128)
    code: str | None = Field(default=None,min_length=6,max_length=64)


class RevokeRequest(AccountInput):
    reason: Reason


class SessionRevoke(RevokeRequest):
    session_id: str = Field(min_length=36,max_length=36)


class DeviceRevoke(RevokeRequest):
    device_id: str = Field(min_length=36,max_length=36)
