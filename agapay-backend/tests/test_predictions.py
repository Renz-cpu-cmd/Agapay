from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.main import app
from app.models import Station, Telemetry, utc_now
from app.prediction_schemas import ModelOutput, PredictionInput, PredictionResponse
from app.services import ml_predictor
from app.services.ml_predictor import get_predictor
from test_accounts import account, headers, reset_accounts

STATION = "PREDICT_TEST"


@pytest.fixture
def access(client):
    with SessionLocal() as db:
        db.query(Telemetry).filter(Telemetry.station_id == STATION).delete()
        if not db.scalar(select(Station).where(Station.station_id == STATION)):
            db.add(Station(station_id=STATION, station_name="Forecast contract test"))
        db.commit()
    yield headers(client.post("/api/auth/register", json=account()))
    app.dependency_overrides.clear()


def history(now, count=12, step_minutes=5, age_seconds=1, invalid=False, future=False):
    with SessionLocal() as db:
        for i in range(count):
            timestamp = now - timedelta(minutes=(count - i - 1) * step_minutes, seconds=age_seconds)
            if future and i == count - 1:
                timestamp = now + timedelta(minutes=1)
            db.add(Telemetry(station_id=STATION, sequence_no=i + 1,
                water_depth_cm=None if invalid and i == count - 1 else 40 + i,
                rainfall_mm=.5, sensor_quality="invalid" if invalid and i == count - 1 else "valid",
                device_uptime_ms=i * 300000, recorded_at=timestamp))
        db.commit()


class Adapter:
    version = "test-adapter-only"
    def __init__(self):
        self.input = None
    def predict(self, window):
        self.input = window
        return {"forecasts": [{"horizon_minutes": h, "water_depth_cm": 0} for h in (30, 60, 90)]}


def use_adapter(adapter):
    app.dependency_overrides[get_predictor] = lambda: adapter


def test_default_auth_contract_and_no_sample_fallback(client, access):
    url = f"/api/predictions/{STATION}"
    assert client.get(url).status_code == 401
    response = client.get(url, headers=access)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["status"] == "not_trained" and data["source"] == "none"
    assert data["model_version"] is None and data["generated_at"] is None
    assert data["input_status"] == "insufficient_data"
    assert data["checked_at"].endswith("Z")
    assert [p["water_depth_cm"] for p in data["forecasts"]] == [None] * 3
    assert "confidence" not in data and "accuracy" not in data
    assert client.get("/api/predictions/UNKNOWN", headers=access).status_code == 404
    assert client.get(url + "?mode=unknown", headers=access).status_code == 422
    assert client.get(url + "?mode=preview&scenario=unknown", headers=access).status_code == 422
    assert client.post(url, headers=access, json={}).status_code == 405


@pytest.mark.parametrize("scenario", ["available", "not_trained", "insufficient_data", "stale_data", "invalid_data", "service_error"])
def test_preview_states_are_explicit_and_do_not_modify_actual_state(client, access, scenario):
    response = client.get(f"/api/predictions/{STATION}?mode=preview&scenario={scenario}", headers=access)
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "simulated" and data["timestamp_basis"] == "synthetic"
    assert data["status"] == scenario and data["model_version"] is None
    assert [p["water_depth_cm"] for p in data["forecasts"]] == ([96, 99, 102] if scenario == "available" else [None] * 3)
    assert client.get(f"/api/predictions/{STATION}", headers=access).json()["status"] == "not_trained"
    with SessionLocal() as db:
        assert db.scalar(select(Telemetry).where(Telemetry.station_id == STATION)) is None
        assert db.scalar(select(Station).where(Station.station_id == STATION)).status == "active"


@pytest.mark.parametrize("settings", [Settings(environment="production"), Settings(prediction_preview_enabled=False)])
def test_preview_disabled_by_environment_or_config(client, access, settings):
    app.dependency_overrides[get_settings] = lambda: settings
    assert client.get(f"/api/predictions/{STATION}", headers=access).json()["preview_allowed"] is False
    assert client.get(f"/api/predictions/{STATION}?mode=preview", headers=access).status_code == 403


def test_adapter_input_and_valid_zero_forecasts_have_correct_targets(client, access):
    now = utc_now()
    history(now)
    adapter = Adapter(); use_adapter(adapter)
    response = client.get(f"/api/predictions/{STATION}", headers=access)
    data = PredictionResponse.model_validate(response.json())
    assert data.status == "available" and data.source == "model"
    assert data.model_version == adapter.version and data.generated_at is not None
    assert data.valid_until > data.checked_at
    assert [p.water_depth_cm for p in data.forecasts] == [0, 0, 0]
    assert all(p.target_at == data.input_last_recorded_at + timedelta(minutes=p.horizon_minutes) for p in data.forecasts)
    assert isinstance(adapter.input, PredictionInput)
    assert adapter.input.samples[0].recorded_at < adapter.input.samples[-1].recorded_at
    assert adapter.input.samples[-1].rainfall_interval_seconds is None
    assert data.timestamp_basis == "server_received"


@pytest.mark.parametrize("options,status", [
    ({"count": 3}, "insufficient_data"), ({"age_seconds": 180}, "stale_data"),
    ({"invalid": True}, "invalid_data"), ({"future": True}, "invalid_data"),
    ({"step_minutes": 6}, "insufficient_data"), ({"step_minutes": .1}, "insufficient_data"),
])
def test_unusable_history_never_calls_model(client, access, options, status):
    history(utc_now(), **options)
    adapter = Adapter(); use_adapter(adapter)
    data = client.get(f"/api/predictions/{STATION}", headers=access).json()
    assert data["status"] == status and adapter.input is None
    assert all(p["water_depth_cm"] is None for p in data["forecasts"])


def test_expired_input_during_inference_is_not_returned_as_available(client, access, monkeypatch):
    now = utc_now(); history(now)
    moments = iter([now, now + timedelta(minutes=3)])
    monkeypatch.setattr(ml_predictor, "utc_now", lambda: next(moments))
    use_adapter(Adapter())
    data = client.get(f"/api/predictions/{STATION}", headers=access).json()
    assert data["status"] == "stale_data"
    assert all(p["water_depth_cm"] is None for p in data["forecasts"])


@pytest.mark.parametrize("bad_output", [{"forecasts": []}, {"forecasts": [{"horizon_minutes": 30, "water_depth_cm": float("nan")}]}, RuntimeError("private model failure")])
def test_adapter_errors_and_invalid_outputs_fail_closed(client, access, bad_output):
    history(utc_now())
    class Broken(Adapter):
        def predict(self, window):
            if isinstance(bad_output, Exception): raise bad_output
            return bad_output
    use_adapter(Broken())
    response = client.get(f"/api/predictions/{STATION}", headers=access)
    assert response.status_code == 200 and response.json()["status"] == "service_error"
    assert "private model failure" not in response.text
    assert all(p["water_depth_cm"] is None for p in response.json()["forecasts"])


def test_model_schema_refuses_claims_and_incomplete_horizons():
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"forecasts": [], "accuracy": .99})
    with pytest.raises(ValidationError):
        PredictionInput.model_validate({"station_id": STATION, "as_of": "2026-09-04T00:00:00", "timestamp_basis": "synthetic", "samples": []})
