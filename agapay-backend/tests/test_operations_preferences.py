"""F17-F19: synthetic transport, lifecycle and persistent capability acceptance."""
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select, text
from app.database import SessionLocal
from app.models import Alert, NotificationDevice, NotificationDelivery, NotificationEvent, Telemetry
from app.governance_models import VerifiedArea, ResidentSubscription
from app.operations_models import StationDeliveryGate
from app.services.notification_service import process_pending
from app.services.notification_provider import FakeNotificationProvider
from app.migrate_operations_preferences import migrate
from test_accounts import account, headers, reset_accounts, staff
from test_alerts import payload
from test_notifications import register, registration, resident, rows
from test_rain_gauge import event
from test_station_security import device, mqtt_transport, deliver, token_headers


def operations(client, device):
    return client.get(f'/api/stations/{device[0]}/operations', headers=device[1]).json()


def transition(client, device, state, **changes):
    current = operations(client, device)
    return client.post(f'/api/stations/{device[0]}/lifecycle', headers=device[1], json=dict(
        expected_revision=current['revision'], expected_identity_version=current['identity_version'],
        state=state, reason='Synthetic acceptance lifecycle review', **changes))


def water(client, device, sequence, depth):
    return client.post('/api/telemetry', headers=token_headers(device[2]), json=payload(device[0], sequence, depth))


def test_admin_metadata_is_audited_and_stale_write_cannot_overwrite(client, device):
    path=f'/api/stations/{device[0]}/metadata'
    body=dict(expected_revision=operations(client,device)['revision'], station_name='Reviewed station', reason='Reviewed descriptive correction')
    assert client.patch(path,json=body).status_code==401
    assert client.patch(path,headers=resident(client),json=body).status_code==403
    assert client.patch(path,headers=staff(client,'officer'),json=body).status_code==403
    saved=client.patch(path,headers=device[1],json=body)
    assert saved.status_code==200 and saved.json()['station_name']=='Reviewed station'
    assert client.patch(path,headers=device[1],json={**body,'station_name':'Stale replacement'}).status_code==409
    assert operations(client,device)['station_name']=='Reviewed station'
    assert client.patch(path,headers=device[1],json={**body,'latitude':0}).status_code==422
    audit=client.get(f'/api/stations/{device[0]}/audit',headers=device[1]).json()
    assert any(a['action']=='station_metadata_updated' and a['actor_id']>0 and a['details']['after']['station_name']=='Reviewed station' for a in audit)


@pytest.mark.parametrize('state,accepted',[('active',True),('maintenance',True),('inactive',False),('decommissioned',False)])
def test_water_http_and_mqtt_and_rain_share_lifecycle(client,device,mqtt_transport,state,accepted):
    if state!='active':assert transition(client,device,state).status_code==200
    sub,acks,settings=mqtt_transport
    response=water(client,device,1,105)
    assert response.status_code==(201 if accepted else 401 if state=='decommissioned' else 403)
    deliver(sub,device[0],{'ingest_token':device[2]['ingest_token'],'telemetry':payload(device[0],2,106)})
    deliver(sub,device[0],{'ingest_token':device[2]['ingest_token'],'rain':event(station=device[0]).model_dump()},channel='rain')
    with SessionLocal() as db:
        samples=list(db.scalars(select(Telemetry).where(Telemetry.station_id==device[0])))
    assert len(samples)==(2 if accepted else 0)
    assert len(acks)==(2 if accepted else 0) # Independent committed water and rain receipts.
    assert {topic.rsplit('/',1)[-1] for topic,_ in acks}==({'telemetry-ack','rain-ack'} if accepted else set())
    assert Path(settings.rain_gauge_store_path).exists()==accepted
    contract=operations(client,device)
    assert contract['external_sensor_notifications']==(state=='active')
    assert 'offline' in contract['local_alarm_policy']


def test_maintenance_escalates_without_push_holds_recovery_and_retains_incident(client,device):
    access=resident(client);register(client,access)
    assert transition(client,device,'maintenance').status_code==200
    assert water(client,device,1,105).status_code==201
    for seq in range(2,7):assert water(client,device,seq,0).status_code==201
    with SessionLocal() as db:
        episode=db.scalar(select(Alert).where(Alert.station_id==device[0]))
        assert episode.status=='ACTIVE' and episode.current_severity=='EVACUATE'
        assert db.scalar(select(NotificationEvent)) is not None
        assert db.scalar(select(StationDeliveryGate)).external_allowed is False
        assert db.scalar(select(NotificationDelivery)) is None
    assert transition(client,device,'inactive').status_code==200
    with SessionLocal() as db:assert db.scalar(select(Alert).where(Alert.station_id==device[0])).status=='ACTIVE'
    monitored=client.get('/api/monitoring/stations',headers=device[1],params={'station_id':device[0]}).json()  # R5: own station only
    row=next(s for s in monitored['stations'] if s['station_id']==device[0])
    assert row['hazard_state']=='unresolved' and row['lifecycle']['state']=='inactive'


