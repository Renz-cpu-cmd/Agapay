"""Dashboard adapter for the existing rainfall model and controlled-basin physics.

Reads archived context, telemetry and the separate rain journal. Never writes
operational telemetry, alert state or notification deliveries.
"""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

from app.hybrid_schemas import HybridProjectionRequest
from app.ml.hybrid_demo.hydrology import Basin, NOTICE, project, sensor_initial, water_balance


def artifact_version(model_directory,dataset):
    paths=[Path(model_directory)/"metadata.json",Path(model_directory)/"forest.json",Path(dataset)]
    return tuple((str(p.resolve()),p.stat().st_size,p.stat().st_mtime_ns) for p in paths)


def get_engine(model_directory: str,dataset: str):
    return _get_engine(model_directory,dataset,artifact_version(model_directory,dataset))


@lru_cache(maxsize=2)
def _get_engine(model_directory: str, dataset: str, version):
    # Load the JSON estimator export, never a pickle supplied by an HTTP client.
    from app.ml.hybrid_demo.engine import DemoEngine
    directory, source = Path(model_directory), Path(dataset)
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    for path, expected in ((source, metadata["dataset"]["sha256"]),
                           (directory / "forest.json", metadata["files"]["forest.json"]["sha256"])):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Hybrid model or rainfall dataset does not match its provenance")
    return DemoEngine(directory, source)


def rainfall_forcing(model_directory: str,dataset: str,hours: tuple):
    version=artifact_version(model_directory,dataset)
    from app.config import get_settings
    settings=get_settings()
    if not settings.read_model_cache_enabled:return _rainfall_forcing(model_directory,dataset,hours,version)
    from app.services.read_models import cached,digest
    key="forcing:"+digest([version,hours])[:48]
    return tuple(cached(key,digest(version),lambda:{"values":list(_rainfall_forcing(model_directory,dataset,hours,version))},ttl=3600,settings=settings,kind="hybrid")["values"])


@lru_cache(maxsize=128)
def _rainfall_forcing(model_directory: str, dataset: str, hours: tuple,version):
    import pandas as pd
    from app.ml.hybrid_demo.rainfall import causal_features, predict_export
    engine = get_engine(model_directory, dataset)
    frame = pd.DataFrame(hours, columns=["timestamp_utc", "rainfall_mm"])
    return tuple(predict_export(engine.forest, causal_features(frame).iloc[-1].tolist()))


def unavailable(reason, now):
    return {"status": "unavailable", "reason": reason, "notice": NOTICE,
            "advisory_only": True, "checked_at": now.isoformat(), "points": []}


