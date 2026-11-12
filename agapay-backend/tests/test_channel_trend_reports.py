from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.config import Settings
from app.database import SessionLocal
from app.models import Alert, Station, StationCredential, StationIdentity, Telemetry, TelemetryProvenance
from app.services.monitoring_service import monitoring_snapshot
from app.services.history_report import build_history_report
from app.services.rise_rate import estimate_rise
from test_accounts import account, headers, reset_accounts, staff
from station_support import device_token

NOW = datetime(2026,10,21,12,0,tzinfo=timezone.utc)


def samples(step, rate=1.2, span=120):
    start=NOW-timedelta(seconds=span)
    return [SimpleNamespace(id=index+1, measured_at=start+timedelta(seconds=seconds),
        recorded_at=start+timedelta(seconds=seconds), water_depth_cm=10+rate*seconds/60,
        sensor_quality="valid", config_version=1, boot_id="BOOT", source_id="DEVICE")
        for index,seconds in enumerate(range(0,span+1,step))]


@pytest.mark.parametrize("step", [1,2,5,10,15])
def test_equivalent_physical_rates_are_frequency_independent(step):
    result=estimate_rise(samples(step),NOW)
    assert result["trend"]=="rising"
    assert result["rise_rate_cm_per_minute"]==pytest.approx(1.2)
    assert result["rise_rate_lower"]==pytest.approx(1.2)
    assert result["trend_coverage"] >= .8


@pytest.mark.parametrize("rate,tier", [(0,"stable"),(.5,"rising"),(4,"rising_rapidly"),(-1,"falling")])
def test_rates_and_boundary_units_are_cm_per_minute(rate,tier):
    result=estimate_rise(samples(5,rate),NOW)
    assert result["trend"]==tier
    assert result["rise_rate_cm_per_minute"]==pytest.approx(rate)


def test_invalid_gaps_reboots_and_short_windows_never_manufacture_stability():
    short=samples(1,0,span=2)
    assert estimate_rise(short,NOW)["trend"]=="unknown"
    invalid=samples(10,0)
    invalid[-1].sensor_quality="invalid"
    assert estimate_rise(invalid,NOW)["rise_rate_cm_per_minute"] is None
    gap=samples(10,0)
    gap=gap[:3]+gap[-2:]
    assert estimate_rise(gap,NOW)["trend"]=="unknown"
    reboot=samples(10,0)
    reboot[-1].boot_id="NEW_BOOT"
    assert estimate_rise(reboot,NOW)["trend"]=="unknown"
    assert estimate_rise(samples(10,0),NOW+timedelta(seconds=31))["trend"]=="unknown"
    assert estimate_rise(samples(10,0),NOW,review_ids={13})["trend"]=="unknown"


def test_isolated_depth_outlier_has_robust_rate_and_uncertainty():
    rows=samples(5,1.2)
    rows[10].water_depth_cm += 30
    result=estimate_rise(rows,NOW)
    assert result["rise_rate_cm_per_minute"]==pytest.approx(1.2)
    assert result["trend_method"].endswith("not a calibrated confidence interval")


@pytest.fixture
def scoped(client):
    ids=['HIST_'+uuid4().hex[:9].upper() for _ in range(2)]
    with SessionLocal() as db:
        for station_id in ids:
            db.add(Station(station_id=station_id,station_name='Synthetic '+station_id))
        db.commit()
    for station_id in ids:
        device_token(station_id)
    return ids


def insert(db,station_id,seq,at,depth,*,valid=True,trusted=True,late=False):
    identity=db.get(StationIdentity,station_id)
    credential=db.scalar(select(StationCredential).where(StationCredential.station_id==station_id))
    row=Telemetry(station_id=station_id,sequence_no=seq,config_version=1,schema_version=2,
        boot_id='REPORT_BOOT',boot_sequence=1,source_id=identity.device_id,
        measured_at=at,recorded_at=at,received_at=at,water_depth_cm=depth if valid else None,
        sensor_quality='valid' if valid else 'invalid',device_uptime_ms=seq*1000,rainfall_mm=0,
        firmware_version='1.0.0-test',eligible_for_current=not late,disposition='current' if not late else 'late_measurement')
    db.add(row);db.flush()
    if trusted:
        db.add(TelemetryProvenance(telemetry_id=row.id,credential_id=credential.id,
            ingress_transport='http',ingress_identity=identity.device_id,source_class='physical_device',stream='operational',registry_version=1))
    return row


