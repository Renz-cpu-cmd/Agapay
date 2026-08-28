from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
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
