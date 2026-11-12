from fastapi import HTTPException
from sqlalchemy import select
from app.models import Station,StationIdentity,utc_now
from app.operations_models import StationOperation,StationDeliveryGate


_LOAD=object()  # sentinel: "not supplied; read it"


def contract(db,station,*,identity=_LOAD,operation=_LOAD,configuration=_LOAD):
    if identity is _LOAD:identity=db.get(StationIdentity,station.station_id)
    row=db.get(StationOperation,station.station_id) if operation is _LOAD else operation
    state=identity.state if identity and identity.state!='commissioned' else station.status
    return dict(state=state,revision=row.revision if row else 0,notification_epoch=row.notification_epoch if row else 0,
        identity_version=identity.version if identity else 0,reason=row.reason if row else 'Legacy lifecycle; no managed transition recorded',
        ingestion='accepted' if station.status in ('active','maintenance') and identity and identity.state=='commissioned' else 'rejected',
        observations='visible with administrative state and original measurement time',
        hazard_policy='escalation_and_sustained_recovery' if station.status=='active' else 'escalation_only_recovery_held' if station.status=='maintenance' else 'existing_incidents_retained_unresolved',
        external_sensor_notifications=station.status=='active' and bool(identity and identity.state=='commissioned')
            and _configuration_eligible(db,station.station_id,configuration)[0],
        local_alarm_policy='Device offline fail-safe continues; server lifecycle is not a remote mute acknowledgement')


def ensure_ingestion_allowed(station):
    if station.status not in ('active','maintenance'):
        raise HTTPException(403,'Station lifecycle rejects both water and rain ingestion; observations and existing incidents are preserved')


def touch(db,station,actor,reason,*,invalidate_delivery=False):
    from app.governance_models import HazardRecovery
    row=db.get(StationOperation,station.station_id,populate_existing=True)
    if row is None:
        row=StationOperation(station_id=station.station_id,revision=0,notification_epoch=0,actor_id=actor.id,reason=reason)
        db.add(row)
    row.revision+=1
    if invalidate_delivery:
        row.notification_epoch+=1
        recovery=db.get(HazardRecovery,station.station_id)
        if recovery:db.delete(recovery)
    row.actor_id,row.reason,row.updated_at=actor.id,reason,utc_now()
    return row


def _configuration_eligible(db,station_id,configuration=_LOAD):
    from app.device_config import operational_eligibility
    if configuration is _LOAD:return operational_eligibility(db,station_id)
    return operational_eligibility(db,station_id,configuration)


def capture_gate(db,event,station_id):
    station=db.scalar(select(Station).where(Station.station_id==station_id))
    operation=db.get(StationOperation,station_id)
    allowed=station is not None and station.status=='active'
    state=station.status if station else 'unknown'
    if allowed:
        # R4: an active station whose installation configuration is not reviewed keeps
        # its durable, suppressed event (no recipients) and never replays it later.
        eligible,reason=_configuration_eligible(db,station_id)
        if not eligible:
            allowed,state=False,reason
    db.add(StationDeliveryGate(event_id=event.id,notification_epoch=operation.notification_epoch if operation else 0,
        external_allowed=allowed,lifecycle_state=state))
    return allowed


def delivery_allowed(db,event,station_id):
    station=db.scalar(select(Station).where(Station.station_id==station_id))
    operation=db.get(StationOperation,station_id)
    epoch=operation.notification_epoch if operation else 0
    gate=db.get(StationDeliveryGate,event.id)
    return bool(station and station.status=='active' and (gate.external_allowed and gate.notification_epoch==epoch if gate else epoch==0)
                and _configuration_eligible(db,station_id)[0])
