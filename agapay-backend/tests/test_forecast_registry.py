"""Synthetic software fixtures only; none is real evaluation/approval evidence."""
from copy import deepcopy
from datetime import timedelta
import json
import pytest
from sqlalchemy import select
from app.database import SessionLocal
from app.models import User,Station,Telemetry,TelemetryProvenance,StationCredential,utc_now
from app.models import StationIdentity
from app.device_config import Installation,StationConfiguration,configuration_hash
from app.account_schemas import RegisterRequest
from app.services.accounts import create_user
from app.services.forecast_registry import register,publish_station
from app.forecast_models import ForecastModel,ForecastApproval,PublishedForecast
from app.ml.water_depth import FEATURE_VERSION,validate_bundle
from test_accounts import reset_accounts,staff,account,headers,sign_in
from test_predictions import STATION
from station_support import device_token

def candidate(station=STATION,config_hash='a'*64,source='physical_field'):
    cutoff=utc_now()-timedelta(days=60)
    bundle=dict(card=dict(station_id=station,datum='Synthetic software-test datum',configuration_hash=config_hash,source_class=source,
        data_license='Synthetic fixture license; no real field data',provenance='Synthetic test cases; not a field validation claim',calibration_history='Synthetic fixture calibration history only',
        training_cutoff=cutoff.isoformat(),limitations='Software fixture only; never authorize a real deployment from this test',dataset_sha256='b'*64),
        feature_version=FEATURE_VERSION,weights=[[2,0,0]]*3,
        train_events=[dict(event_id=f'train{i}',start=(cutoff-timedelta(days=i+2)).isoformat(),target_end=(cutoff-timedelta(days=i+1)).isoformat()) for i in range(3)],
        test_cases=[dict(event_id=f'test{i//3}',origin=(cutoff+timedelta(days=20+i//3,minutes=i%3*5)).isoformat(),available_at=(cutoff+timedelta(days=20+i//3,minutes=i%3*5,seconds=1)).isoformat(),configuration_hash=config_hash,features=[[20,59,84,99][i//3%4],1],targets=[[22,61,86,101][i//3%4]]*3) for i in range(48)])
    from app.ml.decision_evaluation import DecisionPolicy
    for row in bundle['test_cases']:row['storm_intensity']='synthetic_extreme_fixture'
    bundle['decision_validation']=dict(policy=DecisionPolicy(version='synthetic-software-fixture',status='reviewed',evidence_sha256='f'*64,required_storm_intensities=['synthetic_extreme_fixture']).model_dump(),feature_domain=[[0,200],[-10,10]],
        calibration_cases=[dict(event_id=f'calibration{i}',origin=(cutoff+timedelta(days=2+i)).isoformat(),available_at=(cutoff+timedelta(days=2+i,seconds=1)).isoformat(),configuration_hash=config_hash,features=[40,1],targets=[42]*3) for i in range(10)],unavailable_test_cases=[])
    return bundle

@pytest.fixture
def setup(client):
    uploader=staff(client)
    with SessionLocal() as db:
        creator=db.scalar(select(User).where(User.email=='admin@example.com'))
        create_user(db,RegisterRequest(**account('independent@example.com')),'admin')
        creator_id=creator.id
        db.query(Telemetry).filter(Telemetry.station_id==STATION).delete()
        if not db.scalar(select(Station).where(Station.station_id==STATION)):db.add(Station(station_id=STATION,station_name='Synthetic registry station'))
        db.commit()
    reviewer=headers(sign_in(client,'independent@example.com','web'))
    device_token(STATION)
    values=Installation(datum='Synthetic software-test datum',installation_height_cm=150,sensor_min_cm=20,sensor_max_cm=450,uncertainty_cm=2,range_margin_cm=5,advisory_cm=60,warning_cm=85,critical_cm=100,rain_mm_per_tip=.7).model_dump()
    config_hash=configuration_hash(STATION,1,values)
    with SessionLocal() as db:
        db.add(StationConfiguration(station_id=STATION,revision=1,config_hash=config_hash,installation=values,validation_status='field_reviewed',evidence='Synthetic fixture; not physical calibration evidence',reason='Software test only',reviewer_id=creator_id,effective_at=utc_now()-timedelta(days=1)))
        db.commit();model=register(db,db.get(User,creator_id),candidate(config_hash=config_hash))
    return uploader,reviewer,model,config_hash

def approve(client,access,identity,version=0,decision='approved'):
    return client.post(f'/api/forecast-registry/{identity}/review',headers=access,json=dict(expected_version=version,decision=decision,reason='Synthetic independent software review only',evidence_sha256='c'*64))

def deploy(client,access,identity,config_hash,version=0):
    return client.post(f'/api/forecast-deployments/{STATION}',headers=access,json=dict(expected_version=version,model_id=identity,configuration_hash=config_hash,reason='Synthetic reviewed binding for software tests'))

def observations(config_hash):
    now=utc_now()
    with SessionLocal() as db:
        credential=db.scalar(select(StationCredential).where(StationCredential.station_id==STATION))
        for i in range(12):
            at=now-timedelta(minutes=(11-i)*5,seconds=1)
            row=Telemetry(station_id=STATION,sequence_no=i+1,water_depth_cm=40+i,sensor_quality='valid',device_uptime_ms=i*300000,
                rainfall_mm=0,recorded_at=at,measured_at=at,received_at=at,schema_version=2,config_version=1,source_id='TEST_'+STATION,eligible_for_current=True,disposition='current',applied_config_hash=config_hash)
            db.add(row);db.flush();db.add(TelemetryProvenance(telemetry_id=row.id,credential_id=credential.id,ingress_transport='mqtt',ingress_identity='TEST_'+STATION,source_class='physical_device',stream='operational',registry_version=1))
        db.commit()

def test_default_and_production_return_clear_unavailable_without_experiments(client):
    from sqlalchemy import event
    from app.database import engine
    access=headers(client.post('/api/auth/register',json=account()))
    raw_reads=[]
    def observe(connection,cursor,statement,parameters,context,many):
        if 'from telemetry' in statement.lower():raw_reads.append(statement)
    event.listen(engine,'before_cursor_execute',observe)
    try:data=client.get('/api/predictions/STATION_001',headers=access).json()
    finally:event.remove(engine,'before_cursor_execute',observe)
    assert not raw_reads
    assert data['status']=='not_trained' and data['forecast_id'] is None and all(r['water_depth_cm'] is None for r in data['forecasts'])
    assert client.get('/api/forecast-registry',headers=access).status_code==403
    assert client.get('/api/rain-activity/STATION_001',headers=access).json()['points']==[]

def test_independent_approval_baseline_gates_versions_and_audit(client,setup):
    uploader,reviewer,identity,config_hash=setup
    assert approve(client,uploader,identity).status_code==403
    assert deploy(client,reviewer,identity,config_hash).status_code==422
    assert approve(client,reviewer,identity).status_code==200
    assert approve(client,reviewer,identity).status_code==409
    assert deploy(client,reviewer,identity,'d'*64).status_code==422
    assert deploy(client,reviewer,identity,config_hash).status_code==200
    assert deploy(client,reviewer,identity,config_hash).status_code==409
    with SessionLocal() as db:
        from app.identity_models import MutationAudit
        actions=set(db.scalars(select(MutationAudit.action)))
        assert {'forecast_registered','forecast_reviewed','forecast_binding_changed'}<=actions

def test_one_published_id_matches_staff_resident_and_historical_values_and_revocation(client,setup):
    _,reviewer,identity,config_hash=setup
    assert approve(client,reviewer,identity).status_code==200
    assert deploy(client,reviewer,identity,config_hash).status_code==200
    observations(config_hash)
    resident=headers(client.post('/api/auth/register',json=account()))
    with SessionLocal() as db:
        forecast_id=publish_station(db,STATION)
        assert forecast_id and publish_station(db,STATION)==forecast_id
    web=client.get(f'/api/predictions/{STATION}',headers=reviewer).json()
    mobile=client.get(f'/api/predictions/{STATION}',headers=resident).json()
    assert web['forecast_id']==mobile['forecast_id']==forecast_id
    for key in ('forecasts','model_version','generated_at','valid_until','configuration_hash','deployment_version','reference_datum','measurement_source','data_cutoff'):assert web[key]==mobile[key],key
    canonical=client.get(f'/api/forecasts/{forecast_id}',headers=resident).json()
    assert canonical['current'] and canonical['product']['forecasts']==web['forecasts']
    # Local experiment controls are absent from every operational read request.
    assert client.post('/api/hybrid-projections/'+STATION,headers=resident,json={'controlled_basin_confirmed':True}).status_code==403
    assert approve(client,reviewer,identity,1,'revoked').status_code==200
    assert client.get(f'/api/predictions/{STATION}',headers=resident).json()['status']=='unavailable'
    assert not client.get(f'/api/forecasts/{forecast_id}',headers=resident).json()['current']
    with SessionLocal() as db:assert db.query(PublishedForecast).count()==1

def test_concurrent_publishers_share_one_id_expiry_and_configuration_changes_fail_closed(client,setup,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app.services import forecast_registry as registry
    _,reviewer,identity,config_hash=setup
    assert approve(client,reviewer,identity).status_code==200
    assert deploy(client,reviewer,identity,config_hash).status_code==200
    observations(config_hash)
    def publish(_):
        with SessionLocal() as db:return publish_station(db,STATION)
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(publish,range(2)))
    assert ids[0] and ids[0]==ids[1]
    original_now=utc_now()
    monkeypatch.setattr(registry,'utc_now',lambda:original_now+timedelta(minutes=3))
    result=client.get(f'/api/predictions/{STATION}',headers=reviewer).json()
    assert result['status']=='stale_data' and all(point['water_depth_cm'] is None for point in result['forecasts'])
    assert not client.get(f'/api/forecasts/{ids[0]}',headers=reviewer).json()['current']
    monkeypatch.setattr(registry,'utc_now',utc_now)
    with SessionLocal() as db:
        source=db.get(StationIdentity,STATION);source.version+=1;db.commit()
    result=client.get(f'/api/predictions/{STATION}',headers=reviewer).json()
    assert result['status']=='unavailable' and 'identity changed' in result['reason']
    with SessionLocal() as db:
        configuration=db.scalar(select(StationConfiguration).where(StationConfiguration.station_id==STATION));configuration.validation_status='prototype';db.commit()
    assert client.get(f'/api/predictions/{STATION}',headers=reviewer).json()['status']=='unavailable'

def test_forecast_readiness_distinguishes_missing_configuration_and_worker(client,setup):
    from app.config import Settings
    from app.services.operations_health import diagnostics
    _,reviewer,identity,config_hash=setup
    settings=Settings(operations_required=['forecasting'],hybrid_projection_enabled=False,mqtt_enabled=False)
    with SessionLocal() as db:assert 'FORECAST_NOT_CONFIGURED' in {r['code'] for r in diagnostics(db,settings)['alerts']}
    assert approve(client,reviewer,identity).status_code==200
    assert deploy(client,reviewer,identity,config_hash).status_code==200
    with SessionLocal() as db:assert 'FORECASTS_WORKER_STALE' in {r['code'] for r in diagnostics(db,settings)['alerts']}

def test_viewer_reads_project_only_model_card_not_training_or_heldout_cases(client,setup):
    from sqlalchemy import event
    from app.database import engine
    _,reviewer,identity,config_hash=setup
    assert approve(client,reviewer,identity).status_code==200
    assert deploy(client,reviewer,identity,config_hash).status_code==200
    observations(config_hash)
    with SessionLocal() as db:assert publish_station(db,STATION)
    queries=[]
    def observe(connection,cursor,statement,parameters,context,many):
        if statement.lstrip().upper().startswith('SELECT') and 'forecast_models' in statement:queries.append(statement.lower())
    event.listen(engine,'before_cursor_execute',observe)
    try:assert client.get(f'/api/predictions/{STATION}',headers=reviewer).json()['status']=='available'
    finally:event.remove(engine,'before_cursor_execute',observe)
    # Only model-card paths are extracted, never the whole bundle (json_extract on SQLite, -> on PostgreSQL).
    assert queries and all('json_extract' in query or 'forecast_models.bundle ->' in query for query in queries)

@pytest.mark.parametrize('change',['synthetic','baseline','overlap','cutoff','calibration','nonfinite'])
def test_bad_evidence_cannot_pass_approval_gate(change):
    bundle=candidate()
    if change=='synthetic':bundle['card']['source_class']='synthetic_fixture'
    if change=='baseline':bundle['weights']=[[0,0,0]]*3
    if change=='overlap':bundle['train_events'][0]['event_id']='test0'
    if change=='cutoff':bundle['test_cases'][0]['origin']=bundle['card']['training_cutoff']
    if change=='calibration':bundle['test_cases'][0]['configuration_hash']='e'*64
    if change=='nonfinite':bundle['weights'][0][0]=float('nan')
    with pytest.raises(ValueError):validate_bundle(bundle,approval=True)
