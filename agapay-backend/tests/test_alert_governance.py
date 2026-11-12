from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.database import SessionLocal
from app.governance_models import (GovernanceAudit, HazardDecision, HazardPolicy, NotificationAudience,
    ResidentSubscription, VerifiedArea)
from app.models import Alert, NotificationDelivery, User, utc_now
from app.services.notification_provider import FakeNotificationProvider
from app.services.notification_service import process_pending
from test_accounts import account, headers, reset_accounts, staff
from test_alerts import episodes, transitions
from test_notifications import registration
from station_support import device_token, ordering_fields


@pytest.fixture
def governed(client):
    from app.models import Station
    station_id = 'GOV_' + uuid4().hex[:10].upper()
    with SessionLocal() as db:
        db.add(Station(station_id=station_id, station_name='Synthetic governance station', barangay='Free text locality'))
        db.commit()
    token = device_token(station_id)
    with SessionLocal() as db:
        db.delete(db.get(HazardPolicy, station_id))
        db.commit()
    origin = utc_now() - timedelta(seconds=90)
    def send(sequence, depth, *, seconds=None):
        payload = dict(**ordering_fields(station_id, sequence), station_id=station_id,
            sequence_no=sequence, device_uptime_ms=sequence*5000, firmware_version='1.0.0-synthetic',
            sensor_quality='valid' if depth is not None else 'invalid', water_depth_cm=depth, rainfall_mm=0)
        payload['measured_at'] = (origin + timedelta(seconds=sequence*5 if seconds is None else seconds)).isoformat()
        result = client.post('/api/telemetry', json=payload, headers={'Authorization': 'Bearer '+token})
        assert result.status_code == 201, result.text
        return result.json()
    return station_id, send


@pytest.fixture
def issuer(client, governed):
    access = staff(client)
    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == 'admin'))
        actor_id = actor.id
    for code in ['AREA_A', 'AREA_B']:
        response = client.post('/api/alert-governance/areas', headers=access, json=dict(
            id=code, name='Synthetic '+code, identifier_scheme='AGAPAY exercise identifiers',
            evidence='Synthetic area for isolated tests only; no geographic exposure claim', reason='Explicit synthetic registry setup'))
        assert response.status_code == 201, response.text
    response = client.post('/api/alert-governance/authorities', headers=access, json=dict(
        id='APP', name='AGAPAY App Operations', authority_class='app_operator',
        evidence='Internal prototype authority for application advisories only', reason='Configure synthetic application issuer'))
    assert response.status_code == 201, response.text
    response = client.post('/api/alert-governance/authorities/APP/grants', headers=access, json=dict(
        user_id=actor_id, area_ids=['AREA_A'], station_ids=[governed[0]], citywide=True,
        expected_revision=0, reason='Explicit synthetic staff jurisdiction'))
    assert response.status_code == 200, response.text
    response = client.post(f'/api/alert-governance/stations/{governed[0]}/areas', headers=access,
        json=dict(area_ids=['AREA_A'], reason='Explicit tested affected-area mapping'))
    assert response.status_code == 200
    return access


def test_provisional_noise_does_not_chatter_and_sustained_recovery_resolves(client, governed):
    station, send = governed
    for seq, depth in enumerate([59.9, 60.1, 59.9, 60.1, 57, 57, 57], 1):
        send(seq, depth)
    episode, = episodes(station)
    assert episode.status == 'RESOLVED'
    assert [t.new_severity for t in transitions(station)] == ['ADVISORY', 'NORMAL']
    assert client.get(f'/api/stations/{station}/hazard-policy', headers=staff(client)).json()['state'] == 'provisional'


def test_critical_jump_is_immediate_even_if_implausible_and_invalid_never_recovers(governed):
    station, send = governed
    send(1, 1)
    send(2, 105, seconds=5.01)
    assert episodes(station)[0].current_severity == 'EVACUATE'
    with SessionLocal() as db:
        decision = db.scalar(select(HazardDecision).where(HazardDecision.station_id == station).order_by(HazardDecision.telemetry_id.desc()))
        assert decision.review_required and decision.reason == 'immediate_escalation_review'
    for sequence, depth in enumerate([50, 50, None, 50, 50], 3):
        send(sequence, depth)
    assert episodes(station)[0].current_severity == 'EVACUATE'
    send(8, 50)
    assert episodes(station)[0].status == 'RESOLVED'


