"""Exercise response records are segregated from any future operational dispatch."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import utc_now, sqlite_bigint


class SosDrillPolicy(Base):
    __tablename__ = 'sos_drill_policies'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    settings: Mapped[dict] = mapped_column(JSON)
    reviewed_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SosDrillIncident(Base):
    __tablename__ = 'sos_drill_incidents'
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    correlation_reason: Mapped[str] = mapped_column(String(500))
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SosDrillResponse(Base):
    __tablename__ = 'sos_drill_responses'
    sos_id: Mapped[int] = mapped_column(ForeignKey('sos_requests.id'), primary_key=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    policy: Mapped[dict] = mapped_column(JSON)
    coordinator_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    phase: Mapped[str] = mapped_column(String(24), default='UNASSIGNED')
    attention: Mapped[str] = mapped_column(String(24), default='normal')
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    attempted_users: Mapped[list] = mapped_column(JSON, default=list)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey('sos_drill_incidents.id'), nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)


class SosResponseEvent(Base):
    __tablename__ = 'sos_response_events'
    __table_args__ = (UniqueConstraint('sos_id', 'request_version', name='uq_sos_response_event_version'),)
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    sos_id: Mapped[int] = mapped_column(ForeignKey('sos_requests.id'), index=True)
    request_version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_name: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict] = mapped_column(JSON)
    resident_message: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


@event.listens_for(SosResponseEvent, 'before_update')
@event.listens_for(SosResponseEvent, 'before_delete')
def immutable_event(*_):
    raise ValueError('SOS response events are append-only')


TABLES = [SosDrillPolicy.__table__, SosDrillIncident.__table__, SosDrillResponse.__table__, SosResponseEvent.__table__]
