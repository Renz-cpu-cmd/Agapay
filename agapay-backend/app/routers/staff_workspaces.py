"""Decision views over recorded evidence; ownership is separate from hazard state."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.orm import Session, aliased

from app.database import get_db
from app.models import (Alert, Station, StationIdentity, StationAuditEvent, Telemetry,
                        TelemetryProvenance, StationSourceRegistry, User, utc_now)
from app.governance_models import GovernanceAudit, StationArea, VerifiedArea
from app.routers.alerts import require_staff, require_alert
from app.services.station_security import lock_station, utc
from app.services.alert_governance import record
from app.staff_workspace_schemas import CommandQueue, OwnershipRead, StationWorkspace

router = APIRouter(prefix="/api", tags=["staff workspaces"])
OWNER_ACTION = "sensor_owner_changed"


def owner_contract(event):
    details = event.details if event else {}
    return {"revision": event.id if event else 0, "owner_id": details.get("owner_id"),
        "owner_name": details.get("owner_name"), "changed_at": utc(event.created_at) if event else None}


def ownership(db, alert_id):
    event = db.scalar(select(GovernanceAudit).where(GovernanceAudit.action == OWNER_ACTION,
        GovernanceAudit.subject == f"sensor-episode:{alert_id}").order_by(GovernanceAudit.id.desc()).limit(1))
    return owner_contract(event)


def physical_evidence(telemetry_column):
    # Historical identity is tied to each observation, never inferred from today's
    # firmware label or station identity after recommissioning.
    # R4: shared with the resident community feed (services/incident_verification.py).
    from app.device_config import operational_review_required
    from app.services.incident_verification import recorded_evidence
    return recorded_evidence(telemetry_column, require_reviewed_configuration=operational_review_required())


@router.get("/alerts/command-queue", response_model=CommandQueue)
def command_queue(scope: Literal["operational", "unverified"] = "operational",
                  limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db), user: User = Depends(require_staff)):
    proven = and_(physical_evidence(Alert.trigger_telemetry_id), physical_evidence(Alert.latest_telemetry_id))
    conditions = [Alert.status == "ACTIVE", proven if scope == "operational" else ~proven]
    all_count, physical_count = db.execute(select(func.count(), func.sum(case((proven, 1), else_=0)))
        .select_from(Alert).where(Alert.status == "ACTIVE")).one()
    counts = {"operational": int(physical_count or 0), "unverified": int(all_count - (physical_count or 0))}
    total = counts[scope]
    rows = db.scalars(select(Alert).where(*conditions).order_by(
        case((Alert.current_severity == "EVACUATE", 0), (Alert.current_severity == "WARNING", 1), else_=2),
        Alert.triggered_at, Alert.id).offset(offset).limit(limit)).all()
    station_ids = [row.station_id for row in rows]
    stations = {row.station_id: row for row in db.scalars(select(Station).where(Station.station_id.in_(station_ids)))}
    subjects = [f"sensor-episode:{row.id}" for row in rows]
    latest_owner_ids = select(func.max(GovernanceAudit.id)).where(GovernanceAudit.action == OWNER_ACTION,
        GovernanceAudit.subject.in_(subjects)).group_by(GovernanceAudit.subject)
    owners = {row.subject: row for row in db.scalars(select(GovernanceAudit).where(GovernanceAudit.id.in_(latest_owner_ids)))}
    area_bindings = db.execute(select(StationArea.station_id, VerifiedArea.id, VerifiedArea.name).join(VerifiedArea,
        StationArea.area_id == VerifiedArea.id).where(StationArea.station_id.in_(station_ids),
        StationArea.enabled.is_(True), VerifiedArea.active.is_(True))).all()
    areas_by_station = {}
    for binding in area_bindings:
        areas_by_station.setdefault(binding.station_id, []).append({"id": binding.id, "name": binding.name})
    items = []
    for row in rows:
        station = stations[row.station_id]
        items.append({"id": row.id, "station_id": row.station_id, "station_name": station.station_name,
            "severity": row.current_severity, "triggered_at": utc(row.triggered_at),
            "last_transition_at": utc(row.last_transition_at), "latest_telemetry_id": row.latest_telemetry_id,
            "latest_depth_cm": row.latest_depth_cm, "ownership": owner_contract(owners.get(f"sensor-episode:{row.id}")),
            "areas": areas_by_station.get(row.station_id, []),
            "source": "recorded_physical" if scope == "operational" else "unverified"})
    return {"items": items, "total": total, "has_more": offset + len(items) < total,
        "checked_at": utc_now(), "scope": scope, "counts": counts}


class OwnerWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(ge=0)
    expected_telemetry_id: int = Field(ge=1)
    action: Literal["take", "release"]
    reason: str = Field(min_length=3, max_length=500)


@router.post("/alerts/{alert_id}/ownership", response_model=OwnershipRead)
def change_owner(alert_id: int, payload: OwnerWrite, db: Session = Depends(get_db),
                 user: User = Depends(require_staff)):
    episode = require_alert(db, alert_id)
    lock_station(db, episode.station_id)  # Same serialization boundary as ingestion.
    db.refresh(episode)
    before = ownership(db, alert_id)
    if episode.status != "ACTIVE" or episode.latest_telemetry_id != payload.expected_telemetry_id or before["revision"] != payload.expected_revision:
        raise HTTPException(409, "Episode or ownership changed. Refresh and manually review before another action.")
    if payload.action == "take" and before["owner_id"] not in (None, user.id):
        raise HTTPException(409, "Another staff member owns this episode. Review the current ownership.")
    if payload.action == "release" and before["owner_id"] is None:
        raise HTTPException(409, "No owner is recorded. Refresh and review the current ownership.")
    if payload.action == "release" and before["owner_id"] != user.id and user.role != "admin":
        raise HTTPException(403, "Only the recorded owner or an administrator can release review responsibility.")
    after = {"owner_id": user.id if payload.action == "take" else None,
             "owner_name": user.name if payload.action == "take" else None}
    record(db, user, OWNER_ACTION, f"sensor-episode:{alert_id}", payload.reason,
        {**after, "before": jsonable_encoder(before), "after": after, "latest_telemetry_id": episode.latest_telemetry_id})
    db.commit()
    return ownership(db, alert_id)


@router.get("/stations/{station_id}/workspace", response_model=StationWorkspace)
def station_workspace(station_id: str, limit: int = Query(20, ge=1, le=50),
                      offset: int = Query(0, ge=0), db: Session = Depends(get_db),
                      user: User = Depends(require_staff)):
    station = db.scalar(select(Station).where(Station.station_id == station_id))
    if not station:
        raise HTTPException(404, "Station not found")
    identity = db.get(StationIdentity, station_id)
    base = select(Telemetry).where(Telemetry.station_id == station_id, Telemetry.eligible_for_current.is_(True))
    latest = db.scalar(base.order_by(Telemetry.recorded_at.desc(), Telemetry.id.desc()).limit(1))
    valid = db.scalar(base.where(Telemetry.sensor_quality == "valid", Telemetry.water_depth_cm.is_not(None))
        .order_by(Telemetry.recorded_at.desc(), Telemetry.id.desc()).limit(1))
    received = db.scalar(select(Telemetry).where(Telemetry.station_id == station_id)
        .order_by(Telemetry.received_at.desc(), Telemetry.id.desc()).limit(1))
    def sample(row):
        if row is None:
            return None
        p = db.get(TelemetryProvenance, row.id)
        return {"id": row.id, "measured_at": utc(row.measured_at) if row.measured_at else None,
            "received_at": utc(row.received_at), "quality": row.sensor_quality,
            "disposition": row.disposition, "source_id": p.ingress_identity if p else None,
            "registry_version": p.registry_version if p else None,
            "transport": p.ingress_transport if p else None,
            "source_class": p.source_class if p else "unverified"}
    condition = StationAuditEvent.station_id == station_id
    total = db.scalar(select(func.count()).select_from(StationAuditEvent).where(condition))
    events = db.scalars(select(StationAuditEvent).where(condition).order_by(StationAuditEvent.id.desc())
        .offset(offset).limit(limit)).all()
    return {"station_id": station_id, "checked_at": utc_now(),
        "identity": {"device_id": identity.device_id, "version": identity.version, "state": identity.state,
            "coordinates_verified": identity.coordinates_verified, "datum": identity.reference_datum,
            "calibration_note": identity.calibration_note,
            "commissioned_at": utc(identity.commissioned_at) if identity.commissioned_at else None} if identity else None,
        "latest_sample": sample(latest), "last_valid": sample(valid), "latest_received": sample(received),
        "events": [{"id": e.id, "action": e.action, "actor": e.actor_name, "reason": e.reason,
            "created_at": utc(e.created_at)} for e in events], "total": total,
        "has_more": offset + len(events) < total}
