"""Registry-owned source identity. Payloads/firmware strings never grant trust."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import StationCredential, StationIdentity, StationSourceRegistry, utc_now
from app.services.station_security import utc


def trusted_ingress(db: Session, station_id: str, config_version: int, source_id: str,
                    credential_id: str | None, transport: str, stream: str) -> dict:
    # Caller holds the station lock. A credential ID comes only from the server's
    # successful token authentication; it is not part of any client input schema.
    from app.models import Station
    from sqlalchemy import select
    from app.services.station_lifecycle import ensure_ingestion_allowed
    station=db.scalar(select(Station).where(Station.station_id==station_id))
    if station:ensure_ingestion_allowed(station)
    credential = db.get(StationCredential, credential_id, populate_existing=True) if credential_id else None
    identity = db.get(StationIdentity, station_id, populate_existing=True)
    registry = db.get(StationSourceRegistry, (station_id, config_version), populate_existing=True)
    if (credential is None or identity is None or registry is None
            or identity.state != "commissioned" or identity.version != config_version
            or identity.device_id != source_id or registry.device_id != identity.device_id
            or credential.station_id != station_id or credential.identity_version != config_version
            or credential.revoked_at is not None or utc(credential.expires_at) <= utc_now()
            or transport not in ("http", "mqtt") or credential.transport not in (transport, "both")):
        raise HTTPException(403, "Ingress requires an authenticated, reviewed source registry identity.")
    if registry.stream != stream or (stream == "operational" and registry.source_class != "physical_device"):
        raise HTTPException(403, "Source is not authorized for this stream; exercise traffic has a separate namespace.")
    return dict(credential_id=credential.id, ingress_transport=transport, ingress_identity=registry.device_id,
                source_class=registry.source_class, stream=registry.stream, registry_version=config_version)


def provenance_fields(row) -> dict:
    return dict(source_class=row.source_class if row else "unverified",
                source_trusted=bool(row and row.source_class == "physical_device" and row.stream == "operational"),
                stream=row.stream if row else "operational",
                ingress_identity=row.ingress_identity if row else None,
                ingress_transport=row.ingress_transport if row else "legacy")
