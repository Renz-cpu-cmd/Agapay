from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import health, stations, telemetry
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


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "name": "AGAPAY API",
        "version": "0.1.0",
        "docs": "/docs",
    }
