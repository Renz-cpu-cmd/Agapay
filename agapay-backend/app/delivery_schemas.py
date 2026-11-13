from datetime import datetime
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,SecretStr,field_validator


class ReceiptCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    delivery_id:int=Field(gt=0,le=9007199254740991)
    attempt_no:int=Field(ge=1,le=100)
    stage:Literal['RECEIVED','OPENED']
    receipt_token:SecretStr=Field(min_length=40,max_length=80)
    reported_at:datetime|None=None
    @field_validator('reported_at')
    @classmethod
    def aware(cls,value):
        if value and value.tzinfo is None:raise ValueError('Receipt timestamp must include timezone')
        return value


class ConsentUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=0)
    enabled:bool


class DeliveryAcknowledge(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=0)
    confirmed:Literal[True]


class DeliveryReconcile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=0)
    decision:Literal['provider_accepted','not_accepted','closed_no_resend','followup_recorded']
    evidence_kind:Literal['provider_record','recipient_contact','manual_review','fallback_action']
    evidence_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    reason:str=Field(min_length=8,max_length=500)
