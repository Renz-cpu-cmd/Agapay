"""An ACK names the committed immutable observation, never merely a publish."""
from sqlalchemy import select
from app.models import Telemetry
from app.services.telemetry_service import _same_payload, ConflictingTelemetryError


def acknowledged_duplicate(db, payload):
    row = db.scalar(select(Telemetry).where(
        Telemetry.station_id == payload.station_id, Telemetry.config_version == payload.config_version,
        Telemetry.boot_id == payload.boot_id, Telemetry.sequence_no == payload.sequence_no))
    if row is None or not _same_payload(row, payload):
        raise ConflictingTelemetryError('Conflicting immutable observation')
    return row


def acknowledgement(payload, observation):
    return dict(station_id=payload.station_id, config_version=payload.config_version,
                boot_id=payload.boot_id, sequence_no=payload.sequence_no, persisted=True,
                telemetry=observation)
