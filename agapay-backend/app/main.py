from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import alerts, auth, community_alerts, health, monitoring, stations, telemetry, users, sos, predictions
from app.seed import seed_demo_station


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_station(db)

    mqtt_client = None
    if settings.mqtt_enabled:
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
app.include_router(stations.router)
app.include_router(telemetry.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sos.router)
app.include_router(predictions.router)
app.include_router(monitoring.router)
app.include_router(alerts.router)
app.include_router(community_alerts.router)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type"])


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]})


@app.middleware("http")
async def private_account_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/auth", "/api/users", "/api/sos", "/api/predictions", "/api/monitoring", "/api/alerts", "/api/community-alerts")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "name": "AGAPAY API",
        "version": "0.1.0",
        "docs": "/docs",
    }
