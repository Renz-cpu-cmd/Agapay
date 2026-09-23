from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


sqlite_bigint = BigInteger().with_variant(Integer, "sqlite")


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance')",
            name="ck_station_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    station_name: Mapped[str] = mapped_column(String(255))
    barangay: Mapped[str | None] = mapped_column(String(255), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    sensor_height_cm: Mapped[float] = mapped_column(Float, default=120.0)
    threshold_advisory_cm: Mapped[float] = mapped_column(Float, default=60.0)
    threshold_warning_cm: Mapped[float] = mapped_column(Float, default=85.0)
    threshold_evacuate_cm: Mapped[float] = mapped_column(Float, default=100.0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_ping: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        UniqueConstraint(
            "station_id", "sequence_no", name="uq_telemetry_station_sequence"
        ),
        CheckConstraint(
            "sensor_quality IN ('valid', 'invalid')",
            name="ck_telemetry_sensor_quality",
        ),
    )

    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    station_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("stations.station_id"), index=True
    )
    sequence_no: Mapped[int] = mapped_column(BigInteger)
    water_depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_mm: Mapped[float] = mapped_column(Float, default=0.0)
    sensor_quality: Mapped[str] = mapped_column(String(20))
    device_uptime_ms: Mapped[int] = mapped_column(BigInteger)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class Alert(Base):
    """One continuous sensor flood episode, including recovery to NORMAL."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("source = 'sensor'", name="ck_alert_source"),
        CheckConstraint("current_severity IN ('NORMAL', 'ADVISORY', 'WARNING', 'EVACUATE')", name="ck_alert_severity"),
        CheckConstraint("highest_severity IN ('ADVISORY', 'WARNING', 'EVACUATE')", name="ck_alert_highest_severity"),
        CheckConstraint(
            "(status = 'ACTIVE' AND current_severity <> 'NORMAL' AND resolved_at IS NULL) OR "
            "(status = 'RESOLVED' AND current_severity = 'NORMAL' AND resolved_at IS NOT NULL)",
            name="ck_alert_lifecycle",
        ),
        Index("ix_alert_station_status", "station_id", "status"),
        Index("ix_alert_status_triggered", "status", "triggered_at"),
        Index(
            "uq_alert_active_station", "station_id", unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    station_id: Mapped[str] = mapped_column(String(50), ForeignKey("stations.station_id"))
    current_severity: Mapped[str] = mapped_column(String(20))
    highest_severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    source: Mapped[str] = mapped_column(String(20), default="sensor")
    trigger_telemetry_id: Mapped[int] = mapped_column(ForeignKey("telemetry.id"), unique=True)
    latest_telemetry_id: Mapped[int] = mapped_column(ForeignKey("telemetry.id"))
    trigger_sequence_no: Mapped[int] = mapped_column(BigInteger)
    latest_sequence_no: Mapped[int] = mapped_column(BigInteger)
    trigger_depth_cm: Mapped[float] = mapped_column(Float)
    latest_depth_cm: Mapped[float] = mapped_column(Float)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_transition_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertTransition(Base):
    __tablename__ = "alert_transitions"
    __table_args__ = (
        CheckConstraint("previous_severity IN ('NORMAL', 'ADVISORY', 'WARNING', 'EVACUATE')", name="ck_transition_previous"),
        CheckConstraint("new_severity IN ('NORMAL', 'ADVISORY', 'WARNING', 'EVACUATE')", name="ck_transition_new"),
        CheckConstraint("previous_severity <> new_severity", name="ck_transition_changed"),
        Index("ix_alert_transition_history", "alert_id", "id"),
    )

    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"))
    station_id: Mapped[str] = mapped_column(String(50), ForeignKey("stations.station_id"), index=True)
    # A persisted sample can cause at most one flood transition, even on retry.
    telemetry_id: Mapped[int] = mapped_column(ForeignKey("telemetry.id"), unique=True)
    sequence_no: Mapped[int] = mapped_column(BigInteger)
    previous_severity: Mapped[str] = mapped_column(String(20))
    new_severity: Mapped[str] = mapped_column(String(20))
    water_depth_cm: Mapped[float] = mapped_column(Float)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'officer', 'resident')", name="ck_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(30), default="")
    barangay: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(20), default="resident")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AdministratorSetup(Base):
    __tablename__ = "administrator_setup"
    __table_args__ = (CheckConstraint("id = 1", name="ck_single_administrator_setup"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NotificationDevice(Base):
    __tablename__ = "notification_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "installation_id", name="uq_notification_installation"),
        CheckConstraint("platform IN ('android', 'ios')", name="ck_notification_platform"),
        CheckConstraint("provider = 'fcm'", name="ck_notification_provider"),
        CheckConstraint("NOT enabled OR (provider_token IS NOT NULL AND token_hash IS NOT NULL)", name="ck_notification_token"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    installation_id: Mapped[str] = mapped_column(String(36))
    platform: Mapped[str] = mapped_column(String(10))
    provider: Mapped[str] = mapped_column(String(10), default="fcm")
    provider_token: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    # Deliberately not a FK: revoked/expired sessions may be deleted. Delivery
    # requires a still-valid session, so logout also protects failed cleanup.
    session_hash: Mapped[str] = mapped_column(String(64), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NotificationEvent(Base):
    """Durable intent, including transitions with zero eligible recipients."""
    __tablename__ = "notification_events"
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    transition_id: Mapped[int] = mapped_column(ForeignKey("alert_transitions.id"), unique=True)
    notification_type: Mapped[str] = mapped_column(String(30), default="SENSOR_ESCALATION")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("event_id", "device_id", name="uq_notification_event_device"),
        CheckConstraint("state IN ('PENDING', 'PROCESSING', 'SENT', 'FAILED', 'SUPPRESSED', 'TESTED', 'UNKNOWN')", name="ck_notification_delivery_state"),
        Index("ix_notification_pending", "state", "next_attempt_at"),
    )
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("notification_events.id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("notification_devices.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    device_revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    result_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SosRequest(Base):
    __tablename__ = "sos_requests"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_sos_resident_request"),
        CheckConstraint("status IN ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED')", name="ck_sos_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    payload_hash: Mapped[str] = mapped_column(String(64))
    resident_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30))
    barangay: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(300))
    message: Mapped[str] = mapped_column(String(1000), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_source: Mapped[str] = mapped_column(String(20))
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    practice: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