def test_downward_spike_cannot_clear_critical_episode(governed):
    station, send = governed
    send(1, 105)
    send(2, 1, seconds=5.01)
    assert episodes(station)[0].current_severity == 'EVACUATE'
    with SessionLocal() as db:
        decisions = list(db.scalars(select(HazardDecision).where(HazardDecision.station_id == station).order_by(HazardDecision.telemetry_id)))
        assert decisions[-1].reason == 'implausible_recovery_held'


def test_gap_restarts_recovery_and_all_exit_bands_are_checked(governed):
    station, send = governed
    send(1, 105)
    for seq, depth in enumerate([59.9, 59.9, 59.9, 60.1], 2):
        send(seq, depth)
    assert episodes(station)[0].current_severity == 'ADVISORY'
    send(6, 57)
    send(7, 57, seconds=55)  # Gap exceeds 15 seconds.
    send(8, 57, seconds=60)
    assert episodes(station)[0].status == 'ACTIVE'
    send(9, 57, seconds=65)
    assert episodes(station)[0].status == 'RESOLVED'


def test_station_policy_is_versioned_authorized_and_audited(client, governed, issuer):
    station, _ = governed
    from app.services.hazard_policy import PROVISIONAL_RULES
    body = dict(expected_version=0, rules={**PROVISIONAL_RULES, 'advisory_hysteresis_cm': 3},
                validation_evidence='Synthetic operator test evidence; not physical validation', reason='Test station-specific recovery configuration')
    assert client.post(f'/api/stations/{station}/hazard-policy', json=body).status_code == 401
    response = client.post(f'/api/stations/{station}/hazard-policy', json=body, headers=issuer)
    assert response.status_code == 200, response.text
    assert response.json()['version'] == 1
    assert client.post(f'/api/stations/{station}/hazard-policy', json=body, headers=issuer).status_code == 409
    records = client.get('/api/alert-governance/audit', headers=issuer).json()
    assert any(row['action'] == 'hazard_policy_approved' for row in records)


def resident_device(client, email):
    result = client.post('/api/auth/register', json=account(email))
    access = headers(result)
    response = client.post('/api/notification-devices', headers=access,
        json=registration(token='synthetic-token-'+email.replace('@','-'), installation=str(uuid4())))
    assert response.status_code == 200, response.text
    return access, response.json()['id']


def subscribe(client, access, kind, target, enabled=True, revision=0):
    return client.post('/api/alert-subscriptions', headers=access,
        json=dict(kind=kind, target_id=target, enabled=enabled, expected_revision=revision))


def test_only_explicit_station_or_verified_area_subscribers_receive(client, governed, issuer):
    station, send = governed
    one, device_one = resident_device(client, 'one@example.com')
    two, device_two = resident_device(client, 'two@example.com')
    three, device_three = resident_device(client, 'three@example.com')
    four, device_four = resident_device(client, 'four@example.com')
    assert subscribe(client, one, 'station', station).status_code == 200
    assert subscribe(client, two, 'area', 'AREA_A').status_code == 200
    assert subscribe(client, three, 'area', 'AREA_B').status_code == 200
    assert subscribe(client, four, 'area', 'Free text locality').status_code == 422
    send(1, 105)
    with SessionLocal() as db:
        assert set(db.scalars(select(NotificationDelivery.device_id))) == {device_one, device_two}
    # Profile text cannot silently enroll or change a push audience.
    assert client.patch('/api/auth/me', headers=four, json={'expected_version':1,'barangay': 'AREA_A'}).status_code == 200
    assert subscribe(client, one, 'station', station, enabled=False, revision=1).status_code == 200
    assert subscribe(client, one, 'station', station, enabled=True, revision=1).status_code == 409
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 2
    with SessionLocal() as db:
        states = {row.device_id: row.state for row in db.scalars(select(NotificationDelivery))}
        assert states[device_one] == 'SUPPRESSED' and states[device_two] == 'TESTED'


def test_no_subscription_means_no_delivery_and_no_legacy_broadcast(client, governed):
    station, send = governed
    resident_device(client, 'none@example.com')
    send(1, 105)
    with SessionLocal() as db:
        assert db.scalar(select(NotificationAudience)) is not None
        assert db.scalar(select(NotificationDelivery)) is None


