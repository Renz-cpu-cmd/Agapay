"""Read-only audit of application behavior using a disposable in-memory database.

Run from agapay-backend with its Python environment. No lifespan, MQTT, provider,
existing database, account, or physical device is used.
"""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "agapay-backend"))
os.environ["AGAPAY_DATABASE_URL"] = "sqlite://"
os.environ["AGAPAY_MQTT_ENABLED"] = "false"
os.environ["AGAPAY_NOTIFICATION_PROVIDER"] = "disabled"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Alert, NotificationEvent, Station, Telemetry, utc_now
from app.services.monitoring_service import monitoring_snapshot

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)


def memory_db():
    with Session(engine, expire_on_commit=False) as db:
        yield db


app.dependency_overrides[get_db] = memory_db
client = TestClient(app)  # Deliberately no context manager: no startup/lifespan.
result = {"scope": "disposable in-memory SQLite; no external calls or live writes"}
created = client.post("/api/stations", json={"station_id": "AUDIT_STATION", "station_name": "Disposable audit station"})
assert created.status_code == 201
result["unauthenticated_station_creation"] = created.status_code


def post_sample(sequence, depth, quality="valid", station_id="AUDIT_STATION"):
    return client.post("/api/telemetry", json={
        "station_id": station_id, "sequence_no": sequence,
        "water_depth_cm": depth, "rainfall_mm": 0,
        "sensor_quality": quality, "device_uptime_ms": sequence,
        "firmware_version": "1.0.0",
    })


assert post_sample(1001, 105).status_code == 201
with Session(engine) as db:
    alert = db.scalar(select(Alert))
    result["unauthenticated_telemetry_side_effect"] = {
        "http_status": 201, "alert_severity": alert.current_severity,
        "notification_event_created": db.scalar(select(NotificationEvent.id)) is not None,
    }

assert post_sample(1000, 1).status_code == 201
with Session(engine) as db:
    alert = db.scalar(select(Alert))
    result["out_of_order_unique_sequence"] = {
        "received_sequences": [1001, 1000], "http_status_for_older_sequence": 201,
        "episode_status": alert.status, "severity": alert.current_severity,
    }
    station = db.scalar(select(Station))
    station.status = "maintenance"
    db.commit()

assert post_sample(1002, 105).status_code == 201
with Session(engine) as db:
    alerts = db.scalars(select(Alert).order_by(Alert.id)).all()
    result["maintenance_station_ingestion"] = {
        "http_status": 201, "latest_episode_status": alerts[-1].status,
        "latest_episode_severity": alerts[-1].current_severity,
    }
    for sample in db.scalars(select(Telemetry)):
        sample.recorded_at = utc_now() - timedelta(hours=1)
    station = db.scalar(select(Station))
    station.status = "active"
    db.commit()

assert post_sample(1003, None, "invalid").status_code == 201
with Session(engine) as db:
    snapshot = monitoring_snapshot(db, stale_after_seconds=30, history_limit=20)
    station = snapshot.stations[0]
    result["invalid_heartbeat_after_old_valid_depth"] = {
        "connection": station.connection_status, "age_seconds": station.age_seconds,
        "current_depth_cm": station.current_depth_cm,
        "sensor_quality": station.sensor_quality,
        "observed_at": station.observed_at.isoformat(),
        "last_valid_depth_age_seconds": 3600,
        "source_inferred_from_client_firmware_string": station.source,
    }

from app.config import Settings
from app.services.mqtt_subscriber import start_mqtt_subscriber

fake_mqtt = MagicMock()
retained = {
    "station_id": "AUDIT_STATION", "sequence_no": 1004,
    "water_depth_cm": 10, "rainfall_mm": 0, "sensor_quality": "valid",
    "device_uptime_ms": 1004, "firmware_version": "1.0.0",
}
with patch("paho.mqtt.client.Client", return_value=fake_mqtt), patch(
    "app.services.mqtt_subscriber.SessionLocal", lambda: Session(engine)
):
    subscriber = start_mqtt_subscriber(Settings(mqtt_enabled=True, rain_gauge_enabled=False))
    subscriber.on_message(subscriber, None, SimpleNamespace(
        topic="agapay/stations/AUDIT_STATION/telemetry",
        payload=json.dumps(retained).encode(), retain=True,
    ))
with Session(engine) as db:
    accepted = db.scalar(select(Telemetry).where(Telemetry.sequence_no == 1004))
    result["retained_mqtt_telemetry"] = {
        "stored": accepted is not None,
        "server_received_age_seconds": (utc_now() - accepted.recorded_at.replace(tzinfo=utc_now().tzinfo)).total_seconds(),
    }

assert client.post("/api/stations", json={"station_id": "AUDIT_CHATTER", "station_name": "Disposable noise probe"}).status_code == 201
for sequence, depth in enumerate((59.9, 60.1, 59.9, 60.1), 1):
    assert post_sample(sequence, depth, station_id="AUDIT_CHATTER").status_code == 201
with Session(engine) as db:
    episodes = db.scalars(select(Alert).where(Alert.station_id == "AUDIT_CHATTER")).all()
    result["threshold_chatter"] = {
        "depths_cm": [59.9, 60.1, 59.9, 60.1],
        "episodes_created": len(episodes),
        "notification_events_total_including_other_probes": len(db.scalars(select(NotificationEvent)).all()),
    }

print(json.dumps(result, indent=2))
client.close()
app.dependency_overrides.clear()
engine.dispose()