def test_report_aligns_explicit_time_buckets_preserves_gaps_and_exact_extrema(scoped):
    with SessionLocal() as db:
        start=NOW-timedelta(minutes=4)
        insert(db,scoped[0],1,start,0)
        insert(db,scoped[0],2,start+timedelta(seconds=10),20,late=True)
        insert(db,scoped[0],3,start+timedelta(minutes=2),999,valid=False)
        insert(db,scoped[0],4,start+timedelta(minutes=3),500,trusted=False)
        insert(db,scoped[1],1,start+timedelta(minutes=1,seconds=15),8)
        db.commit()
        result=build_history_report(db,start_at=start,end_at=NOW,station_ids=scoped,bucket_seconds=60,now=NOW)
        a,b=sorted(result['stations'],key=lambda item:scoped.index(item['station_id']))
        assert [bucket['mean_depth_cm'] for bucket in a['buckets']]==[10,None,None,None]
        assert [bucket['mean_depth_cm'] for bucket in b['buckets']]==[None,8,None,None]
        assert a['minimum_depth_cm']==0 and a['maximum_depth_cm']==20 and a['mean_depth_cm']==10
        assert a['valid_count']==2 and a['sample_count']==4 and a['covered_buckets']==1
        assert a['invalid_count']==1 and a['unverified_count']==1
        assert a['source_details']
        assert result['scope']['timezone']=='Asia/Manila'
        assert result['scope']['start_local'].endswith('+08:00')


def test_event_report_uses_persisted_episode_boundaries_including_resolution(scoped):
    with SessionLocal() as db:
        start=NOW-timedelta(minutes=3)
        trigger=insert(db,scoped[0],1,start,101)
        end=insert(db,scoped[0],2,start+timedelta(minutes=1),0)
        insert(db,scoped[0],3,NOW,119)
        episode=Alert(station_id=scoped[0],status='RESOLVED',current_severity='NORMAL',highest_severity='EVACUATE',
            trigger_telemetry_id=trigger.id,latest_telemetry_id=end.id,trigger_sequence_no=1,latest_sequence_no=2,
            trigger_depth_cm=101,latest_depth_cm=0,triggered_at=start,last_transition_at=end.measured_at,resolved_at=end.measured_at)
        db.add(episode);db.commit()
        result=build_history_report(db,event_id=episode.id,now=NOW)
        assert result['scope']['start_at']==start and result['scope']['end_at']==end.measured_at.replace(tzinfo=timezone.utc)
        assert result['stations'][0]['maximum_depth_cm']==101
        assert result['stations'][0]['sample_count']==2


def test_report_auth_and_query_budgets(client,scoped,monkeypatch):
    access=staff(client)
    path='/api/monitoring/history'
    args={'start_at':(NOW-timedelta(hours=1)).isoformat(),'end_at':NOW.isoformat(),'station_id':scoped[0]}
    assert client.get(path,params=args).status_code==401
    resident=headers(client.post('/api/auth/register',json=account('hist-resident@example.com')))
    assert client.get(path,params=args,headers=resident).status_code==403
    response=client.get(path,params=args,headers=access)
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='no-store'
    # Real query strings arrive as strings: every UI option must validate after
    # integer parsing, while the report service still rejects unsupported sizes.
    for bucket in (30,60,300,900,3600):
        selected=client.get(path,params={**args,'bucket_seconds':str(bucket)},headers=access)
        assert selected.status_code==200,selected.text
        assert selected.json()['scope']['bucket_seconds']==bucket
    for bucket in ('31','0','3601','60.5','not-a-number'):
        assert client.get(path,params={**args,'bucket_seconds':bucket},headers=access).status_code==422
    assert client.get(path,params={**args,'start_at':(NOW-timedelta(days=8)).isoformat()},headers=access).status_code==422
    assert client.get(path,params={**args,'start_at':'2026-10-21T10:00:00'},headers=access).status_code==422
    from app.services import history_report
    monkeypatch.setattr(history_report,'MAX_ROWS',1)
    with SessionLocal() as db:
        insert(db,scoped[0],1,NOW-timedelta(seconds=10),0)
        insert(db,scoped[0],2,NOW-timedelta(seconds=5),1)
        db.commit()
    response=client.get(path,params=args,headers=access)
    assert response.status_code==422 and 'No partial report' in response.text


