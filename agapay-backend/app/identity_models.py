"""Durable identity workflows; secrets are hashed or encrypted, never audited raw."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, event, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import utc_now, sqlite_bigint


class MutationAudit(Base):
    __tablename__ = 'mutation_audit'
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_label: Mapped[str] = mapped_column(String(160))
    subject_type: Mapped[str] = mapped_column(String(40), index=True)
    subject_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(1000))
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


@event.listens_for(MutationAudit, 'before_update')
@event.listens_for(MutationAudit, 'before_delete')
def immutable_audit(*_):
    raise ValueError('Mutation audit events are append-only')


class AuthBudget(Base):
    __tablename__ = 'auth_budgets'
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    reset_at: Mapped[int] = mapped_column(Integer, index=True)


class IdentityAction(Base):
    __tablename__ = 'identity_actions'
    __table_args__=(Index("ix_identity_open_invitation", "email", unique=True,
        sqlite_where=text("purpose = 'invitation' AND used_at IS NULL"),
        postgresql_where=text("purpose = 'invitation' AND used_at IS NULL")),)
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(30), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    account_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MfaCredential(Base):
    __tablename__ = 'mfa_credentials'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    secret_ciphertext: Mapped[str] = mapped_column(Text)
    last_step: Mapped[int] = mapped_column(Integer, default=-1)
    enabled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MfaRecoveryCode(Base):
    __tablename__ = 'mfa_recovery_codes'
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdentityMail(Base):
    __tablename__ = 'identity_mail'
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    action_hash: Mapped[str] = mapped_column(ForeignKey('identity_actions.token_hash'))
    recipient: Mapped[str] = mapped_column(String(254))
    body_ciphertext: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(16), default='PENDING', index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


TABLES = [MutationAudit.__table__, AuthBudget.__table__, IdentityAction.__table__,
          MfaCredential.__table__, MfaRecoveryCode.__table__, IdentityMail.__table__]
