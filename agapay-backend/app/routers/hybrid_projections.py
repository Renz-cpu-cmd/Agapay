from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config import Settings, get_settings
from app.database import get_db
from app.hybrid_schemas import HybridProjectionRequest,HybridProjectionResponse
from app.models import User
from app.routers.telemetry import require_station
from app.services.accounts import current_user
from app.services.monitoring_service import monitoring_snapshot
from app.services.rain_gauge_service import RainGaugeStore

router = APIRouter(prefix="/api/hybrid-projections", tags=["experimental dashboard projection"])


@router.post("/{station_id}",response_model=HybridProjectionResponse,response_model_exclude_none=True)
def projection(station_id: str, payload: HybridProjectionRequest, db: Session = Depends(get_db),
               settings: Settings = Depends(get_settings), user: User = Depends(current_user)):
    if user.role not in ("admin", "officer"):
        raise HTTPException(403, "Staff access required")
    return run_projection(station_id, payload, db, settings)


def run_projection(station_id, payload, db, settings):
    from app.services.read_models import cached,digest,generation,file_version
    from sqlalchemy.orm import sessionmaker
    if settings.environment != "development" or not settings.hybrid_projection_enabled:
        raise HTTPException(403,"Experimental controlled-basin projections are disabled")
    require_station(db,station_id)
    request_key=payload.model_dump(mode='json')
    if payload.depth_source=='sensor':request_key.pop('initialization_at',None)
    key="hybrid:"+digest([station_id,request_key])[:48]
    artifact=[file_version(Path(settings.hybrid_model_directory)/name) for name in ("metadata.json","forest.json")]
    fingerprint=generation(db,settings,extra=[artifact,file_version(settings.hybrid_dataset_path)],station_id=station_id)
    factory=sessionmaker(bind=db.get_bind(),expire_on_commit=False)
    if db.new or db.dirty or db.deleted:raise RuntimeError('Projection reads require a clean read transaction')
    db.rollback()
    def build():
        with factory() as reader:return _run_projection(station_id,payload,reader,settings)
    return cached(key,fingerprint,build,ttl=settings.read_model_seconds,settings=settings,session_factory=factory,kind="hybrid",wait_seconds=2)


def _run_projection(station_id, payload, db, settings):
    if settings.environment != "development" or not settings.hybrid_projection_enabled:
        raise HTTPException(403, "Experimental controlled-basin projections are disabled")
    require_station(db, station_id)
    from app.services.hybrid_projection import dashboard_projection, unavailable
    now = datetime.now(timezone.utc)
    sensor = snapshot = None
    if payload.mode == "live":
        if not settings.rain_gauge_enabled:
            return {**unavailable("Live rain feed is disabled. Select historical ML demonstration or start the configured live rain backend.", now), "station_id": station_id}
        if payload.rain_source == "simulated_rain_gauge" and not settings.rain_gauge_allow_simulator:
            raise HTTPException(403, "Test simulator is disabled")
        if payload.depth_source == "sensor":
            monitor = monitoring_snapshot(db, stale_after_seconds=settings.telemetry_stale_after_seconds, history_limit=2, now=now,settings=settings,station_ids=[station_id])
            sensor = next(s.model_dump(mode="json") for s in monitor.stations if s.station_id == station_id)
        anchor = datetime.fromisoformat(sensor["last_valid_depth_at"].replace("Z", "+00:00")) if sensor and sensor["last_valid_depth_at"] else payload.initialization_at or now
        payload = payload.model_copy(update={"initialization_at": anchor})
        try:
            snapshot = RainGaugeStore(Path(settings.rain_gauge_store_path),read_only=True,raw_retention_days=settings.rain_raw_retention_days).snapshot(station_id, payload.rain_source, anchor_at=anchor, now=now)
        except (sqlite3.Error,OSError,ValueError):
            return {**unavailable('Independent rain journal unavailable; operator maintenance is required.',now),'station_id':station_id}
        from app.device_config import current_configuration
        configuration=current_configuration(db,station_id)
        if configuration and snapshot.get('calibration_version')!=configuration.config_hash:
            snapshot.update(connected=False,status="configuration_mismatch",ml_ready=False)
    try:
        result = dashboard_projection(payload, settings, snapshot=snapshot, sensor=sensor, now=now)
        result["station_id"] = station_id
        return result
    except (ValueError, TypeError) as error:
        raise HTTPException(422, str(error)) from error
    except (FileNotFoundError, ImportError, KeyError):
        raise HTTPException(503, "Hybrid model artifacts or ML runtime are unavailable. Start the API with requirements-rain-demo.txt installed.")


@router.get("/{station_id}/summary",response_model=HybridProjectionResponse,response_model_exclude_none=True)
def projection_summary(station_id: str, db: Session = Depends(get_db),
                       settings: Settings = Depends(get_settings), user: User = Depends(current_user)):
    """Resident-readable demo summary with server-owned inputs, never staff controls.

    Uses the same assumed basin as the automatic local web demo. It does not
    inherit another browser's private settings or publish a field-validated forecast.
    """
    if user.role not in ('admin','officer'):raise HTTPException(403,'Private experimental workspace is staff-only; use published predictions and rain activity')
    payload = HybridProjectionRequest(controlled_basin_confirmed=True, mode="live", depth_source="sensor")
    try:
        result = run_projection(station_id, payload, db, settings)
    except HTTPException as error:
        if error.status_code != 422:
            raise
        from app.services.hybrid_projection import unavailable
        result = {**unavailable("Fresh measured depth and physical rainfall are required for this demonstration.", datetime.now(timezone.utc)), "station_id": station_id}
    fields = ("station_id", "status", "reason", "notice", "advisory_only", "mode", "checked_at", "valid_until",
              "initial_depth_cm", "initial_source", "initialization_at", "model_version", "rainfall_source",
              "rainfall_context_at", "rainfall_history", "adjusted", "points")
    summary = {key: result[key] for key in fields if key in result}
    snapshot = result.get("rain_snapshot")
    # Gauge connectivity is independent of whether measured depth can initialize
    # a forecast. Preserve rainfall activity when the depth input is stale.
    if snapshot is None and settings.rain_gauge_enabled:
        try:
            snapshot = RainGaugeStore(Path(settings.rain_gauge_store_path),read_only=True,raw_retention_days=settings.rain_raw_retention_days).snapshot(station_id, "physical_rain_gauge")
        except (sqlite3.Error,OSError,ValueError):
            snapshot=None
    summary["rain_activity"] = {key: snapshot.get(key) for key in (
        "station_id", "data_source", "connected", "checked_at", "last_received_at", "current_hour_start",
        "incomplete_hour_mm", "completed_hours", "ml_ready", "current_hour_product", "calibration_version", "mm_per_tip", "source_trusted", "source_class", "product_version")} if snapshot else None
    summary["setup_label"] = "Controlled demonstration · assumed basin parameters"
    return summary

