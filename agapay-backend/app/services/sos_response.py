"""Recorded drill actions; no transport calls and no operational activation switch."""
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import select, update
from app.models import SosRequest, User, utc_now
from app.sos_response_models import SosDrillPolicy, SosDrillResponse, SosDrillIncident, SosResponseEvent
from app.services.sos_concurrency import claim, conflict
from app.services.station_security import utc
from app.services.mutation_audit import record

DEFAULTS = dict(timezone='Asia/Manila', assignment_seconds=120, acceptance_seconds=180,
                departure_seconds=300, arrival_seconds=900, review_seconds=300,
                coordinator_id=None, shifts=[], fallback_contacts=[])


def policy_read(db):
    policy = db.get(SosDrillPolicy, 1, populate_existing=True)
    return dict(version=policy.version if policy else 0, configured=policy is not None,
                settings=policy.settings if policy else DEFAULTS, mode='drill', operational_enabled=False,
                activation_requirements=['Agreed LGU procedures, jurisdiction and real fallback contacts',
                    'Verified duty coverage and operator training', 'Witnessed unavailable-first-officer drill',
                    'Reviewed dispatch integration and operational activation release'])


def save_policy(db, actor, payload):
    ids = {s.user_id for s in payload.shifts}
    staff = set(db.scalars(select(User.id).where(User.id.in_(ids), User.is_active.is_(True), User.role.in_(('admin', 'officer')))))
    if staff != ids: raise HTTPException(422, 'Every roster entry must identify active staff')
    policy = db.get(SosDrillPolicy, 1, populate_existing=True)
    if payload.expected_version != (policy.version if policy else 0):
        raise HTTPException(409, dict(code='refresh_required', message='Drill policy changed. Refresh and review.', current=policy_read(db)))
    settings = payload.model_dump(mode='json', exclude={'expected_version', 'reason'})
    if policy:
        changed = db.execute(update(SosDrillPolicy).where(SosDrillPolicy.id == 1,
            SosDrillPolicy.version == payload.expected_version).values(settings=settings,
            version=SosDrillPolicy.version+1, reviewed_by=actor.id, reviewed_at=utc_now()))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, dict(code='refresh_required', message='Drill policy changed. Refresh and review.', current=policy_read(db)))
    else: db.add(SosDrillPolicy(id=1, version=1, settings=settings, reviewed_by=actor.id))
    record(db, actor, 'sos_policy', 1, 'drill_policy_updated', payload.reason,
           {'version': payload.expected_version}, {'version': payload.expected_version+1, 'state': 'drill_only'})
    db.commit()
    return policy_read(db)


def on_duty(db, policy, user_id, now):
    person = db.get(User, user_id, populate_existing=True)
    if not person or not person.is_active or person.role not in ('admin', 'officer'): return False
    return any(s['user_id'] == user_id and datetime.fromisoformat(s['starts_at'].replace('Z', '+00:00')) <= now
               < datetime.fromisoformat(s['ends_at'].replace('Z', '+00:00')) for s in policy['shifts'])


def event(db, item, actor, action, reason, message, details=None):
    db.add(SosResponseEvent(sos_id=item.id, request_version=item.version, actor_id=actor.id if actor else None,
        actor_name=actor.name if actor else 'Drill escalation worker', action=action, reason=reason,
        resident_message=message, details=details or {}))
    record(db, actor, 'sos', item.id, 'drill_'+action, reason, after={'version': item.version, 'status': item.status})


def start(db, item, actor, payload):
    policy = db.get(SosDrillPolicy, 1, populate_existing=True)
    if not policy or policy.version != payload.policy_version:
        raise HTTPException(409, dict(code='refresh_required', message='Configure and review the current drill policy first.'))
    # Serialize policy selection with edits before taking the request version.
    db.execute(update(SosDrillPolicy).where(SosDrillPolicy.id == 1).values(version=SosDrillPolicy.version))
    db.refresh(policy)
    if policy.version != payload.policy_version: conflict(db, item, 'Drill policy changed. Refresh before starting.')
    if not item.practice: raise HTTPException(403, 'This workspace accepts exercises only')
    if not on_duty(db, policy.settings, policy.settings['coordinator_id'], utc_now()):
        raise HTTPException(409, 'The configured drill coordinator has no current active duty coverage')
    review = dict(status='ACKNOWLEDGED', acknowledged_by=actor.id, acknowledged_by_name=actor.name,
                  acknowledged_at=utc_now()) if item.status == 'ACTIVE' else {}
    claim(db, item, payload.expected_version, conditions=(SosRequest.status != 'RESOLVED',), fields=review)
    if db.get(SosDrillResponse, item.id): conflict(db, item, 'A response drill already exists. Refresh the request.')
    response = SosDrillResponse(sos_id=item.id, policy_version=policy.version, policy=policy.settings,
        coordinator_id=policy.settings['coordinator_id'], phase='UNASSIGNED',
        due_at=utc_now()+timedelta(seconds=policy.settings['assignment_seconds']))
    db.add(response)
    event(db, item, actor, 'started', payload.reason, 'Response drill started. A coordinator owns review; no responder has accepted dispatch.')
    db.commit()
    return read(db, item, actor)


