"""Synthetic evidence exercises gates only; no physical uncertainty claim."""
from copy import deepcopy
from datetime import timedelta
import hashlib,json
import pytest
from sqlalchemy import select
from app.ml.water_depth import validate_bundle,stamp
from app.ml.decision_evaluation import evaluate,drift_report,DecisionPolicy
from app.services.forecast_registry import publish_station
from app.database import SessionLocal
from app.models import Telemetry,User
from app.forecast_release import export,verify
from test_forecast_registry import candidate,setup,approve,deploy,observations
from test_predictions import STATION
from test_accounts import reset_accounts


def test_intervals_use_calibration_event_maxima_and_later_test_coverage():
    bundle=candidate();report=evaluate(bundle)
    assert report['release_ready'] and report['calibration_events']==10 and report['test_events']==16
    assert report['event_coverage']==1 and report['radius_cm']==2
    assert set(report['groups'])=={'site','season','intensity','storm_intensity','missingness'}
    assert all(row['events']==16 for row in report['paired_event_bootstrap'].values())
    assert all(row['missed_events']==0 and row['lead_minutes']['median']>=10 for row in report['decisions'].values())
    # Many origins in one event must not increase independent calibration count.
    for i,row in enumerate(bundle['decision_validation']['calibration_cases']):
        row['event_id']='same_storm';row['origin']=(stamp(row['origin'])+timedelta(minutes=i)).isoformat()
        row['available_at']=(stamp(row['origin'])+timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError,match='Too few independent'):evaluate(bundle)

@pytest.mark.parametrize('change',['provisional','missing_calibration','leakage','missing_negatives','wide_intervals','outage','ood','missed','poor_coverage','overlapping_events'])
def test_candidate_cannot_be_approved_on_pooled_gain_alone(change):
    bundle=candidate();e=bundle['decision_validation']
    if change=='provisional':e['policy']['status']='provisional'
    if change=='missing_calibration':e['calibration_cases']=[]
    if change=='leakage':e['calibration_cases'][0]['event_id']=bundle['test_cases'][0]['event_id']
    if change=='missing_negatives':bundle['test_cases']=[r for r in bundle['test_cases'] if r['targets'][0]>=60]
    if change=='wide_intervals':
        for row in e['calibration_cases']:row['targets']=[100]*3
    if change=='outage':e['unavailable_test_cases']=[dict(event_id='outage',origin=(stamp(bundle['test_cases'][-1]['origin'])+timedelta(days=1)).isoformat(),targets=[105]*3,missingness_regime='api_gap')]
    if change=='ood':e['feature_domain']=[[0,90],[-10,10]]
    if change=='missed':e['policy']['minimum_lead_minutes']=90
    if change=='poor_coverage':
        for row in bundle['test_cases']:row['targets']=[v+10 for v in row['targets']]
    if change=='overlapping_events':bundle['test_cases'][3]['origin']=bundle['test_cases'][0]['origin']
    with pytest.raises(ValueError):validate_bundle(bundle,approval=True)


def test_unavailable_and_ood_are_reported_as_missing_forecasts_not_zero_or_safe():
    bundle=candidate();bundle['decision_validation']['feature_domain']=[[0,90],[-10,10]]
    report=evaluate(bundle)
    assert not report['release_ready'] and 'unavailable_or_ood' in report['groups']['missingness']
    assert report['decisions']['100.0']['missed_events']>0
    for scores in report['groups']['missingness']['unavailable_or_ood'].values():
        assert scores['mae_cm'] is None and scores['available']==0


def test_drift_window_has_minimum_coverage_explicit_threshold_and_no_side_effects():
    base=stamp(candidate()['card']['training_cutoff'])
    rows=[dict(measured_at=(base+timedelta(minutes=i)).isoformat(),features=[250 if i<5 else 50,1]) for i in range(30)]
    assert drift_report(rows,[[0,200],[-10,10]])['status']=='rollback_required'
    assert drift_report(rows[:5],[[0,200],[-10,10]])['status']=='insufficient_data'
    with pytest.raises(ValueError):drift_report(list(reversed(rows)),[[0,200],[-10,10]])


