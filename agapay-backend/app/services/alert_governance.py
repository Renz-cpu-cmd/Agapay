from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import exists, select, update
from app.governance_models import (AlertAuthority, AuthorityGrant, CitywideDispatch, GovernanceAudit,
    NotificationAudience, NotificationRecipient, OfficialNotice, ResidentSubscription, StationArea, VerifiedArea)
from app.models import Alert, AlertTransition, NotificationDelivery, NotificationDevice, NotificationEvent, Station, User, utc_now
from app.services.station_security import utc


def record(db, actor, action, subject, reason, details):
    from app.services.mutation_audit import record as general_record
    general_record(db,actor,"governance",subject,action,reason,details.get("before",{}),details.get("after",details))
    db.add(GovernanceAudit(actor_id=actor.id, action=action, subject=subject, reason=reason, details=details))


def verified_areas(db, ids):
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Duplicate area identifiers")
    areas = list(db.scalars(select(VerifiedArea).where(VerifiedArea.id.in_(ids), VerifiedArea.active.is_(True))))
    if len(areas) != len(ids):
        raise HTTPException(422, "Every area must have an active verified identifier")
    by_id = {area.id: area for area in areas}
    return [by_id[area_id] for area_id in ids]


def authorized(db, actor, authority_id, area_ids=(), *, citywide=False):
    if actor.role not in ("admin", "officer") or not actor.is_active:
        raise HTTPException(403, "Authorized staff access required")
    # Serialize issuance, grant changes and lifecycle updates under this row.
    db.execute(update(AlertAuthority).where(AlertAuthority.id == authority_id).values(active=AlertAuthority.active))
    authority = db.get(AlertAuthority, authority_id, populate_existing=True)
    grant = db.get(AuthorityGrant, (authority_id, actor.id), populate_existing=True)
    if not authority or not authority.active or not grant or not grant.active:
        raise HTTPException(403, "An explicit active issuing-authority grant is required")
    if citywide and not grant.citywide:
        raise HTTPException(403, "An explicit citywide authority grant is required")
    if not citywide and not set(area_ids).issubset(set(grant.area_ids)):
        raise HTTPException(403, "Requested area is outside staff jurisdiction")
    return authority


def issue_notice(db, actor, payload):
    authority = authorized(db, actor, payload.authority_id, payload.area_ids)
    areas = verified_areas(db, payload.area_ids)
    if payload.status == "Actual" and payload.category == "action" and (authority.authority_class != "public_authority" or any(area.area_class != "geographic" for area in areas)):
        raise HTTPException(403, "Public-authority action notices require a verified public issuing authority")
    if utc(payload.expires_at) <= utc_now() or utc(payload.expires_at) > utc_now() + timedelta(days=30):
        raise HTTPException(422, "Notice must expire in the future within 30 days")
    previous = None
    if payload.reference_id:
        previous = db.get(OfficialNotice, payload.reference_id)
        if not previous or previous.authority_id != authority.id or previous.status != payload.status:
            raise HTTPException(409, "Reference must identify a notice from the same issuer and status")
        if previous.message_type == "Cancel" or db.scalar(select(OfficialNotice.id).where(OfficialNotice.reference_id == previous.id)):
            raise HTTPException(409, "Notice already updated/cancelled. Refresh; do not retry a stale write.")
        if payload.message_type == "Cancel" and set(payload.area_ids) != set(previous.area_ids):
            raise HTTPException(422, "Cancellation must identify all original areas")
        if payload.effective_at > utc_now():
            raise HTTPException(422, "Corrections and cancellations take effect immediately")
    notice = OfficialNotice(**payload.model_dump(), issuer_name=authority.name,
        issued_by=actor.id, authority_class=authority.authority_class, area_names=[area.name for area in areas])
    db.add(notice)
    db.flush()
    record(db, actor, "official_notice_" + payload.message_type.lower(), notice.id, payload.reason, payload.model_dump(mode="json"))
    return notice


def notice_read(db, notice):
    now = utc_now()
    successor = db.scalar(select(OfficialNotice.id).where(OfficialNotice.reference_id == notice.id))
    lifecycle = "superseded" if successor else "cancelled" if notice.message_type == "Cancel" else "expired" if utc(notice.expires_at) <= now else "scheduled" if utc(notice.effective_at) > now else "effective"
    fields = {column.name: getattr(notice, column.name) for column in OfficialNotice.__table__.columns}
    return {**fields, "lifecycle": lifecycle, "superseded_by": successor, "kind": "official_notice"}


