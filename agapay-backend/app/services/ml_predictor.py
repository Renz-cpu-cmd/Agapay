"""Forecast boundary. No model is trained or loaded by this implementation."""
import logging
from datetime import timedelta, timezone
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Telemetry, utc_now
from app.prediction_schemas import HORIZONS, ForecastPoint, ModelOutput, PredictionInput, PredictionResponse

log = logging.getLogger(__name__)
LOOKBACK_MINUTES = 60
MIN_SAMPLES = 12
MIN_SPAN_MINUTES = 30
MAX_GAP_SECONDS = 300
MAX_AGE_SECONDS = 120
FORECAST_TTL_SECONDS = 60


class Predictor(Protocol):
    version: str | None

    def predict(self, history: PredictionInput) -> ModelOutput:
        """Predict horizons from history ending at input_last_recorded_at.

        A rainfall-dependent adapter must reject unknown rainfall intervals;
        it must not infer a period from the HTTP publishing interval.
        """
        ...


class PredictionUnavailable(Exception):
    def __init__(self, status: str, reason: str):
        if status not in ("insufficient_data", "stale_data", "invalid_data"):
            raise ValueError("Unsupported predictor availability status")
        self.status, self.reason = status, reason


class UntrainedPredictor:
    version = None

    def predict(self, history: PredictionInput) -> ModelOutput:
        raise RuntimeError("No trained model is configured")


def get_predictor() -> Predictor:
    # A future reviewed adapter replaces this dependency. Never load the empty
    # model.h5/scaler.pkl placeholders or silently substitute a trend formula.
    return UntrainedPredictor()


def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def assess_input(history: PredictionInput):
    samples = history.samples
    if not samples:
        return "insufficient_data", "No readings are available in the last hour."
    if (history.as_of - samples[-1].recorded_at).total_seconds() > MAX_AGE_SECONDS:
        return "stale_data", "The latest reading is too old for a forecast."
    if any(s.sensor_quality != "valid" for s in samples):
        return "invalid_data", "The history contains invalid sensor readings."
    span = (samples[-1].recorded_at - samples[0].recorded_at).total_seconds()
    if len(samples) < MIN_SAMPLES or span < MIN_SPAN_MINUTES * 60:
        return "insufficient_data", "More timestamped history is needed before forecasting."
    if any((b.recorded_at - a.recorded_at).total_seconds() > MAX_GAP_SECONDS for a, b in zip(samples, samples[1:])):
        return "insufficient_data", "The reading history has gaps that are too large."
    return "usable", "The history passes the provisional input checks."


