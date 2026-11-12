from datetime import timedelta
from types import SimpleNamespace
from pathlib import Path
import json
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.device_config import Installation,StationConfiguration,configuration_hash
from app.models import Station,Telemetry,StationCredential,Alert,utc_now
from app.schemas import TelemetryCreate
from app.services.telemetry_service import ingest_telemetry,DuplicateTelemetryError,ConflictingTelemetryError
from app.services.rain_gauge_service import RainGaugeStore
from test_channel_trend_reports import scoped
from test_accounts import staff,reset_accounts
from test_rain_gauge import event,NOW


def installation(**changes):
    return dict(datum="Synthetic test datum",installation_height_cm=150,sensor_min_cm=20,sensor_max_cm=450,
        uncertainty_cm=2,range_margin_cm=5,advisory_cm=60,warning_cm=85,critical_cm=100,rain_mm_per_tip=.7,**changes)


def configure(client,station):
    access=staff(client)
    body=dict(expected_revision=0,installation=installation(),validation_status="prototype",
        evidence="Synthetic software geometry, not measured field approval",reason="Regression fixture",effective_at=utc_now().isoformat())
    result=client.post(f'/api/stations/{station}/configuration',json=body,headers=access)
    assert result.status_code==201,result.text
    return result.json(),body,access


def payload(station,hash_value,**changes):
    now=utc_now()
    return dict(station_id=station,schema_version=3,config_version=1,source_id='TEST_'+station,
        boot_id='V3_BOOT',boot_sequence=1,sequence_no=1,device_uptime_ms=1000,measured_at=now.isoformat(),
        water_depth_cm=105,rainfall_mm=None,rainfall_interval=None,applied_config_hash=hash_value,
        sensor_quality='valid',firmware_version='0.3.0',**changes)


def test_geometry_requires_margin_without_lowering_critical_threshold():
    assert Installation(**installation()).critical_cm==100
    with pytest.raises(ValueError,match="margin"):
        Installation(**{**installation(),'installation_height_cm':120})
    with pytest.raises(ValueError,match="far-range"):
        Installation(**{**installation(),'installation_height_cm':449})


def test_configuration_requires_admin_version_review_and_exposes_application_mismatch(client,scoped):
    station=scoped[0]
    config,body,access=configure(client,station)
    route=f'/api/stations/{station}/configuration'
    assert client.post(route,json=body).status_code==401
    assert client.post(route,json=body,headers=access).status_code==409
    assert config['config_hash']==configuration_hash(station,1,Installation(**installation()).model_dump(mode='json'))
    assert config['status']=='missing' and config['validation_status']=='prototype'
    with SessionLocal() as db:
        credential=db.scalar(select(StationCredential).where(StationCredential.station_id==station))
        wrong=TelemetryCreate(**payload(station,'0'*64))
        row=ingest_telemetry(db,wrong,credential_id=credential.id)
        assert not row.eligible_for_current and row.disposition=='configuration_mismatch'
        assert db.scalar(select(Alert.id).where(Alert.station_id==station)) is None
        correct=TelemetryCreate(**{**payload(station,config['config_hash']),'sequence_no':2,'device_uptime_ms':2000})
        row=ingest_telemetry(db,correct,credential_id=credential.id)
        assert row.eligible_for_current and row.rainfall_mm is None
        with pytest.raises(DuplicateTelemetryError):
            ingest_telemetry(db,correct,credential_id=credential.id)
        with pytest.raises(ConflictingTelemetryError):
            ingest_telemetry(db,correct.model_copy(update={'sensor_fault':'no_echo'}),credential_id=credential.id)
        bench=TelemetryCreate(**{**payload(station,config['config_hash']),'sequence_no':3,'device_uptime_ms':3000,'local_alert_profile':'cardboard_bench','water_depth_cm':0})
        row=ingest_telemetry(db,bench,credential_id=credential.id)
        assert not row.eligible_for_current and row.disposition=='exercise_local_outputs'
        late=TelemetryCreate(**{**payload(station,'0'*64),'sequence_no':4,'device_uptime_ms':4000,'measured_at':(utc_now()-timedelta(hours=1)).isoformat()})
        assert ingest_telemetry(db,late,credential_id=credential.id).disposition=='stale_measurement'
    snapshot=client.get('/api/monitoring/stations',headers=access,params={'station_id':station}).json()  # R5: own station only
    view=next(s for s in snapshot['stations'] if s['station_id']==station)
    assert view['configuration']['status']=='matched'
    assert view['configuration']['local_alert_profile']=='cardboard_bench'
    assert view['current_depth_cm']==105  # Bench output mode cannot imply operational recovery.
    assert not view['depth_fresh'] and not view['depth_source_trusted']
    assert view['hazard_state']=='unresolved'
    assert view['latest_rainfall_mm'] is None and view['rainfall_product']['quality']=='unknown'
    assert view['threshold_evacuate_cm']==100


