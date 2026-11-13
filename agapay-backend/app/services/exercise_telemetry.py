"""Isolated exercise stream: no operational cursor, heartbeat, alert or outbox."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.models import ExerciseTelemetry
from app.schemas import TelemetryRead
from app.services.ingress_provenance import trusted_ingress
from app.services.station_security import lock_station
from app.services.telemetry_service import DuplicateTelemetryError, ConflictingTelemetryError, utc, MAX_FUTURE_SKEW_SECONDS


def ingest_exercise(db, payload, *, credential_id, transport):
    try:
        lock_station(db, payload.station_id)
        context = trusted_ingress(db, payload.station_id, payload.config_version, payload.source_id,
                                  credential_id, transport, "exercise")
        measured = utc(payload.measured_at)
        normalized = payload.model_copy(update={"measured_at": measured}).model_dump(mode="json")
        existing = db.scalar(select(ExerciseTelemetry).where(
            ExerciseTelemetry.station_id == payload.station_id, ExerciseTelemetry.config_version == payload.config_version,
            ExerciseTelemetry.boot_id == payload.boot_id, ExerciseTelemetry.sequence_no == payload.sequence_no))
        if existing:
            if existing.payload == normalized:
                raise DuplicateTelemetryError("Duplicate telemetry: exact retry")
            raise ConflictingTelemetryError("Conflicting telemetry: exercise sample key reused")
        now = datetime.now(timezone.utc)
        if measured and measured > now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
            raise HTTPException(422, "Measurement time is too far in the future.")
        row = ExerciseTelemetry(station_id=payload.station_id, config_version=payload.config_version,
            boot_id=payload.boot_id, boot_sequence=payload.boot_sequence, sequence_no=payload.sequence_no,
            payload=normalized, measured_at=measured, received_at=now,
            **{k: v for k, v in context.items() if k not in ("stream", "registry_version")})
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise


def exercise_read(row):
    return TelemetryRead.model_validate({**row.payload, "id": row.id, "received_at": row.received_at,
        "recorded_at": row.measured_at or row.received_at, "eligible_for_current": False, "disposition": "exercise",
        "stream": "exercise", "source_class": row.source_class, "source_trusted": False,
        "ingress_identity": row.ingress_identity, "ingress_transport": row.ingress_transport})


def exercise_history(db, station_id, limit):
    return list(db.scalars(select(ExerciseTelemetry).where(ExerciseTelemetry.station_id == station_id)
        .order_by(ExerciseTelemetry.config_version.desc(), ExerciseTelemetry.boot_sequence.desc(),
                  ExerciseTelemetry.sequence_no.desc(), ExerciseTelemetry.id.desc()).limit(limit)))
