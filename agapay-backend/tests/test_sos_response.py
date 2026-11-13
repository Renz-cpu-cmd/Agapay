"""Real SQLite writes through independent HTTP requests; all contacts/dispatches are synthetic drills."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
import pytest
from sqlalchemy import select, text, create_engine
from app.account_schemas import RegisterRequest
from app.database import SessionLocal
from app.models import SosRequest, User, utc_now
from app.services.accounts import create_user
from app.services.station_security import utc
from app.services.sos_response import process_due
from app.sos_response_models import SosResponseEvent, SosDrillResponse
from app.routers import sos as router
from app.migrate_sos_response import migrate, require_schema
from test_accounts import account, headers, staff, sign_in, reset_accounts
from test_sos import payload, resident


def make_request(client, resident):
    return client.post('/api/sos', headers=resident, json=payload()).json()


def fix(at=None, **changes):
    return dict(expected_version=1, latitude=15.97, longitude=120.57, accuracy_m=5,
                location_recorded_at=(at or utc_now()).isoformat(), **changes)


def synchronize_reads(monkeypatch):
    original = router.visible
    barrier = Barrier(2)
    def visible(*args):
        item = original(*args)
        barrier.wait(timeout=10)
        return item
    monkeypatch.setattr(router, 'visible', visible)


def test_concurrent_delayed_fix_cannot_overwrite_newer_committed_fix(client, resident, monkeypatch):
    item = make_request(client, resident)
    url = f'/api/sos/{item["id"]}/location'
    newer = utc_now(); older = newer-timedelta(seconds=1)
    committed = Event(); original = router.claim
    synchronize_reads(monkeypatch)
    def claim(*args, **kwargs):
        if kwargs['fields']['location_recorded_at'] == older:
            assert committed.wait(timeout=10)
        return original(*args, **kwargs)
    monkeypatch.setattr(router, 'claim', claim)
    def send(at):
        response = client.patch(url, headers=resident, json=fix(at))
        if at == newer: committed.set()
        return response
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, [older, newer]))
    assert [r.status_code for r in responses] == [409, 200]
    assert responses[0].json()['detail']['code'] == 'refresh_required'
    assert responses[0].json()['detail']['current']['version'] == 2
    with SessionLocal() as db:
        assert utc(db.get(SosRequest, item['id']).location_recorded_at) == utc(newer)


@pytest.mark.parametrize('identical', [True, False])
def test_concurrent_equal_time_fixes_are_idempotent_or_conflicting(client, resident, monkeypatch, identical):
    item = make_request(client, resident); captured = utc_now()
    synchronize_reads(monkeypatch)
    def send(latitude):
        body = fix(captured); body['latitude'] = latitude
        return client.patch(f'/api/sos/{item["id"]}/location', headers=resident, json=body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, [15.97, 15.97 if identical else 15.98]))
    assert sorted(r.status_code for r in responses) == ([200, 200] if identical else [200, 409])
    with SessionLocal() as db: assert db.get(SosRequest, item['id']).version == 2


def test_resolution_winning_race_prevents_location_write(client, resident, monkeypatch):
    access = staff(client); item = make_request(client, resident); url = f'/api/sos/{item["id"]}'
    client.patch(url, headers=access, json={'expected_version':1, 'status':'ACKNOWLEDGED'})
    committed = Event(); original = router.claim
    synchronize_reads(monkeypatch)
    def claim(*args, **kwargs):
        if 'latitude' in kwargs['fields']: assert committed.wait(timeout=10)
        return original(*args, **kwargs)
    monkeypatch.setattr(router, 'claim', claim)
    def resolve():
        response = client.patch(url, headers=access, json={'expected_version':2, 'status':'RESOLVED', 'resolution_note':'Synthetic resolution race'})
        committed.set(); return response
    with ThreadPoolExecutor(max_workers=2) as pool:
        resolution = pool.submit(resolve)
        body = fix(); body['expected_version'] = 2
        location = pool.submit(client.patch, url+'/location', headers=resident, json=body)
        assert resolution.result().status_code == 200
        rejected = location.result()
    assert rejected.status_code == 409 and rejected.json()['detail']['current']['status'] == 'RESOLVED'
    with SessionLocal() as db:
        row = db.get(SosRequest, item['id'])
        assert row.version == 3 and row.location_source == 'manual'


def test_version_required_and_exact_duplicate_replay_does_not_bump_version(client, resident):
    item = make_request(client, resident); url = f'/api/sos/{item["id"]}/location'; body = fix()
    missing = {k:v for k,v in body.items() if k!='expected_version'}
    assert client.patch(url, headers=resident, json=missing).status_code == 422
    first = client.patch(url, headers=resident, json=body)
    assert first.status_code == 200
    assert client.patch(url, headers=resident, json=body).json() == first.json()


@pytest.fixture
def drill(client, resident):
    admin, primary = staff(client), staff(client, 'officer')
    with SessionLocal() as db: create_user(db, RegisterRequest(**account('alternate@example.com')), 'officer')
    alternate = headers(sign_in(client, 'alternate@example.com', 'web'))
    aid, pid, bid = [client.get('/api/auth/me', headers=h).json()['id'] for h in (admin, primary, alternate)]
    now = utc_now()
    policy = dict(expected_version=0, reason='Synthetic drill roster and timeout review', coordinator_id=aid,
        assignment_seconds=5, acceptance_seconds=5, departure_seconds=5, arrival_seconds=5, review_seconds=5,
        shifts=[dict(user_id=i, starts_at=(now-timedelta(hours=1)).isoformat(), ends_at=(now+timedelta(hours=1)).isoformat()) for i in (pid,bid,aid)],
        fallback_contacts=[dict(label='Synthetic bench radio', channel='radio', contact='Exercise channel only')])
    saved = client.patch('/api/sos-response/policy', headers=admin, json=policy)
    assert saved.status_code == 200, saved.text
    item = make_request(client, resident)
    result = client.post(f'/api/sos-response/{item["id"]}/start', headers=admin,
        json=dict(expected_version=1, policy_version=1, reason='Start synthetic response drill'))
    assert result.status_code == 200, result.text
    return dict(admin=admin, primary=primary, alternate=alternate, primary_id=pid, alternate_id=bid,
                coordinator_id=aid, item=item, policy=policy, resident=resident)


def action(client, drill, action, access=None, **fields):
    identity = drill['item']['id']; access = access or drill['admin']
    version = client.get(f'/api/sos-response/{identity}', headers=access).json()['request_version']
    return client.post(f'/api/sos-response/{identity}/actions', headers=access,
        json=dict(expected_version=version, action=action, reason='Synthetic recorded drill action', **fields))


def test_recorded_sequence_requires_real_actor_actions_and_preserves_resident_privacy(client, drill):
    identity = drill['item']['id']; url=f'/api/sos-response/{identity}'
    assert client.get(f'/api/sos/{identity}', headers=drill['resident']).json()['status'] == 'ACKNOWLEDGED'
    assert action(client, drill, 'assign', responder_id=drill['primary_id']).json()['phase'] == 'ASSIGNED'
    assert action(client, drill, 'accept', reference='DRILL-accept').status_code == 403
    assert action(client, drill, 'accept', drill['primary']).status_code == 422
    assert action(client, drill, 'contact_attempt', channel='radio', outcome='no_answer', reference='DRILL-call').status_code == 200
    assert action(client, drill, 'accept', drill['primary'], reference='DRILL-accept').json()['phase'] == 'ACCEPTED'
    assert action(client, drill, 'arrive', drill['primary'], reference='DRILL-arrival').status_code == 409
    assert action(client, drill, 'depart', drill['primary'], reference='DRILL-departure').json()['phase'] == 'EN_ROUTE'
    assert action(client, drill, 'close', drill['primary'], closure_reason='assistance_completed', reference='DRILL-close').status_code == 409
    assert action(client, drill, 'arrive', drill['primary'], reference='DRILL-arrival').json()['phase'] == 'ARRIVED'
    closed = action(client, drill, 'close', drill['primary'], closure_reason='assistance_completed', reference='DRILL-close')
    assert closed.status_code == 200 and closed.json()['phase'] == 'CLOSED'
    public = client.get(url, headers=drill['resident']).json()
    assert public['operational_enabled'] is False and public['closure_reason'] == 'assistance_completed'
    assert 'fallback_contacts' not in public and all('details' not in e and 'reason' not in e for e in public['events'])
    assert action(client, drill, 'contact_attempt').status_code == 409


def test_unavailable_primary_escalates_to_alternate_without_claiming_dispatch(client, drill):
    action(client, drill, 'assign', responder_id=drill['primary_id'])
    escalated = action(client, drill, 'unavailable', drill['primary'])
    assert escalated.status_code == 200, escalated.text
    data = escalated.json()
    assert data['assigned_to'] == drill['alternate_id'] and data['phase'] == 'ASSIGNED'
    assert data['attention'] == 'needs_review' and 'pending' in data['events'][-1]['message']
    assert action(client, drill, 'accept', drill['primary'], reference='DRILL-old-owner').status_code == 403
    assert action(client, drill, 'accept', drill['alternate'], reference='DRILL-alternate-accept').status_code == 200


def test_deadline_worker_is_bounded_durable_and_does_not_fabricate_arrival(client, drill):
    identity = drill['item']['id']
    action(client, drill, 'assign', responder_id=drill['primary_id'])
    now=utc_now()+timedelta(seconds=10)
    result = process_due(SessionLocal, now=now)
    assert result['processed'] == [identity] and result['external_messages_sent'] == 0
    assert process_due(SessionLocal, now=now)['processed'] == []
    assert client.get(f'/api/sos-response/{identity}', headers=drill['admin']).json()['assigned_to'] == drill['alternate_id']
    action(client, drill, 'accept', drill['alternate'], reference='DRILL-accepted')
    action(client, drill, 'depart', drill['alternate'], reference='DRILL-departed')
    process_due(SessionLocal, now=utc_now()+timedelta(seconds=20))
    current = client.get(f'/api/sos-response/{identity}', headers=drill['resident']).json()
    assert current['phase'] == 'EN_ROUTE' and current['attention'] == 'needs_review'
    assert not any(e['action']=='arrive' for e in current['events'])


def test_handoff_requires_new_responder_acceptance_and_closure_cannot_bypass_workflow(client, drill):
    identity = drill['item']['id']
    action(client, drill, 'assign', responder_id=drill['primary_id'])
    action(client, drill, 'accept', drill['primary'], reference='DRILL-accepted')
    result = action(client, drill, 'handoff', drill['primary'], responder_id=drill['alternate_id'])
    assert result.status_code == 200 and result.json()['phase'] == 'ASSIGNED'
    assert action(client, drill, 'depart', drill['alternate'], reference='DRILL-unaccepted').status_code == 409
    status = client.get(f'/api/sos/{identity}', headers=drill['admin']).json()
    assert client.patch(f'/api/sos/{identity}', headers=drill['admin'], json=dict(expected_version=status['version'], status='RESOLVED')).status_code == 409


def test_correlation_preserves_individual_requests_and_hides_other_residents(client, drill):
    created = client.post('/api/sos-response/incidents', headers=drill['admin'], json={'label':'Synthetic common drill incident','reason':'Reviewed same exercise scenario'})
    assert created.status_code == 201
    group = created.json()['id']
    result = action(client, drill, 'correlate', incident_id=group)
    assert result.json()['incident_reference'] == f'DRILL-{group}'
    other = headers(client.post('/api/auth/register', json=account('unrelated@example.com')))
    assert client.get(f'/api/sos-response/{drill["item"]["id"]}', headers=other).status_code == 404
    assert client.get('/api/sos-response/incidents', headers=drill['resident']).status_code == 403
    assert client.get('/api/sos-response/policy', headers=drill['resident']).status_code == 403
    with SessionLocal() as db: assert db.get(SosRequest, drill['item']['id']).request_id == drill['item']['request_id']


def test_policy_conflicts_hours_and_operational_injection_are_rejected(client, drill):
    assert client.patch('/api/sos-response/policy', headers=drill['admin'], json=drill['policy']).status_code == 409
    assert client.patch('/api/sos-response/policy', headers=drill['admin'], json={**drill['policy'], 'expected_version':1,'operational_enabled':True}).status_code == 422
    assert client.patch('/api/sos-response/policy', headers=drill['primary'], json={**drill['policy'],'expected_version':1}).status_code == 403
    with SessionLocal() as db:
        db.get(User, drill['primary_id']).is_active=False; db.commit()
    assert action(client, drill, 'assign', responder_id=drill['primary_id']).status_code == 422


def test_stale_response_action_does_not_append_or_overwrite(client, drill):
    identity=drill['item']['id']
    before=client.get(f'/api/sos-response/{identity}', headers=drill['admin']).json()
    action(client, drill, 'assign', responder_id=drill['primary_id'])
    stale=client.post(f'/api/sos-response/{identity}/actions', headers=drill['admin'], json=dict(
        expected_version=before['request_version'],action='assign',responder_id=drill['alternate_id'],reason='Stale competing assignment'))
    assert stale.status_code==409 and stale.json()['detail']['code']=='refresh_required'
    after=client.get(f'/api/sos-response/{identity}', headers=drill['admin']).json()
    assert len(after['events'])==len(before['events'])+1 and after['assigned_to']==drill['primary_id']


def test_additive_migration_preserves_existing_sos_and_never_activates_operations(tmp_path):
    bind=create_engine('sqlite:///'+str(tmp_path/'old-sos.db'))
    with bind.begin() as db:
        db.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        db.execute(text('CREATE TABLE sos_requests (id INTEGER PRIMARY KEY, practice BOOLEAN, status VARCHAR(20))'))
        db.execute(text("INSERT INTO sos_requests VALUES (42, 1, 'ACKNOWLEDGED')"))
    with pytest.raises(RuntimeError, match='migration required'): require_schema(bind)
    assert migrate(bind)['add_version'] and not migrate(bind)['operational_enabled']
    migrate(bind, apply=True); require_schema(bind)
    with bind.connect() as db: assert db.execute(text('SELECT id, practice, status, version FROM sos_requests')).one()==(42,1,'ACKNOWLEDGED',1)
    assert not migrate(bind, apply=True)['add_version']
    bind.dispose()


def test_two_deadline_workers_record_one_escalation(client, drill):
    identity=drill['item']['id']
    action(client, drill, 'assign', responder_id=drill['primary_id'])
    now=utc_now()+timedelta(seconds=10); barrier=Barrier(2)
    def sweep(_):
        barrier.wait(timeout=10)
        return process_due(SessionLocal, now=now)
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(sweep, range(2)))
    assert sum(r['processed'].count(identity) for r in results)==1
    with SessionLocal() as db:
        assert len(list(db.scalars(select(SosResponseEvent).where(SosResponseEvent.sos_id==identity,SosResponseEvent.action=='escalated'))))==1


def test_active_drill_uses_reviewed_snapshot_and_duty_expiry_rejects_new_assignment(client, drill, monkeypatch):
    updated={**drill['policy'],'expected_version':1,'acceptance_seconds':90}
    assert client.patch('/api/sos-response/policy',headers=drill['admin'],json=updated).status_code==200
    snapshot=client.get(f'/api/sos-response/{drill["item"]["id"]}',headers=drill['admin']).json()
    assert snapshot['policy_version']==1 and snapshot['policy']['acceptance_seconds']==5
    from app.services import sos_response as service
    later=utc_now()+timedelta(hours=2)
    monkeypatch.setattr(service,'utc_now',lambda:later)
    assert action(client,drill,'assign',responder_id=drill['primary_id']).status_code==422


def test_two_residents_can_share_incident_without_combining_their_requests(client, drill):
    other=headers(client.post('/api/auth/register',json=account('second-resident@example.com')))
    second=make_request(client,other)
    start=client.post(f'/api/sos-response/{second["id"]}/start',headers=drill['admin'],json=dict(
        expected_version=1,policy_version=1,reason='Second participant in shared drill'))
    assert start.status_code==200
    group=client.post('/api/sos-response/incidents',headers=drill['admin'],json=dict(label='Shared drill',reason='Reviewed correlation')).json()['id']
    action(client,drill,'correlate',incident_id=group)
    second_drill={**drill,'item':second}
    action(client,second_drill,'correlate',incident_id=group)
    public=client.get(f'/api/sos-response/{second["id"]}',headers=other).json()
    assert public['incident_reference']==f'DRILL-{group}' and 'request_ids' not in public
    assert client.get('/api/sos',headers=other).json()['total']==1
    assert client.get(f'/api/sos/{drill["item"]["id"]}',headers=other).status_code==404


def test_response_events_are_append_only_and_general_audit_identifies_actor(client, drill):
    identity=drill['item']['id']
    action(client,drill,'assign',responder_id=drill['primary_id'])
    audit=client.get('/api/auth/audit?subject_type=sos',headers=drill['admin']).json()
    assert any(e['action']=='drill_assign' and e['actor_id']==drill['coordinator_id'] and e['reason'] for e in audit)
    with SessionLocal() as db:
        event=db.scalar(select(SosResponseEvent).where(SosResponseEvent.sos_id==identity))
        event.reason='Attempted rewrite'
        with pytest.raises(ValueError,match='append-only'):db.commit()
        db.rollback()
