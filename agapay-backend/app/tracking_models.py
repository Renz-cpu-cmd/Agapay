"""Migration 0010: operator-phone station tracking (portable station position).

A station can be carried between sites. While an administrator-granted tracking session is
active, one named resident phone account reports GPS fixes for that station. Fixes are
stored here only: they never overwrite the registry coordinates, the commissioned identity,
the installation configuration or operational eligibility. Moving a station does not
re-validate its depth datum or thresholds.

The phone travels with the person carrying it, so a live position is personal location
data: it is exposed to staff only, and only fixes made during an explicit session are kept.
"""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import sqlite_bigint, utc_now

MAX_ACCURACY_M = 50.0          # coarser fixes are rejected, not stored
MAX_FIX_AGE_SECONDS = 60       # stale fixes are rejected
MAX_FUTURE_SKEW_SECONDS = 5
MIN_INTERVAL_SECONDS = 2.0     # per session
LIVE_FRESH_SECONDS = 30        # a fix older than this is "last known", not live
MAX_SESSION_MINUTES = 720


class StationTrackingSession(Base):
    __tablename__ = 'station_tracking_sessions'
    __table_args__ = (
        CheckConstraint('expires_at > created_at', name='ck_station_tracking_session_window'),
        Index('ix_station_tracking_sessions_station', 'station_id', 'created_at'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    station_id: Mapped[str] = mapped_column(ForeignKey('stations.station_id'))
    tracker_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class StationTrackedPosition(Base):
    __tablename__ = 'station_tracked_positions'
    __table_args__ = (
        CheckConstraint('latitude >= -90 AND latitude <= 90', name='ck_station_tracked_latitude'),
        CheckConstraint('longitude >= -180 AND longitude <= 180', name='ck_station_tracked_longitude'),
        CheckConstraint('accuracy_m > 0 AND accuracy_m <= 50', name='ck_station_tracked_accuracy'),
        Index('ix_station_tracked_positions_station', 'station_id', 'captured_at'),
        Index('ix_station_tracked_positions_session', 'session_id', 'captured_at'),
    )
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('station_tracking_sessions.id'))
    station_id: Mapped[str] = mapped_column(ForeignKey('stations.station_id'))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
