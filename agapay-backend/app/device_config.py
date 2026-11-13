"""Versioned installation configuration. Mathematical checks are not field validation."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from fastapi import HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import ForeignKey, Integer, String, JSON, DateTime, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import utc_now


class Installation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    datum: str = Field(min_length=3,max_length=200)
    installation_height_cm: float = Field(gt=0,le=1000)
    sensor_min_cm: float = Field(gt=0,le=1000)
    sensor_max_cm: float = Field(gt=0,le=1000)
    uncertainty_cm: float = Field(gt=0,le=100)
    range_margin_cm: float = Field(gt=0,le=100)
    advisory_cm: float = Field(ge=0,le=1000)
    warning_cm: float = Field(ge=0,le=1000)
    critical_cm: float = Field(ge=0,le=1000)
    rain_mm_per_tip: float = Field(gt=0,le=100)
    fault_policy: Literal["latch_hazard_signal_fault"] = "latch_hazard_signal_fault"

    @model_validator(mode="after")
    def reachable(self):
        if not self.advisory_cm < self.warning_cm < self.critical_cm:
            raise ValueError("Thresholds must be strictly ordered")
        reserve=self.range_margin_cm+self.uncertainty_cm
        if not self.sensor_min_cm+reserve <= self.installation_height_cm-self.critical_cm:
            raise ValueError("Critical tier lacks reliable near-range margin including uncertainty; review installation geometry")
        if not self.installation_height_cm <= self.sensor_max_cm-reserve:
            raise ValueError("Zero-depth datum lacks far-range margin including uncertainty")
        return self


class ConfigurationRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    expected_revision:int=Field(ge=0)
    installation:Installation
    validation_status:Literal["prototype","bench_reviewed","field_reviewed"]="prototype"
    evidence:str=Field(min_length=10,max_length=2000)
    reason:str=Field(min_length=3,max_length=500)
    effective_at:AwareDatetime


class StationConfiguration(Base):
    __tablename__="station_configurations"
    __table_args__=(UniqueConstraint("station_id","revision"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    station_id:Mapped[str]=mapped_column(ForeignKey("stations.station_id"),index=True)
    revision:Mapped[int]=mapped_column(Integer)
    config_hash:Mapped[str]=mapped_column(String(64))
    installation:Mapped[dict]=mapped_column(JSON)
    validation_status:Mapped[str]=mapped_column(String(30))
    evidence:Mapped[str]=mapped_column(String(2000))
    reason:Mapped[str]=mapped_column(String(500))
    reviewer_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    effective_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)


def configuration_hash(station_id,revision,installation):
    body=dict(station_id=station_id,revision=revision,installation=installation)
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def current_configuration(db,station_id):
    return db.scalar(select(StationConfiguration).where(StationConfiguration.station_id==station_id).order_by(StationConfiguration.revision.desc()).limit(1))


# The single review status that may drive production-authoritative sensor actions.
# Forecast publication already requires the same status (services/forecast_registry.py).
OPERATIONAL_VALIDATION="field_reviewed"


def operational_review_required(settings=None):
    """Default-deny and fail closed.

    Review is required unless ALL of these hold: not production, the setting was
    explicitly turned off, and no external notification provider is configured. So
    turning the setting off can never let an unreviewed station reach a real phone.
    """
    if settings is None:
        from app.config import get_settings
        settings=get_settings()
    relaxed=(settings.environment!="production" and settings.operational_review_required is False
             and settings.notification_provider=="disabled")
    return not relaxed


_LOAD=object()  # sentinel: "not supplied; read it" (None means "no configuration")


def operational_eligibility(db,station_id,configuration=_LOAD):
    """Return (eligible, reason) for resident push, operational queue and citywide dispatch.

    Never used to discard telemetry, hazard decisions or incidents: ineligible stations
    keep measuring, deciding and recording; only external/operational actions are withheld.
    """
    if not operational_review_required():
        return True,"review_not_required"
    if configuration is _LOAD:
        configuration=current_configuration(db,station_id)
    if configuration is None:
        return False,"configuration_missing"
    if configuration.validation_status!=OPERATIONAL_VALIDATION:
        return False,"configuration_"+configuration.validation_status
    return True,OPERATIONAL_VALIDATION


def configuration_contract(row, applied=None):
    return dict(station_id=row.station_id,revision=row.revision,config_hash=row.config_hash,
        installation=row.installation,validation_status=row.validation_status,evidence=row.evidence,
        reviewer_id=row.reviewer_id,effective_at=row.effective_at.replace(tzinfo=timezone.utc) if row.effective_at.tzinfo is None else row.effective_at,
        applied_config_hash=applied,status="matched" if applied==row.config_hash else "missing" if not applied else "mismatch")


def save_configuration(db,station,payload,admin):
    from app.services.station_security import audit
    previous=current_configuration(db,station.station_id)
    if payload.expected_revision != (previous.revision if previous else 0):
        raise HTTPException(409,"Installation configuration changed; refresh and review manually")
    now=utc_now()
    if abs((payload.effective_at-now).total_seconds()) > 300:
        raise HTTPException(422,"Apply configuration with a current effective time; historical or scheduled replacement is not supported")
    revision=payload.expected_revision+1
    installation=payload.installation.model_dump(mode="json")
    row=StationConfiguration(station_id=station.station_id,revision=revision,
        config_hash=configuration_hash(station.station_id,revision,installation),installation=installation,
        validation_status=payload.validation_status,evidence=payload.evidence,reason=payload.reason,
        reviewer_id=admin.id,effective_at=payload.effective_at)
    db.add(row)
    station.sensor_height_cm=installation['installation_height_cm']
    station.threshold_advisory_cm=installation['advisory_cm']
    station.threshold_warning_cm=installation['warning_cm']
    station.threshold_evacuate_cm=installation['critical_cm']
    audit(db,station,admin,"installation_configuration_changed",payload.reason,
          dict(revision=revision,config_hash=row.config_hash,installation=installation,validation_status=payload.validation_status,evidence=payload.evidence))
    db.flush()
    return row
