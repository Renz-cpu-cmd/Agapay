from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from app.config import Settings, get_settings
from app.database import SessionLocal
from app.hybrid_schemas import HybridProjectionRequest
from app.main import app
from app.models import Alert, Telemetry, NotificationDelivery
from app.services.hybrid_projection import dashboard_projection
from app.services.rain_gauge_service import RainGaugeStore
from test_accounts import reset_accounts, staff, headers, account
from test_rain_gauge import event

NOW = datetime(2026, 10, 13, 12, 10, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def config(tmp_path):
    from hybrid_fixtures import build
    model,dataset=build(tmp_path/'synthetic-artifact')
    return Settings(_env_file=None,hybrid_projection_enabled=True,hybrid_model_directory=str(model),
                    hybrid_dataset_path=str(dataset),
                    rain_gauge_store_path=str(tmp_path / "rain.db"), rain_gauge_enabled=True)


def request(**changes):
    return HybridProjectionRequest(controlled_basin_confirmed=True, **changes)


def test_historical_context_runs_saved_model_not_future_rain(config):
    result = dashboard_projection(request(), config, now=NOW)
    assert result["status"] == "available"
    assert "historical-context demonstration" in result["rainfall_source"]
    assert result["initial_source"].startswith("MANUAL")
    assert result["observed_rainfall_since_initialization_mm"] == 0
    assert len(result["rainfall_history"]) == 24
    assert result["rainfall_history"][-1]["timestamp_utc"] == "2025-07-01T12:00:00+00:00"
    assert all(row["valid"] and row["interval_seconds"] == 3600 for row in result["rainfall_history"])
    assert result["model_version"] == "synthetic-ci-rain-v1"
    assert [p["horizon_minutes"] for p in result["points"]] == [30,60,90]
    assert datetime.fromisoformat(result["points"][0]["target_at"]) == NOW + timedelta(minutes=30)
    # Compare the original offline engine's rainfall inference, not archived future values.
    from app.services.hybrid_projection import get_engine
    from app.ml.hybrid_demo.hydrology import Basin
    offline = get_engine(config.hybrid_model_directory,config.hybrid_dataset_path).run(
        mode="ml_backtest",initial_cm=20,basin=Basin(),as_of="2025-07-01T12:00:00+00:00",now=NOW)
    assert result["rainfall_hourly_mm"] == pytest.approx(offline["rainfall_hourly_mm"])


def test_tip_changes_dashboard_depth_once_and_keeps_ml_window(config):
    store = RainGaugeStore(Path(config.rain_gauge_store_path))
    store.ingest(event(station="STATION_001"),.7,now=NOW)
    payload = request(mode="live",initialization_at=NOW)
    before = dashboard_projection(payload,config,snapshot=store.snapshot("STATION_001","physical_rain_gauge",anchor_at=NOW,now=NOW),now=NOW)
    tip = event(1,2,1000,station="STATION_001")
    store.ingest(tip,.7,now=NOW+timedelta(seconds=1))
    snapshot=store.snapshot("STATION_001","physical_rain_gauge",anchor_at=NOW,now=NOW+timedelta(seconds=1))
    after = dashboard_projection(payload,config,snapshot=snapshot,now=NOW+timedelta(seconds=1))
    assert after["adjusted"]["depth_cm"] == pytest.approx(21.12)
    assert after["points"][0]["depth_cm"] > before["points"][0]["depth_cm"]
    assert after["rainfall_hourly_mm"] == before["rainfall_hourly_mm"]
    store.ingest(tip,.7,now=NOW+timedelta(seconds=2))
    repeated=dashboard_projection(payload,config,snapshot=snapshot,now=NOW+timedelta(seconds=2))
    assert repeated["adjusted"]["depth_cm"] == pytest.approx(21.12)
    assert repeated["observed_rainfall_since_initialization_mm"] == pytest.approx(.7)


def test_new_measured_anchor_does_not_add_rain_already_observed(config):
    store=RainGaugeStore(Path(config.rain_gauge_store_path))
    store.ingest(event(station="STATION_001"),.7,now=NOW)
    store.ingest(event(1,2,1000,station="STATION_001"),.7,now=NOW+timedelta(seconds=1))
    observed=NOW+timedelta(seconds=2)
    sensor=dict(source="device",source_class="physical_device",source_trusted=True,depth_source_trusted=True,
        stream="operational",depth_fresh=True,heartbeat_fresh=True,sensor_quality="valid",is_stale=False,is_online=True,
        current_depth_cm=23,observed_at=observed.isoformat(),last_valid_depth_at=observed.isoformat())
    result=dashboard_projection(request(mode="live",depth_source="sensor"),config,sensor=sensor,
        snapshot=store.snapshot("STATION_001","physical_rain_gauge",anchor_at=observed,now=observed),now=observed)
    assert result["adjusted"]["depth_cm"] == 23
    assert result["observed_rainfall_since_initialization_mm"] == 0
    sensor["source_class"]="simulator"
    with pytest.raises(ValueError):dashboard_projection(request(mode="live",depth_source="sensor"),config,sensor=sensor,now=observed)


def test_offline_or_wrong_source_discards_all_forecast_values(config):
    store=RainGaugeStore(Path(config.rain_gauge_store_path));store.ingest(event(station="STATION_001"),.7,now=NOW)
    stale=store.snapshot("STATION_001","physical_rain_gauge",anchor_at=NOW,now=NOW+timedelta(seconds=31))
    result=dashboard_projection(request(mode="live",initialization_at=NOW),config,snapshot=stale,now=NOW+timedelta(seconds=31))
    assert result["status"] == "unavailable" and result["points"] == []
    fresh=store.snapshot("STATION_001","physical_rain_gauge",anchor_at=NOW,now=NOW)
    fresh["data_source"]="simulated_rain_gauge"
    assert dashboard_projection(request(mode="live",initialization_at=NOW),config,snapshot=fresh,now=NOW)["points"] == []


def test_endpoint_staff_scope_production_gate_and_no_safety_writes(client,config):
    app.dependency_overrides[get_settings]=lambda:config
    endpoint="/api/hybrid-projections/STATION_001"
    payload=dict(controlled_basin_confirmed=True)
    try:
        assert client.post(endpoint,json=payload).status_code == 401
        resident=headers(client.post("/api/auth/register",json=account()))
        assert client.post(endpoint,json=payload,headers=resident).status_code == 403
        access=staff(client)
        with SessionLocal() as db:before=tuple(db.query(model).count() for model in (Telemetry,Alert,NotificationDelivery))
        response=client.post(endpoint,json=payload,headers=access)
        assert response.status_code == 200 and response.json()["station_id"] == "STATION_001"
        assert response.headers["cache-control"] == "no-store"
        assert client.post(endpoint,json={"controlled_basin_confirmed":False},headers=access).status_code == 422
        assert client.post(endpoint,json={**payload,"context_at":"2024-01-01T00:00:00Z"},headers=access).status_code == 422
        disabled=client.post(endpoint,json={**payload,"mode":"live"},headers=access)
        assert disabled.json()["status"] == "unavailable"
        with SessionLocal() as db:assert tuple(db.query(model).count() for model in (Telemetry,Alert,NotificationDelivery)) == before
        config.environment="production"
        assert client.post(endpoint,json=payload,headers=access).status_code == 403
    finally:app.dependency_overrides.pop(get_settings,None)


def test_only_24_complete_live_hours_can_replace_archived_context(config):
    origin=NOW.replace(minute=0)
    snapshot=dict(connected=True,data_source="physical_rain_gauge",last_received_at=NOW.isoformat(),
        anchor_at=NOW.isoformat(),rainfall_after_anchor_mm=0,ml_ready=True,
        completed_hours=[dict(timestamp_utc=(origin-timedelta(hours=23-i)).isoformat(),
            rainfall_mm=0,valid=True,interval_seconds=3600) for i in range(24)])
    payload=request(mode="live",initialization_at=NOW)
    result=dashboard_projection(payload,config,snapshot=snapshot,now=NOW)
    assert "genuine completed-hour" in result["rainfall_source"]
    snapshot["incomplete_hour_mm"]=1000
    assert dashboard_projection(payload,config,snapshot=snapshot,now=NOW)["rainfall_hourly_mm"] == result["rainfall_hourly_mm"]
    snapshot["completed_hours"][5]["valid"]=False
    with pytest.raises(ValueError):dashboard_projection(payload,config,snapshot=snapshot,now=NOW)
    snapshot["completed_hours"][5]["valid"]=True
    snapshot["data_source"]="simulated_rain_gauge"
    simulated=dashboard_projection(request(mode="live",rain_source="simulated_rain_gauge",initialization_at=NOW),config,snapshot=snapshot,now=NOW)
    assert "SIMULATED" in simulated["rainfall_source"] and "genuine" not in simulated["rainfall_source"]


def test_mobile_cannot_read_or_mutate_private_experiments(client,config):
    app.dependency_overrides[get_settings]=lambda:config
    try:
        access=headers(client.post('/api/auth/register',json=account()))
        assert client.get('/api/hybrid-projections/STATION_001/summary',headers=access).status_code==403
        assert client.post('/api/hybrid-projections/STATION_001',json={'controlled_basin_confirmed':True},headers=access).status_code==403
        response=client.get('/api/rain-activity/STATION_001',headers=access)
        assert response.status_code==200 and response.json()['workspace']=='observations_only'
        assert response.json()['points']==[] and 'adjusted' not in response.json()
    finally:app.dependency_overrides.pop(get_settings,None)


def test_mobile_summary_gates_stale_inputs_and_never_writes_alerts(client, config):
    app.dependency_overrides[get_settings] = lambda: config
    try:
        resident_access = headers(client.post('/api/auth/register', json=account()))
        with SessionLocal() as db:
            before = tuple(db.query(model).count() for model in (Telemetry, Alert, NotificationDelivery))
        response = client.get('/api/rain-activity/STATION_001', headers=resident_access)
        assert response.status_code == 200
        assert response.json()['status'] == 'unavailable' and response.json()['points'] == []
        # A stale depth must not make a separately fresh physical gauge say Offline.
        RainGaugeStore(Path(config.rain_gauge_store_path)).ingest(event(station='STATION_001'), .7, now=datetime.now(timezone.utc))
        response = client.get('/api/rain-activity/STATION_001', headers=resident_access)
        assert response.json()['status'] == 'unavailable'
        assert response.json()['rain_activity']['connected'] is True
        with SessionLocal() as db:
            assert tuple(db.query(model).count() for model in (Telemetry, Alert, NotificationDelivery)) == before
        config.environment = 'production'
        assert client.get('/api/rain-activity/STATION_001', headers=resident_access).status_code == 200
        config.environment = 'development'
        config.hybrid_projection_enabled = False
        assert client.get('/api/rain-activity/STATION_001', headers=resident_access).status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings, None)

