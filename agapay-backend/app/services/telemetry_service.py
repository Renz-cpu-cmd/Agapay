"""Atomic measurement ordering shared by HTTP/MQTT; receipt is not measurement."""
from datetime import datetime, timedelta, timezone
import time

from fastapi import HTTPException
from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from app.models import Station, StationIdentity, StationTelemetryState, Telemetry, TelemetryBoot, TelemetryProvenance
from app.schemas import TelemetryCreate
from app.services.alert_service import process_sensor_alert
from app.services.ingress_provenance import trusted_ingress, provenance_fields

MAX_CURRENT_AGE_SECONDS = 120
MAX_FUTURE_SKEW_SECONDS = 5


class UnknownStationError(Exception):
    pass


class DuplicateTelemetryError(Exception):
    """Exact retry of a previously stored immutable measurement."""


class ConflictingTelemetryError(DuplicateTelemetryError):
    """An existing sample/boot key was reused with different content."""


def utc(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _same_payload(row: Telemetry, payload: TelemetryCreate) -> bool:
    return all(
        utc(getattr(row, key)) == utc(value) if key == "measured_at" else getattr(row, key) == value
        for key, value in payload.model_dump(mode="json",exclude={"measured_at"}).items()
    ) and utc(row.measured_at)==utc(payload.measured_at)


def ingest_telemetry(db: Session, payload: TelemetryCreate, *, credential_id: str | None = None,
                     transport: str = "http", historical: bool = False) -> Telemetry:
    try:
        # SQLite serializes writers; PostgreSQL locks this station row. Refresh
        # after waiting so an ORM identity map cannot hide another worker's cursor.
        locked = db.execute(update(Station).where(Station.station_id == payload.station_id)
                            .values(last_ping=Station.last_ping))
        if locked.rowcount != 1:
            raise UnknownStationError(payload.station_id)
        station = db.scalar(select(Station).where(Station.station_id == payload.station_id)
                            .execution_options(populate_existing=True))
        from app.services.station_lifecycle import ensure_ingestion_allowed
        ensure_ingestion_allowed(station)
        identity = db.get(StationIdentity, payload.station_id, populate_existing=True)
        if (identity is None or identity.state != "commissioned"
                or payload.config_version != identity.version or payload.source_id != identity.device_id):
            raise HTTPException(403, "Telemetry source/configuration does not match the commissioned device.")
        provenance = trusted_ingress(db, payload.station_id, payload.config_version, payload.source_id,
                                     credential_id, transport, "operational")
        from app.device_config import current_configuration
        configuration=current_configuration(db,payload.station_id)
        config_mismatch=(payload.schema_version==3 or configuration is not None) and (
            configuration is None or payload.applied_config_hash!=configuration.config_hash)
        if payload.rainfall_interval and configuration and payload.rainfall_interval.calibration_version!=configuration.config_hash:
            raise HTTPException(422,"Rainfall calibration version differs from reviewed configuration")
        if payload.rainfall_interval and configuration and abs(payload.rainfall_interval.mm_per_tip-configuration.installation['rain_mm_per_tip'])>1e-5:
            raise HTTPException(422,"Rainfall coefficient differs from reviewed configuration")

        existing = db.scalar(select(Telemetry).where(
            Telemetry.station_id == payload.station_id, Telemetry.config_version == payload.config_version,
            Telemetry.boot_id == payload.boot_id, Telemetry.sequence_no == payload.sequence_no))
        if existing is not None:
            error = DuplicateTelemetryError if _same_payload(existing, payload) else ConflictingTelemetryError
            raise error("Duplicate telemetry: exact retry" if error is DuplicateTelemetryError
                        else "Conflicting telemetry: sample key reused with different payload")

        now = datetime.now(timezone.utc)
        measured = utc(payload.measured_at)
        if measured is not None and measured > now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
            raise HTTPException(422, "Measurement time is too far in the future.")
        boot = db.get(TelemetryBoot, (payload.station_id, payload.config_version, payload.boot_id), populate_existing=True)
        ordinal = db.scalar(select(TelemetryBoot).where(
            TelemetryBoot.station_id == payload.station_id, TelemetryBoot.config_version == payload.config_version,
            TelemetryBoot.boot_sequence == payload.boot_sequence))
        if ((boot is not None and boot.boot_sequence != payload.boot_sequence)
                or (ordinal is not None and ordinal.boot_id != payload.boot_id)):
            raise ConflictingTelemetryError("Conflicting telemetry: boot identity/ordinal reused")
        if boot is None:
            boot = TelemetryBoot(station_id=payload.station_id, config_version=payload.config_version,
                                 boot_id=payload.boot_id, boot_sequence=payload.boot_sequence,
                                 highest_sequence=0, highest_uptime_ms=-1)
            db.add(boot)
            db.flush()
        newest_boot = db.scalar(select(TelemetryBoot.boot_sequence).where(
            TelemetryBoot.station_id == payload.station_id, TelemetryBoot.config_version == payload.config_version
        ).order_by(TelemetryBoot.boot_sequence.desc()).limit(1))
        state = db.get(StationTelemetryState, payload.station_id, populate_existing=True)
        disposition = "current"
        if payload.boot_sequence < newest_boot:
            disposition = "retired_boot"
        elif measured is None:
            disposition = "unsynchronized"
        elif (now - measured).total_seconds() > MAX_CURRENT_AGE_SECONDS:
            disposition = "stale_measurement"
        elif state is None and station.last_ping is not None and measured <= utc(station.last_ping):
            # At upgrade there is no measured-time cursor for legacy rows. The
            # preserved last receipt is a conservative floor, never a new clock.
            disposition = "pre_upgrade_measurement"
        elif state is not None:
            same_boot = (state.config_version == payload.config_version and state.boot_id == payload.boot_id)
            if measured <= utc(state.measured_at):
                disposition = "late_measurement"
            elif same_boot and (payload.sequence_no <= state.sequence_no
                                or payload.device_uptime_ms <= state.device_uptime_ms):
                disposition = "out_of_order"

        if disposition == "current" and (payload.sequence_no <= boot.highest_sequence
                                          or payload.device_uptime_ms <= boot.highest_uptime_ms):
            disposition = "out_of_order"
        if config_mismatch and disposition=="current":
            disposition="configuration_mismatch"
        if payload.local_alert_profile!="depth" and disposition=="current":
            disposition="exercise_local_outputs"
        # Explicit journal replay is historical even when measured seconds ago.
        # Receipt must never turn an outage backlog into a fresh hazard/heartbeat.
        if historical:
            disposition=("journal_configuration_mismatch" if config_mismatch else
                         "journal_exercise_local_outputs" if payload.local_alert_profile!="depth" else
                         "journal_backfill" if measured is not None else "journal_unsynchronized")
        # Advance transport-independent high-water marks even for historical
        # unsynchronized/stale traffic. A later lower sequence cannot become
        # current merely because its clock starts looking fresh.
        boot.highest_sequence = max(boot.highest_sequence, payload.sequence_no)
        boot.highest_uptime_ms = max(boot.highest_uptime_ms, payload.device_uptime_ms)

        # recorded_at remains compatible for chart consumers. For synchronized
        # v2 rows it means measured_at; unsynchronized/legacy rows are explicitly
        # historical and carry measured_at=null and their actual received_at.
        telemetry = Telemetry(**payload.model_dump(mode="json",exclude={"measured_at"}), measured_at=measured,
                              received_at=now, recorded_at=measured or now,
                              eligible_for_current=disposition == "current", disposition=disposition)
        db.add(telemetry)
        db.flush()
        db.add(TelemetryProvenance(telemetry_id=telemetry.id, **provenance))
        if telemetry.eligible_for_current:
            values = dict(config_version=payload.config_version, boot_id=payload.boot_id,
                          boot_sequence=payload.boot_sequence, sequence_no=payload.sequence_no,
                          device_uptime_ms=payload.device_uptime_ms, measured_at=measured,
                          latest_telemetry_id=telemetry.id)
            if state is None:
                db.add(StationTelemetryState(station_id=payload.station_id, **values))
            else:
                for key, value in values.items():
                    setattr(state, key, value)
            # This is the eligible heartbeat receipt. The separate ordering
            # cursor and depth clocks retain actual acquisition time. Historical
            # or replayed samples never reach this branch.
            station.last_ping = now
            station.firmware_version = payload.firmware_version
            decision_started=time.perf_counter()
            process_sensor_alert(db, station, telemetry)
            from app.services import observability as obs
            obs.observe('hazard.decision',time.perf_counter()-decision_started)
            obs.event('hazard.processed',correlation_id=f'observation-{telemetry.id}',sample_id=telemetry.id,state='processed')
        db.commit()
        from app.services import observability as obs
        if measured:obs.observe('ingest.backfill' if historical else 'ingest.live',max(0,(datetime.now(timezone.utc)-measured).total_seconds()))
        obs.event('telemetry.committed',correlation_id=f'observation-{telemetry.id}',sample_id=telemetry.id,station_id=payload.station_id,state=disposition)
    except Exception:
        db.rollback()
        raise
    db.refresh(telemetry)
    return telemetry


def latest_telemetry(db: Session, station_id: str) -> Telemetry | None:
    return db.scalar(select(Telemetry).join(
        StationTelemetryState, StationTelemetryState.latest_telemetry_id == Telemetry.id
    ).where(StationTelemetryState.station_id == station_id))


def telemetry_history(db: Session, station_id: str, limit: int) -> list[Telemetry]:
    return list(db.scalars(select(Telemetry).where(Telemetry.station_id == station_id)
                           .order_by(desc(Telemetry.recorded_at), desc(Telemetry.id)).limit(limit)))


def telemetry_contracts(db, rows):
    from app.schemas import TelemetryRead
    identities = {p.telemetry_id: p for p in db.scalars(select(TelemetryProvenance).where(
        TelemetryProvenance.telemetry_id.in_([r.id for r in rows])))} if rows else {}
    return [TelemetryRead.model_validate(r).model_copy(update=provenance_fields(identities.get(r.id))) for r in rows]