def test_v3_explicit_rainfall_conserves_counts_and_bounds_time():
    stamp=utc_now()
    observation=dict(interval_start=(stamp-timedelta(seconds=5)).isoformat(),interval_end=stamp.isoformat(),tip_count=2,
        mm_per_tip=.7,calibration_version='a'*64,quality='valid',source='physical_rain_gauge')
    body={**payload('RAIN_V3','a'*64),'measured_at':stamp.isoformat(),'rainfall_interval':observation,'rainfall_mm':1.4}
    parsed=TelemetryCreate(**body)
    assert parsed.rainfall_interval.tip_count==2
    for updates in ({'rainfall_mm':.7},{'rainfall_interval':None},{'applied_config_hash':None}):
        with pytest.raises(ValueError):TelemetryCreate(**{**body,**updates})
    with pytest.raises(ValueError):
        TelemetryCreate(**{**body,'rainfall_interval':{**observation,'interval_end':(stamp+timedelta(seconds=1)).isoformat()}})


def test_journal_overlap_reboot_outage_conservation_and_interval_metadata(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.sqlite3')
    store.ingest(event(schema_version=2,calibration_version='a'*64),.7,now=NOW)
    first=event(2,2,1000,schema_version=2,calibration_version='a'*64)
    store.ingest(first,.7,now=NOW+timedelta(seconds=1))
    assert store.ingest(first,.7,now=NOW+timedelta(seconds=2))['delta_tips']==0
    # Overlapping ACK intervals are reconciled from the durable high-water count.
    store.ingest(event(3,3,2000,schema_version=2,calibration_version='a'*64),.7,now=NOW+timedelta(seconds=2))
    store.ingest(event(3,1,0,boot='NEW_BOOT',start=3,schema_version=2,calibration_version='a'*64),.7,now=NOW+timedelta(seconds=3))
    store.ingest(event(5,2,61000,boot='NEW_BOOT',start=3,schema_version=2,calibration_version='a'*64),.7,now=NOW+timedelta(seconds=64))
    snapshot=store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(seconds=64))
    assert snapshot['accepted_tip_count']==5
    assert snapshot['accepted_rainfall_mm']==pytest.approx(3.5)
    assert snapshot['unallocated_recovered_mm']==pytest.approx(1.4)
    product=snapshot['current_hour_product']
    assert product['interval_start']==NOW.isoformat()
    assert product['rainfall_mm']==pytest.approx(2.1) and product['tip_count']==3
    assert product['coverage_complete'] is False and product['calibration_version']=='a'*64
    assert all('interval_end' in hour and 'coverage' in hour and 'calibration_versions' in hour for hour in snapshot['completed_hours'])
    with pytest.raises(ValueError,match='reset'):
        store.ingest(event(0,1,0,boot='ERASED'),.7,now=NOW+timedelta(seconds=65))


