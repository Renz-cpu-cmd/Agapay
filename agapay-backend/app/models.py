from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
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
