from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Literal
from sqlalchemy import select, update, exists, func
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Alert, Station, User, utc_now
from app.governance_models import (AlertAuthority, AuthorityGrant, GovernanceAudit, HazardDecision,
    HazardPolicy, HazardRecovery, OfficialNotice, ResidentSubscription, StationArea, VerifiedArea)
from app.governance_schemas import (AreaBinding, AreaWrite, AuthorityWrite, CitywideWrite,
    GrantWrite, NoticeWrite, PolicyWrite, ReviewWrite, SubscriptionWrite, RevokeBinding)
from app.services.accounts import current_user, require_admin, lock_account
from app.services.station_security import lock_station
from app.services.hazard_policy import PROVISIONAL_RULES
from app.services.alert_governance import (authorized, citywide_dispatch, issue_notice,
    notice_read, record, verified_areas)

router = APIRouter(prefix="/api", tags=["alert governance"])


def columns(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


@router.get("/stations/{station_id}/hazard-policy")
def policy_read(station_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.scalar(select(Station.id).where(Station.station_id == station_id)):
        raise HTTPException(404, "Station not found")
    policy = db.get(HazardPolicy, station_id)
    return {**columns(policy), "state": "station_reviewed"} if policy else {
        "station_id": station_id, "version": 0, "rules": PROVISIONAL_RULES,
        "state": "provisional", "evidence": "AGAPAY prototype defaults; physical validation pending"}


@router.post("/stations/{station_id}/hazard-policy")
def policy_write(station_id: str, payload: PolicyWrite, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    station = lock_station(db, station_id)
    policy = db.get(HazardPolicy, station_id, populate_existing=True)
    version = policy.version if policy else 0
    if payload.expected_version != version:
        raise HTTPException(409, "Policy changed. Refresh and manually review; do not retry the stale write.")
    margins = [payload.rules.advisory_hysteresis_cm, payload.rules.warning_hysteresis_cm, payload.rules.evacuate_hysteresis_cm]
    exits = [boundary - margin for boundary, margin in zip(
        [station.threshold_advisory_cm, station.threshold_warning_cm, station.threshold_evacuate_cm], margins)]
    if not 0 <= exits[0] < exits[1] < exits[2]:
        raise HTTPException(422, "Exit boundaries must be nonnegative and strictly ordered")
    if policy is None:
        policy = HazardPolicy(station_id=station_id)
        db.add(policy)
    old_rules = policy.rules
    policy.version, policy.rules = version + 1, payload.rules.model_dump()
    policy.evidence, policy.approved_by, policy.approved_at = payload.validation_evidence, admin.id, utc_now()
    recovery = db.get(HazardRecovery, station_id)
    if recovery:
        db.delete(recovery)
    record(db, admin, "hazard_policy_approved", station_id, payload.reason,
           {"previous_rules": old_rules, "version": policy.version, **payload.model_dump(mode="json")})
    db.commit()
    return columns(policy)


@router.get("/stations/{station_id}/hazard-decisions")
def decisions(station_id: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role not in ("admin", "officer"):
        raise HTTPException(403, "Staff access required")
    return [columns(row) for row in db.scalars(select(HazardDecision).where(HazardDecision.station_id == station_id)
        .order_by(HazardDecision.telemetry_id.desc()).offset(offset).limit(limit))]


@router.post("/sensor-alerts/{alert_id}/reviews")
def review(alert_id: int, payload: ReviewWrite, db: Session = Depends(get_db), user: User = Depends(current_user)):
    episode = db.get(Alert, alert_id)
    if not episode:
        raise HTTPException(404, "Sensor episode not found")
    areas = list(db.scalars(select(StationArea.area_id).where(StationArea.station_id == episode.station_id)))
    authorized(db, user, payload.authority_id, areas)
    lock_station(db, episode.station_id)
    db.refresh(episode)
    if payload.expected_telemetry_id != episode.latest_telemetry_id:
        raise HTTPException(409, "The episode measurement changed; refresh and manually review")
    grant = db.get(AuthorityGrant, (payload.authority_id, user.id))
    if not areas and episode.station_id not in grant.station_ids:
        raise HTTPException(403, "An explicit station or area jurisdiction is required")
    record(db, user, "hazard_review_" + payload.action, str(alert_id), payload.reason,
        {**payload.model_dump(), "latest_telemetry_id": episode.latest_telemetry_id, "episode_severity": episode.current_severity})
    db.commit()
    return {"recorded": True, "sensor_episode_unchanged": True,
            "message": "Review recorded. Authority actions use a separate notice; measurements and recovery are not overwritten."}


@router.post("/alert-governance/areas", status_code=201)
def area_create(payload: AreaWrite, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.get(VerifiedArea, payload.id):
        raise HTTPException(409, "Area identifier already exists")
    area = VerifiedArea(**payload.model_dump(exclude={"reason"}))
    db.add(area)
    record(db, admin, "area_verified", payload.id, payload.reason, payload.model_dump())
    db.commit()
    return columns(area)


@router.post("/alert-governance/authorities", status_code=201)
def authority_create(payload: AuthorityWrite, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.get(AlertAuthority, payload.id):
        raise HTTPException(409, "Authority identifier already exists")
    authority = AlertAuthority(**payload.model_dump(exclude={"reason"}))
    db.add(authority)
    record(db, admin, "authority_registered", payload.id, payload.reason, payload.model_dump())
    db.commit()
    return columns(authority)


@router.post("/alert-governance/authorities/{authority_id}/grants")
def grant_write(authority_id: str, payload: GrantWrite, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    db.execute(update(AlertAuthority).where(AlertAuthority.id == authority_id).values(active=AlertAuthority.active))
    if not db.get(AlertAuthority, authority_id):
        raise HTTPException(404, "Authority not found")
    user = db.get(User, payload.user_id)
    if not user or not user.is_active or user.role not in ("admin", "officer"):
        raise HTTPException(422, "Grant recipient must be active staff")
    verified_areas(db, payload.area_ids)
    if len(set(payload.station_ids)) != len(payload.station_ids) or len(list(db.scalars(select(Station.station_id).where(Station.station_id.in_(payload.station_ids))))) != len(payload.station_ids):
        raise HTTPException(422, "Unknown or duplicate station jurisdiction")
    grant = db.get(AuthorityGrant, (authority_id, user.id), populate_existing=True)
    if payload.expected_revision != (grant.revision if grant else 0):
        raise HTTPException(409, "Grant changed; refresh and manually review")
    if grant is None:
        grant = AuthorityGrant(authority_id=authority_id, user_id=user.id, revision=0)
        db.add(grant)
    for field in ("area_ids", "station_ids", "citywide", "active"):
        setattr(grant, field, getattr(payload, field))
    grant.revision += 1
    record(db, admin, "authority_grant_changed", authority_id, payload.reason, payload.model_dump())
    db.commit()
    return columns(grant)


@router.post("/alert-governance/stations/{station_id}/areas")
def bind_areas(station_id: str, payload: AreaBinding, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    lock_station(db, station_id)
    verified_areas(db, payload.area_ids)
    for area_id in payload.area_ids:
        binding = db.get(StationArea, (station_id, area_id), populate_existing=True)
        if payload.expected_revisions.get(area_id, 0) != (binding.revision if binding else 0):
            raise HTTPException(409, "Area binding changed; refresh and manually review")
        if binding is None:
            db.add(StationArea(station_id=station_id, area_id=area_id))
        else:
            binding.enabled, binding.revision = True, binding.revision + 1
    record(db, admin, "station_areas_added", station_id, payload.reason, payload.model_dump())
    db.commit()
    return {"station_id": station_id, "area_ids": list(db.scalars(select(StationArea.area_id).where(StationArea.station_id == station_id, StationArea.enabled.is_(True))))}


@router.post("/alert-governance/stations/{station_id}/areas/{area_id}/revoke")
def revoke_binding(station_id: str, area_id: str, payload: RevokeBinding, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    lock_station(db, station_id)
    binding = db.get(StationArea, (station_id, area_id), populate_existing=True)
    if not binding:
        raise HTTPException(404, "Area binding not found")
    if payload.expected_revision != binding.revision:
        raise HTTPException(409, "Area binding changed; refresh and manually review")
    binding.enabled, binding.revision = False, binding.revision + 1
    record(db, admin, "station_area_revoked", station_id, payload.reason, {"area_id": area_id, "revision": binding.revision})
    db.commit()
    return columns(binding)


@router.get("/alert-subscriptions")
def subscriptions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {"subscriptions": [columns(row) for row in db.scalars(select(ResidentSubscription).where(ResidentSubscription.user_id == user.id).limit(200))],
        "areas": [columns(row) for row in db.scalars(select(VerifiedArea).where(VerifiedArea.active.is_(True)).limit(200))],
        "stations": [{"station_id": row.station_id, "station_name": row.station_name} for row in db.scalars(select(Station).order_by(Station.station_id).limit(200))]}


@router.post("/alert-subscriptions")
def subscribe(payload: SubscriptionWrite, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != "resident":
        raise HTTPException(403, "Resident subscriptions only")
    lock_account(db, user.id)
    if payload.kind == "station":
        if not db.scalar(select(Station.id).where(Station.station_id == payload.target_id)):
            raise HTTPException(422, "Unknown station")
    else:
        verified_areas(db, [payload.target_id])
    row = db.get(ResidentSubscription, (user.id, payload.kind, payload.target_id), populate_existing=True)
    if payload.expected_revision != (row.revision if row else 0):
        raise HTTPException(409, "Subscription changed. Refresh and manually review; do not retry automatically.")
    if row is None:
        count = len(list(db.scalars(select(ResidentSubscription).where(ResidentSubscription.user_id == user.id))))
        if count >= 200:
            raise HTTPException(422, "Subscription budget reached")
        row = ResidentSubscription(user_id=user.id, kind=payload.kind, target_id=payload.target_id, revision=0)
        db.add(row)
    row.enabled, row.revision, row.updated_at = payload.enabled, row.revision + 1, utc_now()
    record(db, user, "resident_subscription_changed", f"{payload.kind}:{payload.target_id}", "Resident explicitly changed alert subscriptions", payload.model_dump())
    db.commit()
    return columns(row)


@router.get("/alert-governance/capabilities")
def capabilities(db: Session = Depends(get_db), user: User = Depends(current_user)):
    grants = list(db.scalars(select(AuthorityGrant).where(AuthorityGrant.user_id == user.id, AuthorityGrant.active.is_(True))))
    return {"authorities": [{**columns(authority), "grant": columns(grant)} for grant in grants
        if (authority := db.get(AlertAuthority, grant.authority_id)) and authority.active],
        "areas": [columns(area) for area in db.scalars(select(VerifiedArea).where(VerifiedArea.active.is_(True)).limit(200))]}


@router.get("/official-notices")
def notices(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
            area_id: str | None = Query(None, min_length=1, max_length=50),
            status: Literal['Actual', 'Exercise', 'Test'] | None = None, current_only: bool = False,
            db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(OfficialNotice)
    if area_id is not None:
        # Exact JSON array membership before pagination on both supported engines.
        entries = (func.json_array_elements_text(OfficialNotice.area_ids) if db.bind.dialect.name == 'postgresql'
                   else func.json_each(OfficialNotice.area_ids)).table_valued('value')
        query = query.where(exists(select(1).select_from(entries).where(entries.c.value == area_id)))
    if status is not None:
        query = query.where(OfficialNotice.status == status)
    if current_only:
        successor = aliased(OfficialNotice)
        query = query.where(OfficialNotice.expires_at > utc_now(),
            ~exists(select(successor.id).where(successor.reference_id == OfficialNotice.id)))
    rows = db.scalars(query.order_by(OfficialNotice.sent_at.desc(), OfficialNotice.id.desc())
                      .offset(offset).limit(limit + 1)).all()
    return {"items": [notice_read(db, row) for row in rows[:limit]], "has_more": len(rows) > limit,
            "checked_at": utc_now(), "scope": {"area_id": area_id, "status": status, "current_only": current_only}}


@router.post("/official-notices", status_code=201)
def notice_create(payload: NoticeWrite, db: Session = Depends(get_db), user: User = Depends(current_user)):
    notice = issue_notice(db, user, payload)
    db.commit()
    return notice_read(db, notice)


@router.post("/alert-governance/transitions/{transition_id}/citywide")
def dispatch(transition_id: int, payload: CitywideWrite, db: Session = Depends(get_db), user: User = Depends(current_user)):
    result = citywide_dispatch(db, user, transition_id, payload)
    db.commit()
    return result


@router.get("/alert-governance/audit")
def governance_audit(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                     db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [columns(row) for row in db.scalars(select(GovernanceAudit).order_by(GovernanceAudit.id.desc()).offset(offset).limit(limit))]