def predict_station(db: Session, station_id: str, predictor: Predictor, preview_allowed: bool) -> PredictionResponse:
    now = utc_now()
    rows = list(db.scalars(select(Telemetry).where(
        Telemetry.station_id == station_id,
        Telemetry.recorded_at >= now - timedelta(minutes=LOOKBACK_MINUTES),
    ).order_by(Telemetry.recorded_at.desc(), Telemetry.id.desc()).limit(3600)))
    rows.reverse()
    # Include the last known time even when there is no recent history.
    latest = rows[-1] if rows else db.scalar(select(Telemetry).where(Telemetry.station_id == station_id).order_by(Telemetry.recorded_at.desc(), Telemetry.id.desc()).limit(1))
    data = dict(station_id=station_id, checked_at=now, source="none", model_version=predictor.version,
                sample_count=len(rows), valid_sample_count=sum(r.sensor_quality == "valid" and r.water_depth_cm is not None for r in rows),
                input_window_start=as_utc(rows[0].recorded_at) if rows else None,
                input_last_recorded_at=as_utc(latest.recorded_at) if latest else None,
                timestamp_basis="server_received", preview_allowed=preview_allowed,
                forecasts=[ForecastPoint(horizon_minutes=h) for h in HORIZONS])
    try:
        history = PredictionInput(station_id=station_id, as_of=now, timestamp_basis="server_received", samples=[dict(
            recorded_at=as_utc(r.recorded_at), water_depth_cm=r.water_depth_cm, rainfall_mm=r.rainfall_mm, sensor_quality=r.sensor_quality,
        ) for r in rows])
        input_status, reason = assess_input(history)
        if not rows and latest:
            input_status, reason = "stale_data", "No recent readings are available; the last recorded value is stale."
    except ValidationError:
        history = None
        input_status, reason = "invalid_data", "The input history failed validation."
    data["input_status"] = input_status
    if predictor.version is None:
        return PredictionResponse(**data, status="not_trained", reason="A trained forecast model is not configured. " + (reason if input_status != "usable" else ""))
    if input_status != "usable":
        return PredictionResponse(**data, status=input_status, reason=reason)
    try:
        # Validate an adapter's return value even if it returns an already-created object.
        raw = predictor.predict(history)
        output = ModelOutput.model_validate(raw.model_dump() if isinstance(raw, ModelOutput) else raw)
        generated = utc_now()
        expires = min(generated + timedelta(seconds=FORECAST_TTL_SECONDS), data["input_last_recorded_at"] + timedelta(seconds=MAX_AGE_SECONDS))
        if expires <= generated:
            return PredictionResponse(**data, status="stale_data", reason="The input expired before the forecast completed.")
        data.update(source="model", checked_at=generated, generated_at=generated, valid_until=expires,
                    forecasts=[ForecastPoint(horizon_minutes=p.horizon_minutes, water_depth_cm=p.water_depth_cm,
                        target_at=data["input_last_recorded_at"] + timedelta(minutes=p.horizon_minutes)) for p in output.forecasts])
        return PredictionResponse(**data, status="available", reason="Model forecast available for advisory use.")
    except PredictionUnavailable as error:
        return PredictionResponse(**data, status=error.status, reason=error.reason)
    except Exception:
        log.exception("Prediction adapter failed for station %s", station_id)
        # Discard every numeric value if an adapter or output validation fails.
        data.update(source="none", generated_at=None, valid_until=None, forecasts=[ForecastPoint(horizon_minutes=h) for h in HORIZONS])
        return PredictionResponse(**data, status="service_error", reason="The forecast service could not produce a valid result.")


def preview_station(station_id: str, scenario: str) -> PredictionResponse:
    now = utc_now()
    status_map = {"not_trained": "usable", "available": "usable", "service_error": "usable"}
    last = now - timedelta(minutes=10) if scenario == "stale_data" else now
    reasons = {
        "available": "Sample values for interface testing. No trained model or real sensor data was used.",
        "not_trained": "Preview: no trained model is configured.",
        "insufficient_data": "Preview: more timestamped history is needed.",
        "stale_data": "Preview: the latest reading is too old.",
        "invalid_data": "Preview: sensor readings failed quality checks.",
        "service_error": "Preview: the prediction service is unavailable.",
    }
    return PredictionResponse(station_id=station_id, status=scenario, reason=reasons[scenario], source="simulated",
        checked_at=now, generated_at=now if scenario == "available" else None,
        valid_until=now + timedelta(seconds=FORECAST_TTL_SECONDS) if scenario == "available" else None,
        input_status=status_map.get(scenario, scenario), input_window_start=last - timedelta(minutes=55),
        input_last_recorded_at=last, sample_count=3 if scenario == "insufficient_data" else 12,
        valid_sample_count=3 if scenario == "insufficient_data" else 11 if scenario == "invalid_data" else 12,
        timestamp_basis="synthetic", rainfall_interval_seconds=300, preview_allowed=True,
        forecasts=[ForecastPoint(horizon_minutes=h, water_depth_cm=v if scenario == "available" else None,
            target_at=last + timedelta(minutes=h) if scenario == "available" else None) for h, v in zip(HORIZONS, (96.0, 99.0, 102.0))])
