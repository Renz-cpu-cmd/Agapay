from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import engine
from app.routers import alerts, auth, community_alerts, health, monitoring, notification_devices, stations, telemetry, users, sos, predictions, rain_gauge, hybrid_projections
from app.ingress_middleware import IngressBodyLimitMiddleware
from app.routers import exercises, alert_governance,product_preferences,identity,sos_response,response_resources
from app.routers import operations,deliveries,forecasts,privacy,staff_workspaces


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.migrations import require_current
    require_current(engine)
    from app.services.privacy_governance import approved_record, require_released
    from sqlalchemy.orm import Session
    with Session(engine) as db: require_released(db)
    if settings.environment == 'production': approved_record(settings.service_governance_path)

    mqtt_client = None
    if settings.mqtt_enabled and not settings.mqtt_external_subscriber:
        from app.services.mqtt_subscriber import start_mqtt_subscriber

        mqtt_client = start_mqtt_subscriber(settings)
        log.info("MQTT subscriber enabled")

    yield

    if mqtt_client is not None:
        from app.services.mqtt_subscriber import stop_mqtt_subscriber

        stop_mqtt_subscriber(mqtt_client)


app = FastAPI(
    title="AGAPAY API",
    version="0.1.0",
    description="Day-1 telemetry and database foundation for AGAPAY.",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(staff_workspaces.router)
app.include_router(privacy.router)
app.include_router(operations.router)
app.include_router(deliveries.router)
app.include_router(forecasts.router)
app.include_router(stations.router)
app.include_router(product_preferences.router)
app.include_router(telemetry.router)
app.include_router(exercises.router)
app.include_router(alert_governance.router)
app.include_router(auth.router)
app.include_router(identity.router)
app.include_router(users.router)
app.include_router(sos.router)
app.include_router(sos_response.router)
app.include_router(response_resources.router)
app.include_router(predictions.router)
app.include_router(monitoring.router)
app.include_router(alerts.router)
app.include_router(community_alerts.router)
app.include_router(notification_devices.router)
app.include_router(rain_gauge.router)
app.include_router(hybrid_projections.router)
from app.routers import exercise_notifications  # noqa: E402  (isolated EXERCISE_TEST workflow)
app.include_router(exercise_notifications.router)
from app.routers import delivery_recovery  # noqa: E402  (R2 P0 restored-delivery reconciliation)
app.include_router(delivery_recovery.router)
from app.routers import station_tracking  # noqa: E402
app.include_router(station_tracking.admin_router)
app.include_router(station_tracking.tracker_router)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])
app.add_middleware(IngressBodyLimitMiddleware)


from sqlalchemy.exc import TimeoutError as PoolTimeoutError  # noqa: E402


@app.exception_handler(PoolTimeoutError)
async def database_pool_exhausted(request, exc):
    # R2: a connection could not be checked out within database_pool_timeout_seconds. The
    # session never started a transaction, so nothing was written; clients may retry.
    log.warning("database connection pool exhausted route=%s", request.url.path)
    return JSONResponse(status_code=503, headers={"Retry-After": "2"},
                        content={"detail": "Database capacity is temporarily exhausted; retry shortly"})


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]})


@app.middleware("http")
async def private_account_responses(request, call_next):
    from app.services import observability as obs
    import time
    correlation=obs.correlation(request.headers.get('X-Request-ID'))
    counter={'value':0}
    token=obs.request_id.set(correlation);queries=obs.query_count.set(counter);started=time.perf_counter()
    try:
        response=await call_next(request)
    except Exception:
        obs.observe('http.other',time.perf_counter()-started,failed=True)
        obs.event('http.failed',correlation_id=correlation,status=500)
        obs.query_count.reset(queries)
        raise
    finally:
        obs.request_id.reset(token)
    response.headers['X-Request-ID']=correlation
    if settings.environment=='development':response.headers['X-DB-Queries']=str(counter['value'])
    route=getattr(request.scope.get('route'),'path','unmatched')
    if request.url.path!='/live':
        category='monitoring' if route.startswith('/api/monitoring') else 'hybrid' if route.startswith('/api/hybrid') else 'sos' if route.startswith('/api/sos') else 'other'
        obs.observe('http.'+category,time.perf_counter()-started,failed=response.status_code>=500)
        obs.event('http.completed',correlation_id=correlation,status=response.status_code,route=route,duration_seconds=round(time.perf_counter()-started,6))
        obs.schedule_flush()
    obs.query_count.reset(queries)
    if request.url.path.startswith(('/api/operations','/api/notification-deliveries','/api/notification-receipts','/api/forecast','/api/rain-activity')):response.headers['Cache-Control']='no-store'
    if request.url.path.startswith(("/api/privacy", "/api/auth", "/api/users", "/api/stations", "/api/telemetry", "/api/exercises", "/api/sos", "/api/predictions", "/api/monitoring", "/api/alerts", "/api/community-alerts", "/api/notification-devices", "/api/rain-gauge", "/api/hybrid-projections", "/api/alert-governance", "/api/alert-subscriptions", "/api/official-notices", "/api/sensor-alerts", "/api/response-resources", "/api/exercise-notifications")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "name": "AGAPAY API",
        "version": "0.1.0",
        "docs": "/docs",
    }
