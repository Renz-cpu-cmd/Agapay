"""Migration 0008: restored-delivery recovery generations and holds (R2 P0).

A delivery may reach a provider only under the single ACTIVE generation, and never while
it is held. Holds record the state each delivery had when its outcome became unknowable
and are never released for resend: an operator decision closes a hold, it does not
re-queue it. Delivery rows themselves are never rewritten by recovery.
"""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import sqlite_bigint, utc_now


class DeliveryGeneration(Base):
    __tablename__ = 'delivery_generations'
    __table_args__ = (
        CheckConstraint("state IN ('RECOVERING','ACTIVE','SUPERSEDED')", name='ck_delivery_generation_state'),
        CheckConstraint("kind IN ('initialize','restore','declared')", name='ck_delivery_generation_kind'),
        CheckConstraint('claim_seq >= 0', name='ck_delivery_generation_claims'),
    )
    generation: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    token: Mapped[str] = mapped_column(String(36), unique=True)
    state: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(500))
    source_backup_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    database_identity: Mapped[str | None] = mapped_column(String(80), nullable=True)
    claim_seq: Mapped[int] = mapped_column(sqlite_bigint, default=0)
    held_count: Mapped[int] = mapped_column(Integer, default=0)
    declared_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    activated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeliveryHold(Base):
    __tablename__ = 'delivery_recovery_holds'
    __table_args__ = (
        UniqueConstraint('kind', 'delivery_id', name='uq_delivery_recovery_hold'),
        CheckConstraint("kind IN ('operational','exercise_manual','exercise_sensor')", name='ck_delivery_hold_kind'),
        CheckConstraint("decision IS NULL OR decision IN ('provider_accepted','not_delivered','outcome_unknown','superseded')",
                        name='ck_delivery_hold_decision'),
    )
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    generation: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(20))
    delivery_id: Mapped[str] = mapped_column(String(36))
    original_state: Mapped[str] = mapped_column(String(20))
    original_attempts: Mapped[int] = mapped_column(Integer)
    original_result: Mapped[str | None] = mapped_column(String(40), nullable=True)
    original_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    original_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(32))
    held_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    version: Mapped[int] = mapped_column(Integer, default=1)
    decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    evidence_kind: Mapped[str | None] = mapped_column(String(24), nullable=True)
    evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeliveryRecoveryEvent(Base):
    __tablename__ = 'delivery_recovery_events'
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    generation: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


@event.listens_for(DeliveryRecoveryEvent, 'before_update')
@event.listens_for(DeliveryRecoveryEvent, 'before_delete')
def immutable_recovery_event(*_):
    raise ValueError('Delivery recovery evidence is append-only')


TABLES = [DeliveryGeneration.__table__, DeliveryHold.__table__, DeliveryRecoveryEvent.__table__]