def test_pending_push_is_not_replayed_after_maintenance_reactivation(client,device):
    register(client,resident(client))
    assert water(client,device,1,105).status_code==201
    assert rows(NotificationDelivery)[0].state=='PENDING'
    assert transition(client,device,'maintenance').status_code==200
    assert transition(client,device,'active').status_code==200
    provider=FakeNotificationProvider();assert process_pending(provider)==1
    assert rows(NotificationDelivery)[0].state=='SUPPRESSED'
    assert provider.messages=={}


def test_lifecycle_conflicts_and_permissions_require_manual_review(client,device):
    current=operations(client,device)
    path=f'/api/stations/{device[0]}/lifecycle'
    body=dict(expected_revision=current['revision'],expected_identity_version=current['identity_version'],state='inactive',reason='Controlled acceptance update')
    assert client.post(path,json=body).status_code==401
    assert client.post(path,headers=resident(client),json=body).status_code==403
    assert transition(client,device,'maintenance').status_code==200
    assert client.post(path,headers=device[1],json=body).status_code==409
    assert operations(client,device)['state']=='maintenance'


def test_persistent_preferences_use_verified_ids_and_do_not_subscribe_or_translate(client):
    access=resident(client)
    with SessionLocal() as db:
        db.add(VerifiedArea(id='TEST_AREA',name='Synthetic verified geographic fixture',identifier_scheme='test-only',evidence='Synthetic registry review',area_class='geographic',active=True));db.commit()
    initial=client.get('/api/auth/preferences',headers=access).json()
    assert initial['revision']==0 and initial['supported_locales']==['en']
    assert 'unavailable' in initial['translation_status']
    assert client.patch('/api/auth/preferences',headers=access,json={'expected_revision':0,'locale':'fil'}).status_code==422
    for invalid_area in ['free text','', '   ']:
        assert client.patch('/api/auth/preferences',headers=access,json={'expected_revision':0,'resident_area_id':invalid_area}).status_code==422
    changes=dict(expected_revision=0,resident_area_id='TEST_AREA',requested_language='Community requested language')
    saved=client.patch('/api/auth/preferences',headers=access,json=changes)
    assert saved.status_code==200 and saved.json()['locale']=='en'
    assert client.patch('/api/auth/preferences',headers=access,json={**changes,'requested_language':'Stale replacement'}).status_code==409
    persisted=client.get('/api/auth/preferences',headers=access).json()
    assert persisted['resident_area_id']=='TEST_AREA' and persisted['requested_language']=='Community requested language'
    with SessionLocal() as db:assert db.scalar(select(ResidentSubscription)) is None


def test_delivery_off_disables_all_registrations_and_queued_critical_cannot_replay(client,device):
    access=resident(client);register(client,access)
    register(client,access,token='another-synthetic-test-token',installation='00000000-0000-4000-8000-000000000002')
    assert water(client,device,1,105).status_code==201
    assert len(rows(NotificationDelivery))==2
    result=client.patch('/api/auth/preferences',headers=access,json=dict(expected_revision=0,notifications_enabled=False))
    assert result.status_code==200 and result.json()['notifications_enabled'] is False
    assert all(not d.enabled and d.provider_token is None for d in rows(NotificationDevice))
    assert client.post('/api/notification-devices',headers=access,json=registration()).status_code==409
    assert client.patch('/api/auth/preferences',headers=access,json=dict(expected_revision=1,notifications_enabled=True)).status_code==200
    register(client,access)
    provider=FakeNotificationProvider();process_pending(provider)
    assert all(d.state=='SUPPRESSED' for d in rows(NotificationDelivery)) and provider.messages=={}


def test_additive_migration_inspects_then_preserves_existing_rows(tmp_path):
    bind=create_engine('sqlite:///'+str(tmp_path/'migration.db'))
    with bind.begin() as db:
        for table in ('stations','users','notification_events','verified_areas'):db.execute(text(f'CREATE TABLE {table}(id INTEGER PRIMARY KEY, station_id TEXT UNIQUE)'))
        db.execute(text('INSERT INTO stations(id,station_id) VALUES(1,\'PRESERVED\')'))
    assert len(migrate(bind))==3
    assert len(migrate(bind,apply=True))==3
    assert migrate(bind,apply=True)==[]
    with bind.connect() as db:assert db.execute(text('SELECT station_id FROM stations')).scalar()=='PRESERVED'
