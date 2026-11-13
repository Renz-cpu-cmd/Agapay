"""Bounded operational state; no personal data, credentials or measurement rewriting."""
from datetime import datetime
from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import utc_now


class WorkerHeartbeat(Base):
    __tablename__='worker_heartbeats'
    role:Mapped[str]=mapped_column(String(32),primary_key=True)
    state:Mapped[str]=mapped_column(String(16))
    observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
    last_success_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    detail:Mapped[str]=mapped_column(String(64),default='')


class MetricBucket(Base):
    __tablename__='workflow_metric_buckets'
    __table_args__=(Index('ix_workflow_metric_minute','minute'),)
    metric:Mapped[str]=mapped_column(String(48),primary_key=True)
    minute:Mapped[int]=mapped_column(Integer,primary_key=True)
    count:Mapped[int]=mapped_column(Integer,default=0)
    failures:Mapped[int]=mapped_column(Integer,default=0)
    total_seconds:Mapped[float]=mapped_column(Float,default=0)
    maximum_seconds:Mapped[float]=mapped_column(Float,default=0)
    histogram:Mapped[dict]=mapped_column(JSON,default=dict)


class SharedReadModel(Base):
    __tablename__='shared_read_models'
    key:Mapped[str]=mapped_column(String(80),primary_key=True)
    generation:Mapped[str]=mapped_column(String(64),default='')
    payload:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    checked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    lease_token:Mapped[str|None]=mapped_column(String(36),nullable=True)
    lease_until:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


class OperatorAlert(Base):
    __tablename__='operator_alerts'
    code:Mapped[str]=mapped_column(String(64),primary_key=True)
    severity:Mapped[str]=mapped_column(String(16))
    message:Mapped[str]=mapped_column(Text)
    first_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
    last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


TABLES=[WorkerHeartbeat.__table__,MetricBucket.__table__,SharedReadModel.__table__,OperatorAlert.__table__]