def escalate(db, item, response, reason, actor=None, now=None):
    now = now or utc_now()
    # Never invent departure/arrival or reroute a team already travelling.
    candidates = []
    if response.phase in ('UNASSIGNED', 'ASSIGNED'):
        for shift in response.policy['shifts']:
            identity = shift['user_id']
            if identity not in response.attempted_users and identity not in candidates and on_duty(db, response.policy, identity, now):
                candidates.append(identity)
    if candidates:
        response.assigned_to = candidates[0]
        response.attempted_users = [*response.attempted_users, candidates[0]]
        response.phase = 'ASSIGNED'
        response.due_at = now+timedelta(seconds=response.policy['acceptance_seconds'])
        message = 'Drill escalated to another roster member. Dispatch acceptance is still pending.'
    else:
        response.due_at = None
        message = 'Drill needs coordinator review and the configured fallback contact procedure. No new dispatch or arrival is confirmed.'
    response.attention = 'needs_review'
    event(db, item, actor, 'escalated', reason, message, {'assigned_to': response.assigned_to, 'phase': response.phase})


def act(db, item, actor, payload):
    claim(db, item, payload.expected_version, conditions=(SosRequest.status != 'RESOLVED',))
    response = db.get(SosDrillResponse, item.id, populate_existing=True)
    if not response: raise HTTPException(409, 'Start the response drill first')
    if not item.practice: raise HTTPException(403, 'Exercise workspace only')
    a = payload.action
    coordinator = actor.id == response.coordinator_id or actor.role == 'admin'
    responder = actor.id == response.assigned_to
    now = utc_now()
    message = ''
    if a in ('assign', 'handoff'):
        if not coordinator and not (a == 'handoff' and responder): raise HTTPException(403, 'Coordinator or current responder handoff required')
        if a == 'assign' and response.phase not in ('UNASSIGNED', 'ASSIGNED'):
            raise HTTPException(409, 'Use a recorded handoff after dispatch acceptance')
        if not payload.responder_id or not on_duty(db, response.policy, payload.responder_id, now):
            raise HTTPException(422, 'Select an active responder within recorded drill duty hours')
        if payload.responder_id == response.assigned_to: raise HTTPException(409, 'This responder is already assigned')
        response.assigned_to = payload.responder_id
        response.attempted_users = list(dict.fromkeys([*response.attempted_users, payload.responder_id]))
        response.phase, response.attention = 'ASSIGNED', 'normal'
        response.due_at = now+timedelta(seconds=response.policy['acceptance_seconds'])
        message = 'Drill responder assigned; dispatch is not accepted.' if a == 'assign' else 'Drill ownership handed off; the new responder must accept dispatch.'
    elif a == 'contact_attempt':
        if not coordinator and not responder: raise HTTPException(403, 'Assigned responder or coordinator required')
        if not payload.channel or not payload.outcome or not payload.reference:
            raise HTTPException(422, 'Record contact channel, outcome and an action reference')
        message = 'A drill contact attempt was recorded. It does not confirm dispatch.'
    elif a in ('accept', 'depart', 'arrive'):
        expected = {'accept': 'ASSIGNED', 'depart': 'ACCEPTED', 'arrive': 'EN_ROUTE'}[a]
        if not responder: raise HTTPException(403, 'Only the assigned responder can record this action')
        if response.phase != expected: raise HTTPException(409, 'Response stage changed. Refresh and follow the recorded sequence')
        if not payload.reference: raise HTTPException(422, 'A drill action/dispatch reference is required')
        if a == 'accept' and not on_duty(db, response.policy, actor.id, now):
            raise HTTPException(409, 'Responder duty coverage ended; ask the coordinator for a reviewed handoff')
        response.phase = {'accept': 'ACCEPTED', 'depart': 'EN_ROUTE', 'arrive': 'ARRIVED'}[a]
        seconds = {'accept': response.policy['departure_seconds'], 'depart': response.policy['arrival_seconds'], 'arrive': response.policy['review_seconds']}[a]
        response.due_at, response.attention = now+timedelta(seconds=seconds), 'normal'
        message = {'accept': 'Assigned responder recorded acceptance of drill dispatch.', 'depart': 'Assigned responder recorded drill departure.', 'arrive': 'Assigned responder recorded drill arrival.'}[a]
    elif a == 'unavailable':
        if not coordinator and not responder: raise HTTPException(403, 'Assigned responder or coordinator required')
        if response.phase != 'ASSIGNED': raise HTTPException(409, 'Use a handoff for a dispatch already accepted')
        escalate(db, item, response, payload.reason, actor, now)
        db.commit()
        return read(db, item, actor)
    elif a == 'review_escalation':
        if not coordinator: raise HTTPException(403, 'Coordinator review required')
        if response.attention != 'needs_review' or not payload.reference:
            raise HTTPException(422, 'An escalated drill and a fallback/review action reference are required')
        response.attention = 'reviewed'
        response.due_at = now+timedelta(seconds=response.policy['review_seconds'])
        message = 'Coordinator recorded review of the drill escalation. Dispatch and arrival remain separate recorded actions.'
    elif a == 'correlate':
        if not coordinator: raise HTTPException(403, 'Coordinator review required')
        incident = db.get(SosDrillIncident, payload.incident_id) if payload.incident_id else None
        if not incident: raise HTTPException(422, 'Choose a recorded drill incident')
        response.incident_id = incident.id
        message = 'This request was linked to a shared drill incident; its individual history and response remain separate.'
    elif a == 'close':
        if not coordinator and not responder: raise HTTPException(403, 'Coordinator or assigned responder required')
        if not payload.closure_reason or not payload.reference: raise HTTPException(422, 'Closure reason and evidence reference are required')
        if payload.closure_reason == 'assistance_completed' and response.phase != 'ARRIVED':
            raise HTTPException(409, 'Assistance completion requires a recorded arrival')
        if payload.closure_reason != 'assistance_completed' and not coordinator:
            raise HTTPException(403, 'Exceptional or exercise-only closure requires coordinator review')
        if payload.closure_reason == 'duplicate_correlated' and response.incident_id is None:
            raise HTTPException(422, 'Correlate the incident before duplicate closure')
        response.phase, response.due_at, response.closure_reason = 'CLOSED', None, payload.closure_reason
        item.status, item.resolved_at, item.resolved_by, item.resolved_by_name = 'RESOLVED', now, actor.id, actor.name
        item.resolution_note = payload.reason
        message = 'Drill closed with a recorded reason. This is not evidence of a real emergency response.'
    event(db, item, actor, a, payload.reason, message, payload.model_dump(mode='json', exclude={'expected_version', 'reason'}))
    db.commit()
    return read(db, item, actor)


