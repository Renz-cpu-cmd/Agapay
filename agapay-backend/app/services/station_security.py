"""Station-bound credentials and commissioning; no device secrets in audit/logs."""
import hashlib
import re
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (Station, StationAuditEvent, StationCredential, StationIdentity, StationSourceRegistry,
                        StationIngressBudget, User, utc_now)
from app.station_schemas import Commissioning, CredentialRequest

TOKEN_PATTERN = re.compile(r"^agi_[A-Za-z0-9_-]{43}$")
MAX_INGRESS_BYTES = 4096


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def lock_station(db: Session, station_id: str) -> Station:
    result = db.execute(update(Station).where(Station.station_id == station_id)
                        .values(last_ping=Station.last_ping))
    if result.rowcount != 1:
        raise HTTPException(404, "Station not found")
    return db.scalar(select(Station).where(Station.station_id == station_id)
                     .execution_options(populate_existing=True))


def audit(db: Session, station: Station, actor: User, action: str, reason: str, details: dict):
    from app.services.mutation_audit import record
    record(db,actor,"station",station.station_id,action,reason,details.get("before",{}),details.get("after",details))
    db.add(StationAuditEvent(station_id=station.station_id, actor_id=actor.id,
                            actor_name=actor.name, action=action, reason=reason, details=details))


