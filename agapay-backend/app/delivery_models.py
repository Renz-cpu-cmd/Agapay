"""Delivery evidence is independent of transport state and alert/SOS authority."""
from datetime import datetime
from sqlalchemy import Boolean,CheckConstraint,DateTime,ForeignKey,ForeignKeyConstraint,Integer,String,Text,UniqueConstraint,event
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base
from app.models import sqlite_bigint,utc_now


class ReceiptConsent(Base):
    __tablename__='notification_receipt_consents'
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    version:Mapped[int]=mapped_column(Integer,default=0)
    enabled:Mapped[bool]=mapped_column(Boolean,default=False)


class DeliveryControl(Base):
    __tablename__='notification_delivery_controls'
    __table_args__=(CheckConstraint("review_status IN ('unreviewed','provider_accepted','not_accepted','closed_no_resend','followup_recorded')",name='ck_delivery_review'),)
    delivery_id:Mapped[int]=mapped_column(ForeignKey('notification_deliveries.id'),primary_key=True)
    version:Mapped[int]=mapped_column(Integer,default=1)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    review_status:Mapped[str]=mapped_column(String(24),default='unreviewed')
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


class DeliveryAttempt(Base):
    __tablename__='notification_delivery_attempts'
    delivery_id:Mapped[int]=mapped_column(ForeignKey('notification_deliveries.id'),primary_key=True)
    attempt_no:Mapped[int]=mapped_column(Integer,primary_key=True)
    device_revision:Mapped[int]=mapped_column(Integer)
    receipt_hash:Mapped[str|None]=mapped_column(String(64),unique=True,nullable=True)
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
    outcome:Mapped[str]=mapped_column(String(24),default='claimed')
    provider_reference:Mapped[str|None]=mapped_column(String(250),nullable=True)
    provider_reported_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


class DeliveryReceipt(Base):
    __tablename__='notification_delivery_receipts'
    __table_args__=(ForeignKeyConstraint(['delivery_id','attempt_no'],['notification_delivery_attempts.delivery_id','notification_delivery_attempts.attempt_no']),
        CheckConstraint("stage IN ('RECEIVED','OPENED','ACKNOWLEDGED')",name='ck_delivery_receipt_stage'))
    delivery_id:Mapped[int]=mapped_column(sqlite_bigint,primary_key=True)
    attempt_no:Mapped[int]=mapped_column(Integer,primary_key=True)
    stage:Mapped[str]=mapped_column(String(16),primary_key=True)
    basis:Mapped[str]=mapped_column(String(24))
    reported_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    recorded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)


class DeliveryReview(Base):
    __tablename__='notification_delivery_reviews'
    id:Mapped[int]=mapped_column(sqlite_bigint,primary_key=True)
    delivery_id:Mapped[int]=mapped_column(ForeignKey('notification_deliveries.id'),index=True)
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    expected_version:Mapped[int]=mapped_column(Integer)
    decision:Mapped[str]=mapped_column(String(24))
    evidence_kind:Mapped[str]=mapped_column(String(24))
    evidence_sha256:Mapped[str]=mapped_column(String(64))
    reason:Mapped[str]=mapped_column(String(500))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)


@event.listens_for(DeliveryReceipt,'before_update')
@event.listens_for(DeliveryReceipt,'before_delete')
@event.listens_for(DeliveryReview,'before_update')
@event.listens_for(DeliveryReview,'before_delete')
def immutable_evidence(*_):raise ValueError('Delivery evidence is append-only')


TABLES=[ReceiptConsent.__table__,DeliveryControl.__table__,DeliveryAttempt.__table__,DeliveryReceipt.__table__,DeliveryReview.__table__]
