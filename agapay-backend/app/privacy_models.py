"""Minimal case/retention evidence. No passwords, coordinates or request narratives."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Boolean, event
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import utc_now, sqlite_bigint


class PrivacyCase(Base):
    __tablename__ = 'privacy_cases'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(24), default='OPEN')
    decision_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PrivacyHold(Base):
    __tablename__ = 'privacy_holds'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str] = mapped_column(String(40))
    evidence_sha256: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))


class PrivacyEvent(Base):
    __tablename__ = 'privacy_events'
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_id: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RecoveryFence(Base):
    __tablename__ = 'recovery_fences'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(24))
    backup_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


@event.listens_for(PrivacyEvent, 'before_update')
@event.listens_for(PrivacyEvent, 'before_delete')
def immutable_privacy_event(*_):
    raise ValueError('Privacy evidence is append-only')


TABLES = [PrivacyCase.__table__, PrivacyHold.__table__, PrivacyEvent.__table__, RecoveryFence.__table__]
