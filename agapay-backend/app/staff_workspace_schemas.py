from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class OwnershipRead(BaseModel):
    revision: int
    owner_id: int | None
    owner_name: str | None
    changed_at: datetime | None


class AreaRead(BaseModel):
    id: str
    name: str


class CommandEpisode(BaseModel):
    id: int
    station_id: str
    station_name: str
    severity: Literal['ADVISORY', 'WARNING', 'EVACUATE']
    triggered_at: datetime
    last_transition_at: datetime
    latest_telemetry_id: int
    latest_depth_cm: float
    ownership: OwnershipRead
    areas: list[AreaRead]
    source: Literal['recorded_physical', 'unverified']


class CommandQueue(BaseModel):
    items: list[CommandEpisode]
    total: int
    has_more: bool
    checked_at: datetime
    scope: Literal['operational', 'unverified']
    counts: dict[Literal['operational', 'unverified'], int]


class SampleEvidence(BaseModel):
    id: int
    measured_at: datetime | None
    received_at: datetime
    quality: str
    disposition: str
    source_id: str | None
    registry_version: int | None
    transport: str | None
    source_class: str


class IdentityEvidence(BaseModel):
    device_id: str
    version: int
    state: str
    coordinates_verified: bool
    datum: str
    calibration_note: str
    commissioned_at: datetime | None


class StationEvent(BaseModel):
    id: int
    action: str
    actor: str
    reason: str
    created_at: datetime


class StationWorkspace(BaseModel):
    station_id: str
    checked_at: datetime
    identity: IdentityEvidence | None
    latest_sample: SampleEvidence | None
    last_valid: SampleEvidence | None
    latest_received: SampleEvidence | None
    events: list[StationEvent]
    total: int
    has_more: bool
