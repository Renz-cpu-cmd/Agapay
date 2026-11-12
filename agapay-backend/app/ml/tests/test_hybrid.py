"""Synthetic calculation fixtures; real trained artifact checked separately."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestRegressor
from app.ml.hybrid_demo.hydrology import Basin, water_balance, project, sensor_initial
from app.ml.hybrid_demo.rainfall import causal_features, partition_masks, training_rows, export_forest, predict_export
from app.ml.hybrid_demo.engine import DemoEngine


def test_rain_conversion_and_volume_balance():
    basin = Basin(contributing_area_m2=10, basin_surface_area_m2=2, runoff_coefficient=0.5)
    result = water_balance(10, 20, 30, basin)
    assert result["inflow_m3"] == pytest.approx(0.1)
    assert result["depth_cm"] == pytest.approx(15)
    assert result["outflow_m3"] == 0


def test_zero_rain_and_conservation_overflow_and_dryness():
    assert water_balance(10, 0, 30, Basin())["depth_cm"] == pytest.approx(10)
    basin = Basin(contributing_area_m2=100, basin_surface_area_m2=1, runoff_coefficient=1, maximum_depth_cm=10)
    result = water_balance(5, 10, 30, basin)
    assert result["depth_cm"] == 10 and result["overflow_m3"] == pytest.approx(0.95)
    assert 0.05+result["inflow_m3"] == pytest.approx(result["depth_cm"]/100+result["overflow_m3"])
    result = water_balance(5, 0, 30, Basin(basin_surface_area_m2=1, outflow_m3_per_hour=1))
    assert result["depth_cm"] == 0 and result["outflow_m3"] == pytest.approx(0.05)
    assert result["unmet_outflow_m3"] == pytest.approx(0.45)


def test_repeated_overflow_stays_within_capacity_despite_float_rounding():
    result=project(20,[18.3,19.3,15],Basin(maximum_depth_cm=40),datetime(2026,10,12,tzinfo=timezone.utc))
    assert all(p['depth_cm']<=40 for p in result['points'])
    assert result['points'][-1]['depth_cm']==40
    assert sum(p['overflow_m3'] for p in result['points'])>0


@pytest.mark.parametrize("depth,rain", [(-1,0),(101,0),(float('nan'),0),(0,-1),(0,float('inf'))])
def test_invalid_inputs_rejected(depth,rain):
    with pytest.raises(ValueError): water_balance(depth,rain,30,Basin())


def test_horizons_and_uniform_allocations_with_mid_hour_start():
    at = datetime(2026,10,12,1,45,tzinfo=timezone.utc)
    result = project(0,[4,8,12],Basin(),at,rainfall_origin=at.replace(minute=0))
    assert [p["horizon_minutes"] for p in result["points"]] == [30,60,90]
    assert [p["rainfall_mm"] for p in result["points"]] == pytest.approx([3,4,5])
    assert result["points"][2]["target_at"] == (at+timedelta(minutes=90)).isoformat()
    assert result["advisory_only"]


def sample(now):
    return {"source":"device","source_class":"physical_device","source_trusted":True,"depth_source_trusted":True,
            "stream":"operational","depth_fresh":True,"heartbeat_fresh":True,"sensor_quality":"valid","is_stale":False,"is_online":True,
            "current_depth_cm":20,"last_valid_depth_at":now.isoformat()}


@pytest.mark.parametrize("changes", [{"current_depth_cm":None},{"sensor_quality":"invalid"},{"source_class":"simulator"},
                                        {"is_online":False},{"last_valid_depth_at":"2020-01-01T00:00:00Z"},{"last_valid_depth_at":None}])
def test_sensor_missing_invalid_stale_rejected(changes):
    now=datetime(2026,10,12,tzinfo=timezone.utc)
    with pytest.raises(ValueError): sensor_initial({**sample(now),**changes},now)


def test_sensor_valid_and_future_rejected():
    now=datetime(2026,10,12,tzinfo=timezone.utc)
    assert sensor_initial(sample(now),now)==20
    with pytest.raises(ValueError): sensor_initial(sample(now+timedelta(seconds=1)),now)


def data_fixture():
    return pd.DataFrame({"timestamp_utc":pd.date_range('2024-12-29',periods=120,freq='h',tz='UTC'),
                         "rainfall_mm":np.arange(120,dtype=float)%10})


def test_feature_leakage_and_split_purge():
    frame=data_fixture();original=causal_features(frame);changed=frame.copy();changed.loc[61:,'rainfall_mm']=999
    pd.testing.assert_frame_equal(original.iloc[:61],causal_features(changed).iloc[:61])
    x,y,times=training_rows(frame)
    assert y.iloc[0,0]==frame.rainfall_mm.iloc[24] and x.iloc[0,0]==frame.rainfall_mm.iloc[23]
    masks=partition_masks(times)
    assert ((times[masks['validation']]+pd.Timedelta(hours=3))<pd.Timestamp('2025-01-01',tz='UTC')).all()


def test_export_matches_sklearn():
    x,y,_=training_rows(data_fixture())
    model=RandomForestRegressor(n_estimators=4,max_depth=4,random_state=42).fit(x,y)
    forest=export_forest(model)
    np.testing.assert_allclose([predict_export(forest,row.tolist()) for _,row in x.iterrows()],model.predict(x),atol=1e-10)


def engine_fixture(tmp_path):
    frame=data_fixture();frame['station_id']='TEST_ONLY';frame['dataset_source']='fixture';frame['rainfall_interval_seconds']=3600
    csv=tmp_path/'rain.csv';frame.to_csv(csv,index=False)
    x,y,_=training_rows(frame);model=RandomForestRegressor(n_estimators=2,max_depth=2,random_state=42).fit(x,y)
    (tmp_path/'forest.json').write_text(json.dumps(export_forest(model)))
    (tmp_path/'metadata.json').write_text(json.dumps({'version':'synthetic-fixture-only'}))
    return DemoEngine(tmp_path,csv)


def test_replay_reproducible_and_ml_does_not_read_future(tmp_path):
    engine=engine_fixture(tmp_path);asof='2025-01-01T00:00:00Z';now=datetime(2026,10,12,tzinfo=timezone.utc)
    kwargs=dict(initial_cm=20,basin=Basin(),as_of=asof,now=now)
    first=engine.run(mode='historical_replay',**kwargs)
    assert first==engine.run(mode='historical_replay',**kwargs)
    original=engine.run(mode='ml_backtest',**kwargs)
    engine.frame.loc[engine.frame.timestamp_utc.gt(pd.Timestamp(asof)), 'rainfall_mm']=999
    assert original['rainfall_hourly_mm']==engine.run(mode='ml_backtest',**kwargs)['rainfall_hourly_mm']
    assert first['rainfall_hourly_mm']!=engine.run(mode='historical_replay',**kwargs)['rainfall_hourly_mm']


def test_current_refuses_archived_substitute(tmp_path):
    engine=engine_fixture(tmp_path);now=datetime(2026,10,12,1,15,tzinfo=timezone.utc)
    kwargs=dict(mode='ml_current',initial_cm=20,basin=Basin(),as_of='2026-10-12T01:00:00Z',now=now)
    with pytest.raises(ValueError,match='supplied rainfall'):engine.run(**kwargs)
    history=[{'timestamp_utc':t.isoformat(),'rainfall_mm':0} for t in pd.date_range('2026-10-11T02:00Z',periods=24,freq='h')]
    result=engine.run(**kwargs,current_history=history,sensor=sample(now))
    assert result['initial_source']=='registry-verified physical source'
    assert result['initial_depth_cm']==20
    with pytest.raises(ValueError):engine.run(**{**kwargs,'as_of':'2026-10-11T01:00:00Z'},current_history=history)


def test_fastapi_service_isolated(tmp_path):
    from fastapi.testclient import TestClient
    from app.ml.hybrid_demo.server import create_app
    engine_fixture(tmp_path)
    bundle=tmp_path/'index.html';bundle.write_text('<title>fixture</title>')
    # Artifact fixture has no operational app/database imports.
    app=create_app(tmp_path,bundle,tmp_path/'rain.csv')
    with TestClient(app) as client:
        assert client.get('/').status_code==200
        response=client.post('/api/project',json={'mode':'historical_replay','initial_cm':20,'as_of':'2025-01-01T00:00:00Z'})
        assert response.status_code==200 and response.json()['advisory_only']
        assert client.post('/api/project',json={'mode':'ml_current','initial_cm':20,'as_of':'2020-01-01T00:00:00Z'}).status_code==422