def test_citywide_requires_issuer_grant_and_reason_and_is_audited_once(client, governed, issuer):
    station, send = governed
    access, device = resident_device(client, 'city@example.com')
    send(1, 105)
    transition = transitions(station)[0]
    body = dict(authority_id='APP', reason='Explicit synthetic citywide override for this escalation', expires_at=(utc_now()+timedelta(minutes=10)).isoformat())
    path = f'/api/alert-governance/transitions/{transition.id}/citywide'
    assert client.post(path, json=body, headers=access).status_code == 403
    assert client.post(path, json={**body, 'reason':'short'}, headers=issuer).status_code == 422
    result = client.post(path, json=body, headers=issuer)
    assert result.status_code == 200 and result.json()['new_recipients'] == 1, result.text
    assert client.post(path, json=body, headers=issuer).status_code == 409
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 1
    with SessionLocal() as db:
        assert db.scalar(select(NotificationDelivery.state)) == 'TESTED'
        assert db.scalar(select(GovernanceAudit).where(GovernanceAudit.action == 'citywide_dispatch'))


def notice_body(**changes):
    return dict(authority_id='APP', area_ids=['AREA_A'], message_type='Alert', category='advisory', status='Test',
        urgency='Expected', severity='Moderate', certainty='Possible', headline='Synthetic application advisory',
        instruction='Exercise only. Check official local authority instructions.', reason='Test issuer lifecycle only',
        effective_at=(utc_now()-timedelta(seconds=1)).isoformat(), expires_at=(utc_now()+timedelta(hours=1)).isoformat(), **changes)


def test_resident_notice_scope_filters_before_pagination_and_preserves_cancellation(client, governed, issuer):
    from app.governance_models import OfficialNotice
    actual={**notice_body(),'status':'Actual'}
    first=client.post('/api/official-notices',headers=issuer,json=actual).json()
    cancellation=client.post('/api/official-notices',headers=issuer,json={**actual,'message_type':'Cancel','reference_id':first['id']}).json()
    client.post('/api/official-notices',headers=issuer,json=notice_body())
    with SessionLocal() as db:
        actor=db.scalar(select(User).where(User.role=='admin'))
        for index in range(55):
            db.add(OfficialNotice(authority_id='APP',issued_by=actor.id,issuer_name='Synthetic issuer',authority_class='app_operator',
                area_ids=['AREA_A_EXTRA'],area_names=['Different area'],message_type='Alert',category='advisory',status='Actual',
                urgency='Expected',severity='Moderate',certainty='Possible',headline=f'Synthetic other-area {index}',instruction='Synthetic only',reason='Isolated filter regression',
                effective_at=utc_now()-timedelta(minutes=1),expires_at=utc_now()+timedelta(hours=1)))
        db.commit()
    path='/api/official-notices?area_id=AREA_A&status=Actual&current_only=true&limit=1'
    assert client.get(path).status_code==401
    response=client.get(path,headers=issuer).json()
    assert [n['id'] for n in response['items']]==[cancellation['id']]
    assert response['items'][0]['lifecycle']=='cancelled' and not response['has_more']
    assert response['scope']=={'area_id':'AREA_A','status':'Actual','current_only':True}
    history=client.get('/api/official-notices?area_id=AREA_A&status=Actual&limit=1',headers=issuer).json()
    assert history['has_more']
    older=client.get('/api/official-notices?area_id=AREA_A&status=Actual&limit=1&offset=1',headers=issuer).json()
    assert older['items'][0]['id']==first['id'] and older['items'][0]['lifecycle']=='superseded'
    with SessionLocal() as db:
        db.get(OfficialNotice,cancellation['id']).expires_at=utc_now()-timedelta(seconds=1);db.commit()
    assert client.get(path,headers=issuer).json()['items']==[]


def test_notice_issuer_jurisdiction_and_lifecycle_never_come_from_sensor_tiers(client, governed, issuer):
    body = notice_body()
    assert client.post('/api/official-notices', json=body).status_code == 401
    assert client.post('/api/official-notices', json={**body, 'area_ids':['AREA_B']}, headers=issuer).status_code == 403
    assert client.post('/api/official-notices', json={**body, 'category':'action', 'status':'Actual'}, headers=issuer).status_code == 403
    response = client.post('/api/official-notices', json=body, headers=issuer)
    assert response.status_code == 201, response.text
    initial = response.json()
    assert initial['issuer_name'] == 'AGAPAY App Operations' and initial['lifecycle'] == 'effective'
    corrected = {**body, 'message_type':'Update', 'reference_id': initial['id'], 'headline':'Corrected exercise advisory'}
    result = client.post('/api/official-notices', json=corrected, headers=issuer)
    assert result.status_code == 201, result.text
    assert client.post('/api/official-notices', json=corrected, headers=issuer).status_code == 409
    cancelled = client.post('/api/official-notices', headers=issuer,
        json={**body, 'message_type':'Cancel', 'reference_id':result.json()['id'], 'headline':'Exercise advisory cancelled'})
    assert cancelled.status_code == 201, cancelled.text
    records = client.get('/api/official-notices', headers=issuer).json()['items']
    assert {row['lifecycle'] for row in records} == {'cancelled','superseded'}
    assert all(row['kind'] == 'official_notice' and row['authority_class'] == 'app_operator' for row in records)
    governed[1](1, 105)
    assert len(client.get('/api/official-notices', headers=issuer).json()['items']) == 3


