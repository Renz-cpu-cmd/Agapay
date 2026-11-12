from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class StepUp(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: SecretStr = Field(min_length=1, max_length=128)


class CaseCreate(StepUp):
    kind: Literal['access', 'correction', 'erasure']


class CaseDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    state: Literal['IN_REVIEW', 'DEFERRED', 'COMPLETED', 'REJECTED']
    decision_code: Literal['identity_review', 'access_delivered', 'correction_reviewed', 'erasure_external_verified',
                           'open_incident', 'legal_hold', 'external_review', 'not_applicable']
    evidence_sha256: str = Field(pattern='^[a-f0-9]{64}$')


class HoldChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=0)
    active: bool
    expires_at: datetime
    reason_code: Literal['legal_review', 'open_incident', 'subject_dispute']
    evidence_sha256: str = Field(pattern='^[a-f0-9]{64}$')