def commit_security(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Station or device binding already exists. Refresh before retrying.") from None


def commission(db: Session, station: Station, payload: Commissioning, actor: User,
               *, expected_version: int, action: str = "commissioning_updated",
               coordinates: dict | None = None) -> StationIdentity:
    # Caller holds the parent station write lock (a new uncommitted station also suffices).
    identity = db.get(StationIdentity, station.station_id, populate_existing=True)
    if expected_version != (identity.version if identity else 0):
        raise HTTPException(409, "Station commissioning changed. Refresh and review the current values.")
    station_fields = ("station_name", "latitude", "longitude", "sensor_height_cm", "threshold_advisory_cm",
                      "threshold_warning_cm", "threshold_evacuate_cm", "status")
    station_before = {key: getattr(station, key) for key in station_fields}
    for key in ("latitude", "longitude"):
        if coordinates is not None and key in coordinates:
            setattr(station, key, coordinates[key])
    if payload.state == "commissioned" and (
        not payload.coordinates_verified or station.latitude is None or station.longitude is None
    ):
        raise HTTPException(422, "Commissioning requires operator-verified coordinates and a reference datum.")
    before = None if identity is None else {
        key: getattr(identity, key) for key in ("device_id", "state", "coordinates_verified", "reference_datum", "calibration_note", "version")
    }
    now = utc_now()
    if identity is None:
        identity = StationIdentity(station_id=station.station_id, version=1)
        db.add(identity)
    else:
        identity.version += 1
        # Any reviewed binding/calibration/state change invalidates previous credentials.
        db.execute(update(StationCredential).where(StationCredential.station_id == station.station_id,
                   StationCredential.revoked_at.is_(None)).values(revoked_at=now))
    for key in ("device_id", "state", "coordinates_verified", "reference_datum", "calibration_note"):
        setattr(identity, key, getattr(payload, key))
    identity.commissioned_at = now if payload.state == "commissioned" else None
    station.status = "active" if payload.state == "commissioned" else "inactive"
    from app.services.station_lifecycle import touch
    touch(db,station,actor,payload.reason,invalidate_delivery=True)
    after = {key: getattr(identity, key) for key in (
        "device_id", "state", "coordinates_verified", "reference_datum", "calibration_note", "version")}
    db.add(StationSourceRegistry(station_id=station.station_id, config_version=identity.version,
        device_id=identity.device_id, source_class=payload.source_class, stream=payload.stream,
        evidence=payload.provenance_evidence, reviewed_by=actor.id))
    after.update(source_class=payload.source_class, stream=payload.stream,
                 provenance_evidence=payload.provenance_evidence)
    audit(db, station, actor, action, payload.reason, {
        "before": before, "after": after, "station_before": station_before,
        "station": {key: getattr(station, key) for key in station_fields},
    })
    return identity


def issue_credential(db: Session, station: Station, payload: CredentialRequest, actor: User):
    identity = db.get(StationIdentity, station.station_id, populate_existing=True)
    if identity is None or identity.state != "commissioned" or station.status not in ("active","maintenance"):
        raise HTTPException(409, "Commission and activate this station before issuing ingestion credentials.")
    if identity.version != payload.expected_version:
        raise HTTPException(409, "Station commissioning changed. Refresh and review the current values.")
    if utc(payload.expires_at) <= utc_now():
        raise HTTPException(422, "Credential expiry must be in the future")
    token = "agi_" + secrets.token_urlsafe(32)
    credential = StationCredential(station_id=station.station_id, identity_version=identity.version,
        token_hash=digest(token), label=payload.label, transport=payload.transport, expires_at=payload.expires_at)
    db.add(credential)
    db.flush()
    audit(db, station, actor, "credential_issued", payload.reason, {
        "credential_id": credential.id, "identity_version": identity.version,
        "transport": payload.transport, "expires_at": payload.expires_at.isoformat(), "label": payload.label,
    })
    return credential, token


def authorize_ingress(db: Session, token: str, station_id: str, transport: str) -> StationCredential:
    error = HTTPException(401, "A valid station ingestion credential is required.",
                          headers={"WWW-Authenticate": "Bearer"})
    if not TOKEN_PATTERN.fullmatch(token):
        raise error
    credential = db.scalar(select(StationCredential).where(StationCredential.token_hash == digest(token))
                           .execution_options(populate_existing=True))
    if credential is None:
        raise error
    if credential.station_id != station_id:
        raise HTTPException(403, "This credential cannot ingest for the requested station.")
    # Serialize with commissioning/revocation; re-read after waiting for the lock.
    station=lock_station(db, station_id)
    db.refresh(credential)
    identity = db.get(StationIdentity, station_id, populate_existing=True)
    if credential.revoked_at is not None or utc(credential.expires_at) <= utc_now():
        raise error
    if (identity is None or identity.state != "commissioned"
            or identity.version != credential.identity_version):
        raise HTTPException(403, "Station ingestion is not commissioned.")
    if credential.transport not in (transport, "both"):
        raise HTTPException(403, "This credential is not permitted on this transport.")
    from app.services.station_lifecycle import ensure_ingestion_allowed
    ensure_ingestion_allowed(station)
    return credential


def prepare_ingress(db: Session, token: str, station_id: str, transport: str, channel: str, settings: Settings):
    """Charge attempts durably, then reauthorize under the lock for the actual write.

    Separate quota commit means even duplicate/conflicting attempts consume budget.
    The second authorization prevents expiry/revocation in that gap being bypassed.
    Call only with a dedicated ingress session, before any other business mutation.
    """
    try:
        authorize_ingress(db, token, station_id, transport)
        now = utc_now()
        minute = now.replace(second=0, microsecond=0)
        budget = db.get(StationIngressBudget, (station_id, channel), populate_existing=True)
        limit = settings.telemetry_ingest_per_minute if channel == "telemetry" else settings.rain_ingest_per_minute
        if budget is None:
            budget = StationIngressBudget(station_id=station_id, channel=channel, window_start=minute, attempts=0)
            db.add(budget)
        elif utc(budget.window_start) != minute:
            budget.window_start, budget.attempts = minute, 0
        if budget.attempts >= limit:
            raise HTTPException(429, "Station ingestion budget exceeded.",
                                headers={"Retry-After": str(60 - now.second)})
        budget.attempts += 1
        db.commit()
        return authorize_ingress(db, token, station_id, transport)
    except Exception:
        db.rollback()
        raise