def test_metadata_migration_preserves_ids_nullable_rainfall_and_foreign_keys():
    from app.migrate_interval_configuration import migrate
    from app.database import Base
    from sqlalchemy.schema import CreateTable
    from sqlalchemy import MetaData
    engine=create_engine('sqlite://')
    metadata=MetaData()
    Base.metadata.tables['stations'].to_metadata(metadata)
    legacy=Telemetry.__table__.to_metadata(metadata,name='telemetry')
    for name in ('rainfall_interval','applied_config_hash','sensor_fault','local_alert_profile'):
        legacy._columns.remove(legacy.c[name])
    legacy.c.rainfall_mm.nullable=False
    with engine.begin() as connection:
        metadata.tables['stations'].create(connection)
        connection.execute(CreateTable(legacy))
        connection.exec_driver_sql("INSERT INTO stations(id,station_id,station_name,sensor_height_cm,threshold_advisory_cm,threshold_warning_cm,threshold_evacuate_cm,status,created_at) VALUES(1,'PRESERVE_V3','Kept',120,60,85,100,'active',CURRENT_TIMESTAMP)")
        connection.exec_driver_sql("INSERT INTO telemetry(id,station_id,sequence_no,water_depth_cm,rainfall_mm,sensor_quality,device_uptime_ms,recorded_at,received_at) VALUES(42,'PRESERVE_V3',1,105,1.4,'valid',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
        connection.exec_driver_sql("CREATE TABLE retained_reference(id INTEGER PRIMARY KEY,telemetry_id INTEGER REFERENCES telemetry(id))")
        connection.exec_driver_sql("INSERT INTO retained_reference VALUES(1,42)")
    assert migrate(engine)[0]
    migrate(engine,apply=True)
    assert not migrate(engine)[0]
    with engine.connect() as connection:
        row=connection.exec_driver_sql('SELECT id,rainfall_mm,sensor_fault FROM telemetry').one()
        assert tuple(row)==(42,1.4,'none')
        assert connection.exec_driver_sql('SELECT telemetry_id FROM retained_reference').scalar()==42
        assert not connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall()


def test_configuration_header_hash_is_verified_before_offline_render():
    import importlib.util
    path=Path(__file__).resolve().parents[2]/'agapay-firmware/tools/render_station_config.py'
    spec=importlib.util.spec_from_file_location('render_station_config',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    values=Installation(**installation()).model_dump(mode='json')
    body=dict(station_id='CONFIG_TEST',revision=1,installation=values,config_hash=configuration_hash('CONFIG_TEST',1,values))
    header=module.render(body)
    assert '150.0F' in header and body['config_hash'] in header and '100.0F' in header
    with pytest.raises(ValueError,match='hash mismatch'):
        module.render({**body,'installation':{**values,'rain_mm_per_tip':1.25}})


def test_calibration_change_never_reprices_old_counts_or_creates_hourly_input(tmp_path):
    store=RainGaugeStore(tmp_path/'coefficient.sqlite3')
    store.ingest(event(),.7,now=NOW)
    store.ingest(event(1,2,1000),.7,now=NOW+timedelta(seconds=1))
    store.ingest(event(2,3,2000,mm_per_tip=1.25,rainfall_increment_mm=2.5),1.25,now=NOW+timedelta(seconds=2))
    snapshot=store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(seconds=2))
    assert snapshot['accepted_tip_count']==2
    assert snapshot['session_rainfall_mm']==pytest.approx(.7+1.25)
    assert snapshot['unallocated_recovered_mm']==pytest.approx(1.25)
    assert snapshot['incomplete_hour_mm']==pytest.approx(.7)
    assert not snapshot['ml_ready']


def test_mqtt_rain_requires_current_config_hash_and_uses_station_coefficient(client,scoped,tmp_path,monkeypatch):
    import paho.mqtt.client as mqtt
    from app.config import Settings
    from app.services.mqtt_subscriber import start_mqtt_subscriber
    from station_support import device_token
    station=scoped[0]
    config,_,_=configure(client,station)
    path=tmp_path/'versioned-rain.sqlite3'
    settings=Settings(rain_gauge_enabled=True,rain_gauge_store_path=str(path),rain_gauge_calibrations={station:9.9},mqtt_username='test-backend',mqtt_password='test-only')
    monkeypatch.setattr(mqtt.Client,'connect_async',lambda *a,**k:None)
    monkeypatch.setattr(mqtt.Client,'loop_start',lambda *a,**k:None)
    acknowledgements=[]
    monkeypatch.setattr(mqtt.Client,'publish',lambda *a,**k:acknowledgements.append(a))
    sub=start_mqtt_subscriber(settings)
    token=device_token(station)
    def deliver(version):
        body=event(station=station,schema_version=2,calibration_version=version)
        sub.on_message(sub,None,SimpleNamespace(topic=f'agapay/stations/{station}/rain',retain=False,payload=json.dumps(dict(ingest_token=token,rain=body.model_dump())).encode()))
    deliver('0'*64)
    assert not path.exists() and not acknowledgements
    deliver(config['config_hash'])
    assert len(acknowledgements)==1
    view=RainGaugeStore(path).snapshot(station,'physical_rain_gauge')
    assert view['mm_per_tip']==.7 and view['calibration_version']==config['config_hash']
