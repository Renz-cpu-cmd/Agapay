from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
from types import SimpleNamespace
import paho.mqtt.client as mqtt
import pytest
from app.config import Settings,get_settings
from app.database import SessionLocal
from app.main import app
from app.models import Station,Alert,Telemetry
from app.rain_schemas import RainCounterEvent
from app.services.rain_gauge_service import RainGaugeStore
from app.services.mqtt_subscriber import start_mqtt_subscriber
from test_accounts import reset_accounts

NOW=datetime(2026,10,12,1,0,tzinfo=timezone.utc)


def event(count=0,sequence=1,uptime=0,boot='BOOT_A',start=0,source='physical_rain_gauge',station='RAIN_TEST',**changes):
    payload={'station_id':station,'boot_id':boot,'packet_sequence':sequence,'cumulative_tip_count':count,
             'boot_start_tip_count':start,'interval_start_tip_count':start,'mm_per_tip':.7,
             'rainfall_increment_mm':(count-start)*.7,'device_uptime_ms':uptime,
             'last_tip_uptime_ms':uptime if count>start else None,'interval_start_uptime_ms':0,
             'counter_persisted':True,'data_source':source,'firmware_version':'0.2.0'}
    payload.update(changes)
    return RainCounterEvent.model_validate(payload)


def test_single_tip_duplicate_and_consecutive_counts(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.db');store.ingest(event(),.7,now=NOW)
    first=event(1,2,1000);assert store.ingest(first,.7,now=NOW+timedelta(seconds=1))['delta_tips']==1
    assert store.ingest(first,.7,now=NOW+timedelta(seconds=2))['duplicate']
    store.ingest(event(2,3,2000),.7,now=NOW+timedelta(seconds=2))
    snap=store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(seconds=2),anchor_at=NOW)
    assert snap['accepted_tip_count']==2 and snap['session_rainfall_mm']==pytest.approx(1.4)
    assert snap['rainfall_after_anchor_mm']==pytest.approx(1.4)
    assert snap['incomplete_hour_mm']==pytest.approx(1.4)
    assert not snap['ml_ready'] and all(h['rainfall_mm'] is None for h in snap['completed_hours'])
    assert all(h['interval_seconds']==3600 for h in snap['completed_hours'])


def test_restart_has_no_false_increment_and_persistence(tmp_path):
    path=tmp_path/'rain.db';store=RainGaugeStore(path)
    store.ingest(event(),.7,now=NOW);store.ingest(event(1,2,1000),.7,now=NOW+timedelta(seconds=1))
    store=RainGaugeStore(path)
    result=store.ingest(event(1,1,0,boot='BOOT_B',start=1),.7,now=NOW+timedelta(seconds=2))
    assert result['delta_tips']==0
    store.ingest(event(2,2,1000,boot='BOOT_B',start=1),.7,now=NOW+timedelta(seconds=3))
    assert store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(seconds=3))['accepted_tip_count']==2
    with pytest.raises(ValueError):store.ingest(event(0,1,0,boot='COUNTER_ERASED'),.7,now=NOW+timedelta(seconds=4))


def test_outage_recovery_retains_rain_but_not_hourly_ground_truth(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.db');store.ingest(event(),.7,now=NOW)
    store.ingest(event(3,2,3601000),.7,now=NOW+timedelta(hours=1,seconds=1))
    snap=store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(hours=1,seconds=1))
    assert snap['accepted_tip_count']==3 and snap['unallocated_recovered_mm']==pytest.approx(2.1)
    assert snap['incomplete_hour_mm']==0 and not snap['ml_ready']
    assert store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(hours=1,seconds=1),anchor_at=NOW)['rainfall_after_anchor_mm']==0
    stale=store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(days=2))
    assert not stale['connected'] and stale['accepted_tip_count']==3


def test_calibration_and_conflicting_packet_rejected(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.db');store.ingest(event(),.7,now=NOW)
    with pytest.raises(ValueError):store.ingest(event(1,2,1000),.2,now=NOW+timedelta(seconds=1))
    store.ingest(event(1,2,1000),.7,now=NOW+timedelta(seconds=1))
    with pytest.raises(ValueError):store.ingest(event(2,2,1000),.7,now=NOW+timedelta(seconds=2))
    with pytest.raises(ValueError):event(1,3,2000,rainfall_increment_mm=99)


def test_completed_hours_require_real_continuous_coverage(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.db')
    # Proven heartbeat coverage may establish zero-rain hours; no missing slots are filled.
    for seq in range(24*120+1):
        store.ingest(event(0,seq+1,seq*30000),.7,now=NOW+timedelta(seconds=seq*30))
    snapshot=store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(hours=24))
    assert snapshot['ml_ready'] and len(snapshot['completed_hours'])==24
    assert all(h['rainfall_mm']==0 for h in snapshot['completed_hours'])
    assert snapshot['completed_hours'][-1]['timestamp_utc']==(NOW+timedelta(hours=24)).isoformat()
    from rain_reference import RawReference
    original=RawReference(store.path).snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(hours=24))
    assert snapshot['completed_hours']==original['completed_hours']