def read(db, item, viewer, *, before_event_id=None):
    response = db.get(SosDrillResponse, item.id, populate_existing=True)
    if not response:
        return dict(mode='drill', operational_enabled=False, started=False, request_version=item.version,
                    message='Practice request only. Acknowledgement confirms review, not responder dispatch.', events=[])
    query = select(SosResponseEvent).where(SosResponseEvent.sos_id == item.id)
    if before_event_id: query = query.where(SosResponseEvent.id < before_event_id)
    events = list(db.scalars(query.order_by(SosResponseEvent.id.desc()).limit(101)))
    more = len(events) > 100
    events = events[:100]
    def name(identity):
        person = db.get(User, identity) if identity else None
        return person.name if person else None
    data = dict(mode='drill', operational_enabled=False, started=True, request_version=item.version,
        phase=response.phase, attention=response.attention, coordinator_name=name(response.coordinator_id),
        responder_name=name(response.assigned_to), due_at=utc(response.due_at) if response.due_at else None,
        policy_version=response.policy_version, incident_reference=f'DRILL-{response.incident_id}' if response.incident_id else None,
        closure_reason=response.closure_reason, has_more_events=more, next_before_event_id=events[-1].id if more else None,
        events=[dict(id=e.id, action=e.action, message=e.resident_message, created_at=utc(e.created_at),
                     **({'actor_name': e.actor_name, 'reason': e.reason, 'details': e.details} if viewer.role != 'resident' else {})) for e in reversed(events)])
    if viewer.role != 'resident':
        data.update(coordinator_id=response.coordinator_id, assigned_to=response.assigned_to,
                    fallback_contacts=response.policy['fallback_contacts'], policy=response.policy)
    return data


def process_due(session_factory, *, limit=50, now=None):
    if not 1 <= limit <= 100: raise ValueError('Limit must be 1..100')
    now = now or utc_now()
    with session_factory() as db:
        ids = list(db.scalars(select(SosDrillResponse.sos_id).where(SosDrillResponse.due_at <= now,
            SosDrillResponse.phase != 'CLOSED').order_by(SosDrillResponse.due_at).limit(limit)))
    processed = []
    for identity in ids:
        with session_factory() as db:
            item = db.get(SosRequest, identity)
            if not item or not item.practice or item.status == 'RESOLVED': continue
            version = item.version
            result = db.execute(update(SosRequest).where(SosRequest.id == identity,
                SosRequest.version == version, SosRequest.status != 'RESOLVED', SosRequest.practice.is_(True)
                ).values(version=SosRequest.version+1).execution_options(synchronize_session=False))
            if result.rowcount != 1: db.rollback(); continue
            response = db.get(SosDrillResponse, identity, populate_existing=True)
            if response.due_at is None or utc(response.due_at) > now or response.phase == 'CLOSED':
                db.rollback(); continue
            db.refresh(item)
            escalate(db, item, response, 'Recorded drill response deadline exceeded', now=now)
            db.commit()
            processed.append(identity)
    return {'mode': 'drill', 'processed': processed, 'external_messages_sent': 0}
