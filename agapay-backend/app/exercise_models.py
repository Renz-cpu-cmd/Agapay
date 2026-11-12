"""Isolated exercise (test) notification records. Never operational alert/outbox tables.

Every row here is EXERCISE_TEST evidence for a bounded, administrator-authorized session
with an explicit device allowlist. Nothing in these tables can create a flood episode,
an operational NotificationEvent/NotificationDelivery, an advisory or an SOS action.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import utc_now

EXERCISE_TYPE = "EXERCISE_TEST"
DELIVERY_STATES = ("PENDING", "PROCESSING", "TESTED", "SENT", "REJECTED", "SUPPRESSED", "UNKNOWN")


class ExerciseConsent(Base):
    """The device owner's own opt-in for this registration revision."""
    __tablename__ = "exercise_device_consents"
    device_id: Mapped[str] = mapped_column(ForeignKey("notification_devices.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    device_revision: Mapped[int] = mapped_column(Integer)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExerciseSession(Base):
    __tablename__ = "exercise_sessions"
    __table_args__ = (CheckConstraint("max_sends >= 1 AND max_sends <= 50", name="ck_exercise_max_sends"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    max_sends: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ExerciseRecipient(Base):
    """Explicit per-session allowlist entry, pinned to the device registration revision."""
    __tablename__ = "exercise_recipients"
    session_id: Mapped[str] = mapped_column(ForeignKey("exercise_sessions.id"), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("notification_devices.id"), primary_key=True)
    device_revision: Mapped[int] = mapped_column(Integer)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExerciseDelivery(Base):
    __tablename__ = "exercise_deliveries"
    __table_args__ = (
        UniqueConstraint("session_id", "idempotency_key", name="uq_exercise_idempotency"),
        CheckConstraint("message_type = 'EXERCISE_TEST'", name="ck_exercise_type"),
        CheckConstraint("trigger_kind = 'manual'", name="ck_exercise_trigger"),
        CheckConstraint("state IN ('PENDING','PROCESSING','TESTED','SENT','REJECTED','SUPPRESSED','UNKNOWN')",
                        name="ck_exercise_state"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("exercise_sessions.id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("notification_devices.id"), index=True)
    device_revision: Mapped[int] = mapped_column(Integer)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    message_type: Mapped[str] = mapped_column(String(20), default=EXERCISE_TYPE)
    trigger_kind: Mapped[str] = mapped_column(String(16), default="manual")
    state: Mapped[str] = mapped_column(String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --- Migration 0007: sensor-triggered exercise records (separate from manual 0006) ---------

TIER_RANK_SQL = ("CASE {col} WHEN 'NORMAL' THEN 0 WHEN 'ADVISORY' THEN 1 "
                 "WHEN 'WARNING' THEN 2 WHEN 'EVACUATE' THEN 3 END")


class ExerciseStationArm(Base):
    """An administrator armed one station for one exercise session. The baseline is the
    station's tier at arming (NULL = unknown, so the next valid sample only sets it)."""
    __tablename__ = "exercise_station_arms"
    __table_args__ = (
        CheckConstraint("previous_tier IS NULL OR previous_tier IN ('NORMAL','ADVISORY','WARNING','EVACUATE')",
                        name="ck_exercise_arm_tier"),
        CheckConstraint("baseline_tier IS NULL OR baseline_tier IN ('NORMAL','ADVISORY','WARNING','EVACUATE')",
                        name="ck_exercise_arm_baseline"),
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("exercise_sessions.id"), primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), primary_key=True)
    armed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    armed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    baseline_tier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    baseline_telemetry_id: Mapped[int | None] = mapped_column(ForeignKey("telemetry.id"), nullable=True)
    previous_tier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cursor_telemetry_id: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    disarmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExerciseSensorTrigger(Base):
    """One observed upward tier change of an armed station, tied to its exact committed
    telemetry row and the authenticated ingress evidence recorded for it."""
    __tablename__ = "exercise_sensor_triggers"
    __table_args__ = (
        UniqueConstraint("session_id", "station_id", "current_tier", name="uq_exercise_trigger_tier"),
        UniqueConstraint("session_id", "telemetry_id", name="uq_exercise_trigger_telemetry"),
        CheckConstraint("previous_tier IN ('NORMAL','ADVISORY','WARNING','EVACUATE')", name="ck_exercise_trigger_previous"),
        CheckConstraint("current_tier IN ('ADVISORY','WARNING','EVACUATE')", name="ck_exercise_trigger_current"),
        CheckConstraint(f"{TIER_RANK_SQL.format(col='current_tier')} > {TIER_RANK_SQL.format(col='previous_tier')}",
                        name="ck_exercise_trigger_upward"),
        CheckConstraint("reason = 'observed_tier_increase'", name="ck_exercise_trigger_reason"),
        CheckConstraint("status IN ('DELIVERIES_CREATED','NO_RECIPIENTS','SEND_LIMIT')", name="ck_exercise_trigger_status"),
        CheckConstraint("source_class = 'physical_device'", name="ck_exercise_trigger_source"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("exercise_sessions.id"), index=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"))
    telemetry_id: Mapped[int] = mapped_column(ForeignKey("telemetry.id"))
    # Copied ingress evidence (the provenance row is keyed by telemetry_id).
    source_class: Mapped[str] = mapped_column(String(30))
    ingress_identity: Mapped[str] = mapped_column(String(80))
    ingress_transport: Mapped[str] = mapped_column(String(10))
    registry_version: Mapped[int] = mapped_column(Integer)
    credential_id: Mapped[str] = mapped_column(String(36))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    water_depth_cm: Mapped[float] = mapped_column(Float)
    previous_tier: Mapped[str] = mapped_column(String(10))
    current_tier: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(String(40), default="observed_tier_increase")
    status: Mapped[str] = mapped_column(String(20))


class ExerciseSensorDelivery(Base):
    __tablename__ = "exercise_sensor_deliveries"
    __table_args__ = (
        UniqueConstraint("trigger_id", "device_id", name="uq_exercise_sensor_delivery"),
        CheckConstraint("message_type = 'EXERCISE_TEST'", name="ck_exercise_sensor_type"),
        CheckConstraint("state IN ('PENDING','PROCESSING','TESTED','SENT','REJECTED','SUPPRESSED','UNKNOWN')",
                        name="ck_exercise_sensor_state"),
        CheckConstraint("attempts >= 0 AND attempts <= 1", name="ck_exercise_sensor_single_attempt"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trigger_id: Mapped[str] = mapped_column(ForeignKey("exercise_sensor_triggers.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("exercise_sessions.id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("notification_devices.id"), index=True)
    device_revision: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    message_type: Mapped[str] = mapped_column(String(20), default=EXERCISE_TYPE)
    state: Mapped[str] = mapped_column(String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


SENSOR_TABLES = (ExerciseSensorDelivery.__table__, ExerciseSensorTrigger.__table__, ExerciseStationArm.__table__)
# Dependency order for disposable-test cleanup (children first).
TABLES = SENSOR_TABLES + (ExerciseDelivery.__table__, ExerciseRecipient.__table__, ExerciseSession.__table__,
                          ExerciseConsent.__table__)