def test_simulated_source_cannot_mix_with_physical(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.db');store.ingest(event(),.7,now=NOW)
    store.ingest(event(5,1,1000,source='simulated_rain_gauge'),.7,now=NOW+timedelta(seconds=1))
    assert store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(seconds=1))['accepted_tip_count']==0


def test_mqtt_callback_deduplicates_and_never_creates_safety_alerts(client,tmp_path,monkeypatch):
    from station_support import device_token
    station='RAIN_MQTT';settings=Settings(rain_gauge_enabled=True,rain_gauge_store_path=str(tmp_path/'rain.db'),rain_gauge_calibrations={station:.7},mqtt_username='test-backend',mqtt_password='test-broker-only')
    with SessionLocal() as db:db.add(Station(station_id=station,station_name='Test-only rain station'));db.commit()
    monkeypatch.setattr(mqtt.Client,'connect_async',lambda *a,**k:None)
    monkeypatch.setattr(mqtt.Client,'loop_start',lambda *a,**k:None)
    acknowledgements=[]
    monkeypatch.setattr(mqtt.Client,'publish',lambda self,topic,payload,**kwargs:acknowledgements.append((topic,json.loads(payload))))
    sub=start_mqtt_subscriber(settings)
    token=device_token(station)
    def deliver(payload):sub.on_message(sub,None,SimpleNamespace(topic=f'agapay/stations/{station}/rain',payload=json.dumps({'ingest_token':token,'rain':payload.model_dump()}).encode()))
    deliver(event(station=station));tip=event(1,2,1000,station=station);deliver(tip);deliver(tip)
    sub.on_message(sub,None,SimpleNamespace(topic=f'agapay/stations/{station}/rain',retain=True,payload=event(5,3,2000,station=station).model_dump_json().encode()))
    store=RainGaugeStore(Path(settings.rain_gauge_store_path));assert store.snapshot(station,'physical_rain_gauge')['accepted_tip_count']==1
    assert len(acknowledgements)==3
    from app.services import rain_rollups
    summarize=rain_rollups.summarize
    def fail_summary(*args):summarize(*args);raise RuntimeError('Synthetic pre-commit summary failure')
    monkeypatch.setattr(rain_rollups,'summarize',fail_summary)
    next_tip=event(2,3,2000,station=station);deliver(next_tip)
    assert len(acknowledgements)==3
    assert store.snapshot(station,'physical_rain_gauge')['accepted_tip_count']==1
    monkeypatch.setattr(rain_rollups,'summarize',summarize);deliver(next_tip)
    assert len(acknowledgements)==4
    assert store.snapshot(station,'physical_rain_gauge')['accepted_tip_count']==2
    with SessionLocal() as db:
        assert db.query(Alert).filter(Alert.station_id==station).count()==0
        assert db.query(Telemetry).filter(Telemetry.station_id==station).count()==0
        # Children first: PostgreSQL enforces every foreign key into this station's rows.
        from station_support import purge_station
        purge_station(db,station);db.commit()


def test_snapshot_api_requires_auth_and_registered_station(client,tmp_path):
    from test_accounts import staff
    config=Settings(rain_gauge_enabled=True,rain_gauge_store_path=str(tmp_path/'rain.db'),rain_gauge_allow_simulator=False)
    app.dependency_overrides[get_settings]=lambda:config
    try:
        assert client.get('/api/rain-gauge/STATION_001').status_code==401
        auth=staff(client,role='officer')
        assert client.get('/api/rain-gauge/UNKNOWN',headers=auth).status_code==404
        assert client.get('/api/rain-gauge/STATION_001',headers=auth).status_code==200
        assert client.get('/api/rain-gauge/STATION_001?source=simulated_rain_gauge',headers=auth).status_code==403
    finally:app.dependency_overrides.pop(get_settings,None)


def test_legacy_journal_is_unavailable_to_api_channels_and_hybrid_until_explicit_upgrade(client,tmp_path):
    from test_accounts import staff
    from app.services.channel_health import rain_health
    path=tmp_path/'legacy.db';store=RainGaugeStore(path)
    with store.connect() as db:db.execute('PRAGMA user_version=0')
    config=Settings(rain_gauge_enabled=True,rain_gauge_store_path=str(path),hybrid_projection_enabled=True)
    app.dependency_overrides[get_settings]=lambda:config
    try:
        auth=staff(client,role='officer')
        result=client.get('/api/rain-gauge/STATION_001',headers=auth)
        assert result.status_code==503 and 'diagnostics' in result.json()['detail']
        result=client.get('/api/hybrid-projections/STATION_001/summary',headers=auth)
        assert result.status_code==200 and result.json()['status']=='unavailable' and result.json().get('rain_activity') is None
        with SessionLocal() as db:
            row=db.query(Station).filter(Station.station_id=='STATION_001').one()
            assert rain_health(db,row,None,config,NOW)['state']=='unknown'
    finally:app.dependency_overrides.pop(get_settings,None)