def test_publisher_ood_masks_previous_product_and_reports_intervals(client,setup):
    _,reviewer,model,config_hash=setup;assert approve(client,reviewer,model).status_code==200;assert deploy(client,reviewer,model,config_hash).status_code==200
    observations(config_hash)
    with SessionLocal() as db:identity=publish_station(db,STATION)
    from app.services.forecast_registry import tick
    assert tick()==1
    product=client.get(f'/api/predictions/{STATION}',headers=reviewer).json()
    assert product['forecast_id']==identity and product['uncertainty']['calibration_events']==10
    assert all(p['lower_depth_cm']<=p['water_depth_cm']<=p['upper_depth_cm'] for p in product['forecasts'])
    with SessionLocal() as db:
        row=db.scalar(select(Telemetry).where(Telemetry.station_id==STATION).order_by(Telemetry.recorded_at.desc()));row.water_depth_cm=250;db.commit()
        assert publish_station(db,STATION) is None
    result=client.get(f'/api/predictions/{STATION}',headers=reviewer).json()
    assert result['status']=='invalid_data' and all(p['water_depth_cm'] is None for p in result['forecasts'])
    assert not client.get(f'/api/forecasts/{identity}',headers=reviewer).json()['current']
    from app.services import observability as obs
    from app.services.operations_health import diagnostics
    from app.config import Settings
    obs.heartbeat('forecasts')
    with SessionLocal() as db:
        assert 'FORECAST_INPUT_OUT_OF_DOMAIN' in {r['code'] for r in diagnostics(db,Settings(_env_file=None,hybrid_projection_enabled=False,operations_required=['forecasting']))['alerts']}


def test_forecast_input_gates_cannot_be_evicted_by_viewer_parameter_cache():
    from app.runtime_models import SharedReadModel
    from app.models import utc_now
    from app.config import Settings
    from app.services.read_models import cached
    at=utc_now()
    with SessionLocal() as db:
        for i in range(10):db.add(SharedReadModel(key=f'forecast-gate:TEST{i}',generation='1',payload={'status':'available'},checked_at=at,expires_at=at+timedelta(minutes=1)))
        db.commit()
    settings=Settings(_env_file=None,read_model_cache_enabled=True,read_model_max_entries=8)
    for i in range(12):assert cached(f'viewer:test{i}','same',lambda:{'value':1},ttl=2,settings=settings)['value']==1
    with SessionLocal() as db:assert db.query(SharedReadModel).filter(SharedReadModel.key.like('forecast-gate:%')).count()==10


def test_release_export_requires_registry_approval_and_trusted_manifest_and_detects_tamper(client,setup,tmp_path):
    _,reviewer,model,_=setup;destination=tmp_path/'release'
    with SessionLocal() as db:
        admin=db.scalar(select(User).where(User.email=='admin@example.com'))
        with pytest.raises(ValueError,match='approved'):export(db,model,admin.id,'e'*64,destination)
    assert approve(client,reviewer,model).status_code==200
    with SessionLocal() as db:
        admin=db.scalar(select(User).where(User.email=='admin@example.com'))
        checksum=export(db,model,admin.id,'e'*64,destination)
    assert verify(destination,checksum)['model_id']==model
    with pytest.raises(ValueError,match='trusted'):verify(destination,None)
    (destination/'bundle.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='integrity'):verify(destination,checksum)


def test_every_test_file_is_assigned_once_to_a_ci_dependency_profile():
    from scripts.run_test_profile import profiles,ROOT
    assigned=profiles();paths=[p for files in assigned.values() for p in files]
    assert len(paths)==len(set(paths))
    assert set(paths)=={p.relative_to(ROOT).as_posix() for folder in ('tests','app/ml/tests') for p in (ROOT/folder).rglob('test_*.py')}


def test_clean_snapshot_includes_cross_project_tools_and_excludes_machine_state(tmp_path):
    from scripts.validate_clean import snapshot
    root=tmp_path/'Agapay';assert snapshot(root)>0
    assert (root/'agapay-firmware/tools/render_station_config.py').is_file()
    assert (root/'agapay-backend/deploy/mosquitto/station-ingest.acl').is_file()
    assert (root/'agapay-docs/contracts/published-forecast-cases.json').is_file()
    for private in ('data','agapay-backend/.env','agapay-backend/.venv-auth','agapay-web/.env.local','agapay-web/node_modules','agapay-firmware/include/secrets.h'):
        assert not (root/private).exists(),private