def station_subscriptions(db, station_id):
    areas = list(db.scalars(select(StationArea.area_id).join(VerifiedArea, VerifiedArea.id == StationArea.area_id)
                           .where(StationArea.station_id == station_id, StationArea.enabled.is_(True), VerifiedArea.active.is_(True))))
    subscriptions = list(db.scalars(select(ResidentSubscription).where(ResidentSubscription.enabled.is_(True),
        ((ResidentSubscription.kind == "station") & (ResidentSubscription.target_id == station_id)) |
        ((ResidentSubscription.kind == "area") & ResidentSubscription.target_id.in_(areas)))
        .order_by(ResidentSubscription.user_id, ResidentSubscription.kind, ResidentSubscription.target_id)))
    return areas, subscriptions


def event_audience_station(db, event):
    return db.get(NotificationAudience, event.id).station_id


def capture_recipient(db, event, device, subscription=None):
    delivery = NotificationDelivery(event_id=event.id, device_id=device.id,
        user_id=device.user_id, device_revision=device.revision)
    db.add(delivery)
    db.flush()
    from app.services.delivery_evidence import ensure_control
    ensure_control(db,delivery)
    db.add(NotificationRecipient(delivery_id=delivery.id,
        kind=subscription.kind if subscription else "citywide",
        target_id=subscription.target_id if subscription else "citywide",
        subscription_revision=subscription.revision if subscription else 0,
        area_binding_revision=db.get(StationArea, (event_audience_station(db, event), subscription.target_id)).revision if subscription and subscription.kind == "area" else None))


def audience_allows(db, delivery, transition):
    audience = db.get(NotificationAudience, delivery.event_id)
    recipient = db.get(NotificationRecipient, delivery.id)
    if not audience or not recipient or audience.station_id != transition.station_id:
        return False  # Legacy unscoped deliveries must never broadcast implicitly.
    override = db.get(CitywideDispatch, delivery.event_id)
    if override and utc(override.expires_at) > utc_now():
        actor = db.get(User, override.actor_id)
        authority = db.get(AlertAuthority, override.authority_id)
        grant = db.get(AuthorityGrant, (override.authority_id, override.actor_id))
        return bool(actor and actor.is_active and actor.role in ("admin", "officer") and authority and authority.active and grant and grant.active and grant.citywide)
    subscription = db.get(ResidentSubscription, (delivery.user_id, recipient.kind, recipient.target_id))
    if not subscription or not subscription.enabled or subscription.revision != recipient.subscription_revision:
        return False
    if recipient.kind == "station":
        return recipient.target_id == transition.station_id
    area = db.get(VerifiedArea, recipient.target_id)
    binding = db.get(StationArea, (transition.station_id, recipient.target_id))
    return bool(recipient.kind == "area" and area and area.active and recipient.target_id in audience.area_ids
                and binding and binding.enabled and binding.revision == recipient.area_binding_revision)


def citywide_dispatch(db, actor, transition_id, payload):
    authorized(db, actor, payload.authority_id, citywide=True)
    transition = db.get(AlertTransition, transition_id)
    if transition:
        from app.services.station_security import lock_station
        lock_station(db, transition.station_id)
    event = db.scalar(select(NotificationEvent).where(NotificationEvent.transition_id == transition_id))
    from app.services.station_lifecycle import delivery_allowed
    if event and not delivery_allowed(db,event,transition.station_id):
        raise HTTPException(409,'Station lifecycle suppresses this event; maintenance or prior lifecycle events cannot be replayed citywide')
    if not transition or not event or not db.get(NotificationAudience, event.id):
        raise HTTPException(404, "Scoped escalation event not found")
    episode = db.get(Alert, transition.alert_id)
    if episode.status != "ACTIVE" or db.scalar(select(AlertTransition.id).where(
        AlertTransition.alert_id == episode.id, AlertTransition.id > transition.id)):
        raise HTTPException(409, "The escalation is resolved or superseded; refresh before dispatch")
    if db.get(CitywideDispatch, event.id):
        raise HTTPException(409, "Citywide dispatch already exists; no automatic replay")
    if not utc_now() < utc(payload.expires_at) <= utc_now() + timedelta(hours=1):
        raise HTTPException(422, "Citywide dispatch must expire within one hour")
    db.add(CitywideDispatch(event_id=event.id, authority_id=payload.authority_id,
        actor_id=actor.id, reason=payload.reason, expires_at=payload.expires_at))
    # Explicit human intent captures only currently registered devices; never
    # resend a device already captured for this event, including UNKNOWN sends.
    from app.services.notification_service import eligible_devices
    existing = select(NotificationDelivery.device_id).where(NotificationDelivery.event_id == event.id)
    devices = list(db.scalars(eligible_devices().where(NotificationDevice.id.not_in(existing))))
    for device in devices:
        capture_recipient(db, event, device)
    record(db, actor, "citywide_dispatch", str(event.id), payload.reason,
        {"transition_id": transition_id, "authority_id": payload.authority_id, "expires_at": payload.expires_at.isoformat(), "new_recipients": len(devices)})
    return {"event_id": event.id, "new_recipients": len(devices), "expires_at": payload.expires_at}

