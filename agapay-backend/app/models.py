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
    JSON,
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
        Index("ix_telemetry_station_measured_id", "station_id", "measured_at", "id"),
        UniqueConstraint(
            "station_id", "config_version", "boot_id", "sequence_no", name="uq_telemetry_boot_sequence"
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
    boot_id: Mapped[str] = mapped_column(String(80), default="legacy", server_default="legacy")
    boot_sequence: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    config_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    source_id: Mapped[str] = mapped_column(String(80), default="legacy", server_default="legacy")
    firmware_version: Mapped[str] = mapped_column(String(50), default="legacy", server_default="legacy")
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    eligible_for_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    disposition: Mapped[str] = mapped_column(String(40), default="legacy", server_default="legacy")
    water_depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_interval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applied_config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sensor_fault: Mapped[str] = mapped_column(String(40), default="none", server_default="none")
    local_alert_profile: Mapped[str] = mapped_column(String(30), default="depth", server_default="depth")
    sensor_quality: Mapped[str] = mapped_column(String(20))
    device_uptime_ms: Mapped[int] = mapped_column(BigInteger)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class TelemetryBoot(Base):
    """Persisted device boot ordinal; retired boots never become current again."""
    __tablename__ = "telemetry_boots"
    __table_args__ = (UniqueConstraint("station_id", "config_version", "boot_sequence",
                                     name="uq_telemetry_boot_ordinal"),)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), primary_key=True)
    config_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    boot_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    boot_sequence: Mapped[int] = mapped_column(BigInteger)
    highest_sequence: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    highest_uptime_ms: Mapped[int] = mapped_column(BigInteger, default=-1, server_default="-1")


class StationTelemetryState(Base):
    """One cursor per station, modified under the parent station write lock."""
    __tablename__ = "station_telemetry_state"
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), primary_key=True)
    config_version: Mapped[int] = mapped_column(Integer)
    boot_id: Mapped[str] = mapped_column(String(80))
    boot_sequence: Mapped[int] = mapped_column(BigInteger)
    sequence_no: Mapped[int] = mapped_column(BigInteger)
    device_uptime_ms: Mapped[int] = mapped_column(BigInteger)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latest_telemetry_id: Mapped[int] = mapped_column(ForeignKey("telemetry.id"))


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
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid4()))
    audience: Mapped[str] = mapped_column(String(12), default="legacy", server_default="legacy")
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class StationIdentity(Base):
    """Explicit commissioning; existing station rows are never implicitly trusted."""
    __tablename__ = "station_identities"
    __table_args__ = (CheckConstraint(
        "state IN ('pending', 'commissioned', 'decommissioned')", name="ck_station_identity_state"),)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(80), unique=True)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    coordinates_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    reference_datum: Mapped[str] = mapped_column(String(200))
    calibration_note: Mapped[str] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, default=1)
    commissioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StationCredential(Base):
    __tablename__ = "station_credentials"
    __table_args__ = (CheckConstraint("transport IN ('http', 'mqtt', 'both')", name="ck_station_credential_transport"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    station_id: Mapped[str] = mapped_column(ForeignKey("station_identities.station_id"), index=True)
    identity_version: Mapped[int] = mapped_column(Integer)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    transport: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StationAuditEvent(Base):
    __tablename__ = "station_audit_events"
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    actor_name: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class StationIngressBudget(Base):
    """Shared fixed-minute attempt budgets, serialized by the parent station lock."""
    __tablename__ = "station_ingress_budgets"
    station_id: Mapped[str] = mapped_column(ForeignKey("station_identities.station_id"), primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class StationSourceRegistry(Base):
    """Admin-reviewed source designation, immutable for a commissioning version."""
    __tablename__ = "station_source_registry"
    __table_args__ = (
        CheckConstraint("source_class IN ('physical_device', 'simulator', 'unverified')", name="ck_registry_source"),
        CheckConstraint("stream IN ('operational', 'exercise')", name="ck_registry_stream"),
        CheckConstraint("stream = 'exercise' OR source_class = 'physical_device'", name="ck_registry_operational"),
    )
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), primary_key=True)
    config_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(80))
    source_class: Mapped[str] = mapped_column(String(30))
    stream: Mapped[str] = mapped_column(String(20))
    evidence: Mapped[str] = mapped_column(String(1000))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TelemetryProvenance(Base):
    __tablename__ = "telemetry_provenance"
    telemetry_id: Mapped[int] = mapped_column(ForeignKey("telemetry.id"), primary_key=True)
    credential_id: Mapped[str] = mapped_column(ForeignKey("station_credentials.id"))
    ingress_transport: Mapped[str] = mapped_column(String(10))
    ingress_identity: Mapped[str] = mapped_column(String(80))
    source_class: Mapped[str] = mapped_column(String(30))
    stream: Mapped[str] = mapped_column(String(20))
    registry_version: Mapped[int] = mapped_column(Integer)


class ExerciseTelemetry(Base):
    """Exercise data cannot be referenced by operational alerts or cursors."""
    __tablename__ = "exercise_telemetry"
    __table_args__ = (UniqueConstraint("station_id", "config_version", "boot_id", "sequence_no",
                                     name="uq_exercise_boot_sequence"),)
    id: Mapped[int] = mapped_column(sqlite_bigint, primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), index=True)
    config_version: Mapped[int] = mapped_column(Integer)
    boot_id: Mapped[str] = mapped_column(String(80))
    boot_sequence: Mapped[int] = mapped_column(BigInteger)
    sequence_no: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict] = mapped_column(JSON)
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    credential_id: Mapped[str] = mapped_column(ForeignKey("station_credentials.id"))
    ingress_transport: Mapped[str] = mapped_column(String(10))
    ingress_identity: Mapped[str] = mapped_column(String(80))
    source_class: Mapped[str] = mapped_column(String(30))


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
    # Authorization provenance for explicit revocation, NOT an eligibility lease.
    # No FK: naturally expired API sessions may be pruned without revoking push.
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
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
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