def dashboard_projection(payload: HybridProjectionRequest, settings, *, snapshot=None, sensor=None, now=None):
    now = now or datetime.now(timezone.utc)
    engine = get_engine(settings.hybrid_model_directory, settings.hybrid_dataset_path)
    basin = Basin(**payload.basin.model_dump())
    initial_at = payload.initialization_at or now
    if not 0 <= (now - initial_at).total_seconds() <= 86400:
        raise ValueError("Initialization must be within the preceding 24 hours; start a new demonstration")
    initial_depth, initial_source = payload.manual_depth_cm, "MANUAL — configured demonstration depth"
    if payload.depth_source == "sensor":
        initial_depth = sensor_initial(sensor or {}, now, settings.telemetry_stale_after_seconds)
        initial_at = datetime.fromisoformat(sensor["last_valid_depth_at"].replace("Z", "+00:00"))
        initial_source = "MEASURED — registry-verified physical source (not hardware attestation)"
    observed_rain = 0.0
    if payload.mode == "live":
        if not snapshot or not snapshot.get("connected") or snapshot.get("data_source") != payload.rain_source:
            return unavailable("Rain-gauge heartbeat is missing or stale. Start the live feed or select historical ML demonstration.", now)
        age = (now - datetime.fromisoformat(snapshot["last_received_at"])).total_seconds()
        if not 0 <= age <= 30 or snapshot.get("anchor_at") != initial_at.isoformat():
            return unavailable("Live rain must be fresh and aligned after the depth initialization.", now)
        if snapshot.get("rainfall_after_anchor_mm") is None:return unavailable("Initialization rain interval is outside retained coverage.",now)
        observed_rain = snapshot["rainfall_after_anchor_mm"]
    genuine = payload.mode == "live" and snapshot.get("ml_ready", False)
    if genuine:
        hours = snapshot["completed_hours"]
        stamps = [datetime.fromisoformat(h["timestamp_utc"]) for h in hours]
        if len(hours) != 24 or any(not h["valid"] or h["interval_seconds"] != 3600 or not isinstance(h["rainfall_mm"], (int,float)) or not math.isfinite(h["rainfall_mm"]) or h["rainfall_mm"] < 0 for h in hours) or any(
                (b-a).total_seconds() != 3600 for a,b in zip(stamps,stamps[1:])) or not 0 <= (now-stamps[-1]).total_seconds() < 3600:
            raise ValueError("Completed gauge history failed 24-hour continuity/freshness validation")
        context = stamps[-1]
        rows = tuple((h["timestamp_utc"], h["rainfall_mm"]) for h in hours)
        rain_label = ("ML rainfall forecast: genuine completed-hour gauge history (source transfer unvalidated)"
                      if payload.rain_source == "physical_rain_gauge" else "ML rainfall forecast: SIMULATED completed-hour test history")
    else:
        context = payload.context_at.astimezone(timezone.utc)
        matches = engine.frame.index[engine.frame.timestamp_utc.eq(context)]
        if context.year != 2025 or context.minute or context.second or context.microsecond or len(matches) != 1 or matches[0] < 23:
            raise ValueError("Select an actual hourly archived 2025 origin with 24 preceding rainfall observations")
        history = engine.frame.iloc[int(matches[0])-23:int(matches[0])+1]
        rows = tuple((r.timestamp_utc.isoformat(), float(r.rainfall_mm)) for r in history.itertuples())
        rain_label = "ML rainfall forecast: historical-context demonstration"
    rainfall = list(rainfall_forcing(settings.hybrid_model_directory, settings.hybrid_dataset_path, rows))
    # A fixed initialization prevents compounded projected-depth feedback.
    adjusted = water_balance(initial_depth, observed_rain, max((now-initial_at).total_seconds()/60, 1e-9), basin)
    origin = context if genuine else now.replace(minute=0, second=0, microsecond=0)
    result = project(adjusted["depth_cm"], rainfall, basin, now, rainfall_origin=origin)
    expires = now + timedelta(seconds=5 if payload.mode == "live" else 60)
    if payload.mode == "live":
        expires = min(expires, datetime.fromisoformat(snapshot["last_received_at"]) + timedelta(seconds=30))
    result.update(status="available", mode=payload.mode, checked_at=now.isoformat(),
                  valid_until=expires.isoformat(),
                  initial_depth_cm=initial_depth, initial_source=initial_source, initialization_at=initial_at.isoformat(),
                  model_version=engine.metadata["version"], rainfall_source=rain_label,
                  rainfall_context_at=context.isoformat(), rainfall_hourly_mm=rainfall,
                  rainfall_history=[{"timestamp_utc":stamp,"rainfall_mm":amount,"interval_seconds":3600,"valid":True} for stamp,amount in rows],
                  observed_rainfall_since_initialization_mm=observed_rain, adjusted=adjusted,
                  rain_snapshot=snapshot if payload.mode == "live" else None,
                  reason="Controlled-basin projection; archived context is not current weather." if not genuine else "Controlled-basin projection; gauge source transfer is unvalidated.")
    return result

# Preserve explicit test/maintenance cache controls. Filesystem versioning still runs on every access.
get_engine.cache_clear=_get_engine.cache_clear
rainfall_forcing.cache_clear=_rainfall_forcing.cache_clear
