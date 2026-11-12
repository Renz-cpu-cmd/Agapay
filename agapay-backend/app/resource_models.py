"""Versioned authority-maintained resources; drafts never imply verified shelter access."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import utc_now, sqlite_bigint
from app.governance_models import AlertAuthority  # Register the issuer FK for fresh offline bootstrap.


class ResponseResource(Base):
    __tablename__ = 'response_resources'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    authority_id: Mapped[str] = mapped_column(ForeignKey('alert_authorities.id'), index=True)
    area_ids: Mapped[list] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(12), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(1200))
    verification: Mapped[str] = mapped_column(String(20), default='unverified')
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResourceRevision(Base):
    __tablename__ = 'resource_revisions'
    __table_args__ = (UniqueConstraint('resource_id','version',name='uq_resource_revision'),)
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey('response_resources.id'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


@event.listens_for(ResourceRevision,'before_update')
@event.listens_for(ResourceRevision,'before_delete')
def immutable(*_):
    raise ValueError('Resource revisions are append-only')


TABLES = [ResponseResource.__table__,ResourceRevision.__table__]
