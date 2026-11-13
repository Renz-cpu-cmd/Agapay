"""Additive hazard, authority and audience records. No inferred trust or membership."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import sqlite_bigint, utc_now


class HazardPolicy(Base):
    __tablename__ = "hazard_policies"
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    rules: Mapped[dict] = mapped_column(JSON)
    evidence: Mapped[str] = mapped_column(String(2000))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class HazardRecovery(Base):
    __tablename__ = "hazard_recovery"
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), primary_key=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(20))
    count: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HazardDecision(Base):
    __tablename__ = "hazard_decisions"
    telemetry_id: Mapped[int] = mapped_column(ForeignKey("telemetry.id"), primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), index=True)
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observation_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    episode_tier: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(100))
    review_required: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GovernanceAudit(Base):
    __tablename__ = "governance_audit"
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80), index=True)
    subject: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(1000))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class VerifiedArea(Base):
    __tablename__ = "verified_areas"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    identifier_scheme: Mapped[str] = mapped_column(String(80))
    area_class: Mapped[str] = mapped_column(String(20), default="geographic")
    evidence: Mapped[str] = mapped_column(String(2000))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class StationArea(Base):
    __tablename__ = "station_areas"
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), primary_key=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("verified_areas.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class AlertAuthority(Base):
    __tablename__ = "alert_authorities"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    evidence: Mapped[str] = mapped_column(String(2000))
    authority_class: Mapped[str] = mapped_column(String(20), default="app_operator")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthorityGrant(Base):
    __tablename__ = "authority_grants"
    authority_id: Mapped[str] = mapped_column(ForeignKey("alert_authorities.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    area_ids: Mapped[list] = mapped_column(JSON)
    station_ids: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    citywide: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ResidentSubscription(Base):
    __tablename__ = "resident_subscriptions"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    target_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OfficialNotice(Base):
    __tablename__ = "official_notices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    authority_id: Mapped[str] = mapped_column(ForeignKey("alert_authorities.id"), index=True)
    issuer_name: Mapped[str] = mapped_column(String(200))
    authority_class: Mapped[str] = mapped_column(String(20))
    issued_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    area_ids: Mapped[list] = mapped_column(JSON)
    area_names: Mapped[list] = mapped_column(JSON)
    message_type: Mapped[str] = mapped_column(String(10))
    reference_id: Mapped[str | None] = mapped_column(ForeignKey("official_notices.id"), nullable=True, unique=True)
    category: Mapped[str] = mapped_column(String(15))
    status: Mapped[str] = mapped_column(String(10))
    urgency: Mapped[str] = mapped_column(String(15))
    severity: Mapped[str] = mapped_column(String(15))
    certainty: Mapped[str] = mapped_column(String(15))
    headline: Mapped[str] = mapped_column(String(200))
    instruction: Mapped[str] = mapped_column(String(4000))
    reason: Mapped[str] = mapped_column(String(1000))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NotificationAudience(Base):
    __tablename__ = "notification_audiences"
    event_id: Mapped[int] = mapped_column(ForeignKey("notification_events.id"), primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"))
    area_ids: Mapped[list] = mapped_column(JSON)


class NotificationRecipient(Base):
    __tablename__ = "notification_recipients"
    delivery_id: Mapped[int] = mapped_column(ForeignKey("notification_deliveries.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    target_id: Mapped[str] = mapped_column(String(50))
    subscription_revision: Mapped[int] = mapped_column(Integer)
    area_binding_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CitywideDispatch(Base):
    __tablename__ = "citywide_dispatches"
    event_id: Mapped[int] = mapped_column(ForeignKey("notification_events.id"), primary_key=True)
    authority_id: Mapped[str] = mapped_column(ForeignKey("alert_authorities.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [model.__table__ for model in (
    HazardPolicy, HazardRecovery, HazardDecision, GovernanceAudit, VerifiedArea, StationArea,
    AlertAuthority, AuthorityGrant, ResidentSubscription, OfficialNotice,
    NotificationAudience, NotificationRecipient, CitywideDispatch,
)]