def test_rain_health_is_independent_zero_is_valid_and_administration_preserved(scoped,tmp_path):
    from app.services.rain_gauge_service import RainGaugeStore
    from test_rain_gauge import event
    path=tmp_path/'independent-rain.sqlite3'
    settings=Settings(rain_gauge_enabled=True,rain_gauge_store_path=str(path),rain_gauge_calibrations={scoped[0]:.7},mqtt_enabled=False)
    with SessionLocal() as db:
        insert(db,scoped[0],1,NOW,50)
        db.commit()
        row=db.get(StationIdentity,scoped[0])
        credential=db.scalar(select(StationCredential).where(StationCredential.station_id==scoped[0]))
        provenance=dict(credential_id=credential.id,ingress_transport='mqtt',ingress_identity=row.device_id,
            source_class='physical_device',stream='operational',registry_version=1)
        missing=next(s for s in monitoring_snapshot(db,stale_after_seconds=30,history_limit=2,now=NOW,settings=settings,station_ids=[scoped[0]]).stations if s.station_id==scoped[0])
        assert missing.channel_health.water_sensor.state=='healthy'
        assert missing.channel_health.rain_counter.state=='no_data'
        assert not path.exists()  # Monitoring reads never create a rain journal.
        store=RainGaugeStore(path)
        store.ingest(event(station=scoped[0]),.7,now=NOW,provenance=provenance)
        current=next(s for s in monitoring_snapshot(db,stale_after_seconds=30,history_limit=2,now=NOW,settings=settings,station_ids=[scoped[0]]).stations if s.station_id==scoped[0])
        assert current.channel_health.rain_counter.state=='healthy'
        assert current.channel_health.rain_counter.value==0
        assert current.channel_health.calibration.physical_validation=='pending'
        db.scalar(select(Station).where(Station.station_id==scoped[0])).status='maintenance'
        insert(db,scoped[0],2,NOW+timedelta(seconds=40),51)
        db.commit()
        later=next(s for s in monitoring_snapshot(db,stale_after_seconds=30,history_limit=2,now=NOW+timedelta(seconds=40),settings=settings,station_ids=[scoped[0]]).stations if s.station_id==scoped[0])
        assert later.channel_health.water_sensor.state=='healthy'
        assert later.channel_health.rain_counter.state=='stale'
        assert later.administrative_status=='maintenance'


def test_http_heartbeat_cannot_prove_broker_ingestion_and_disconnect_is_observed(scoped):
    from app.services.broker_health import observe
    settings=Settings(mqtt_enabled=True,rain_gauge_enabled=False)
    with SessionLocal() as db:
        insert(db,scoped[0],1,NOW,50)
        db.commit()
        observe('connected')
        view=next(s for s in monitoring_snapshot(db,stale_after_seconds=30,history_limit=2,now=NOW,settings=settings,station_ids=[scoped[0]]).stations if s.station_id==scoped[0])
        assert view.channel_health.water_sensor.state=='healthy'
        assert view.channel_health.broker_ingestion.state=='no_data'
        assert view.channel_health.broker_ingestion.connection_state=='connected'
        observe('disconnected')
        view=next(s for s in monitoring_snapshot(db,stale_after_seconds=30,history_limit=2,now=NOW,settings=settings,station_ids=[scoped[0]]).stations if s.station_id==scoped[0])
        assert view.channel_health.broker_ingestion.state=='disconnected'
        assert view.channel_health.water_sensor.state=='healthy'
    observe('unknown')


def test_history_index_migration_is_additive_and_idempotent():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database import Base
    from app.migrate_history_index import INDEX,migrate
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    INDEX.drop(engine)
    with Session(engine) as db:
        db.add(Station(station_id='INDEX_PRESERVE',station_name='Preserved'))
        db.commit()
    assert migrate(engine) is True
    migrate(engine,apply=True)
    assert migrate(engine) is False
    with Session(engine) as db:
        assert db.scalar(select(Station.station_name))=='Preserved'