def test_additive_migration_preserves_existing_data():
    from sqlalchemy import create_engine
    from app.models import Base, Station
    from app.migrate_alert_governance import migrate
    engine = create_engine('sqlite://')
    core = [table for table in Base.metadata.sorted_tables if not table.name.startswith(('hazard_', 'governance_', 'verified_', 'station_areas', 'alert_authorities', 'authority_', 'resident_subscriptions', 'official_', 'notification_audiences', 'notification_recipients', 'citywide_'))]
    Base.metadata.create_all(engine, tables=core)
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        db.add(Station(station_id='PRESERVE', station_name='Preserved station'))
        db.commit()
    assert migrate(engine)
    migrate(engine, apply=True)
    assert not migrate(engine)
    with Session(engine) as db:
        assert db.scalar(select(Station.station_name)) == 'Preserved station'
        assert db.scalar(select(ResidentSubscription)) is None


def test_area_rebinding_cannot_replay_a_previously_captured_delivery(client, governed, issuer):
    station, send = governed
    access, device = resident_device(client, 'rebind@example.com')
    assert subscribe(client, access, 'area', 'AREA_A').status_code == 200
    send(1, 105)
    path = f'/api/alert-governance/stations/{station}/areas/AREA_A/revoke'
    response = client.post(path, headers=issuer, json=dict(expected_revision=1, reason='Synthetic mapping correction before delivery'))
    assert response.status_code == 200, response.text
    binding_path = f'/api/alert-governance/stations/{station}/areas'
    assert client.post(binding_path, headers=issuer, json=dict(area_ids=['AREA_A'], reason='Attempt stale mapping rebind')).status_code == 409
    response = client.post(binding_path, headers=issuer, json=dict(area_ids=['AREA_A'], expected_revisions={'AREA_A':2}, reason='Explicit synthetic mapping rebind'))
    assert response.status_code == 200, response.text
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 1 and not provider.messages
    with SessionLocal() as db:
        assert db.scalar(select(NotificationDelivery.state).where(NotificationDelivery.device_id == device)) == 'SUPPRESSED'


def test_bootstrap_is_an_app_issuer_without_automatic_subscriptions_or_geographic_claims(client, governed):
    access = staff(client)
    from app.bootstrap_prototype_governance import bootstrap, AREA_ID, AUTHORITY_ID
    from app.governance_models import AlertAuthority, AuthorityGrant
    with SessionLocal() as db:
        plan = bootstrap(db, admin_email='admin@example.com', station_ids=[governed[0]])
        assert plan['apply'] is False and db.get(AlertAuthority, AUTHORITY_ID) is None
        bootstrap(db, admin_email='admin@example.com', station_ids=[governed[0]], apply=True)
        assert db.get(AlertAuthority, AUTHORITY_ID).authority_class == 'app_operator'
        assert db.get(VerifiedArea, AREA_ID).area_class == 'application'
        assert db.scalar(select(ResidentSubscription)) is None
        grant = db.scalar(select(AuthorityGrant).where(AuthorityGrant.authority_id == AUTHORITY_ID))
        assert grant.citywide is False


def test_manual_review_requires_jurisdiction_and_current_measurement_without_rewriting_sensor_history(client, governed, issuer):
    station, send = governed
    first = send(1, 105)
    episode = episodes(station)[0]
    body = dict(authority_id='APP', expected_telemetry_id=first['id'], action='request_escalation',
        requested_severity='EVACUATE', reason='Synthetic operator requests review of critical sensor episode')
    path = f'/api/sensor-alerts/{episode.id}/reviews'
    send(2, 104)
    assert client.post(path, headers=issuer, json=body).status_code == 409
    body['expected_telemetry_id'] = episodes(station)[0].latest_telemetry_id
    response = client.post(path, headers=issuer, json=body)
    assert response.status_code == 200, response.text
    assert response.json()['sensor_episode_unchanged'] is True
    assert [t.new_severity for t in transitions(station)] == ['EVACUATE']
