"""Exercise the installed Paho callback API without opening network sockets."""
import json
from pathlib import Path
from types import SimpleNamespace

import paho.mqtt.client as mqtt
import pytest
from sqlalchemy import select

from app.config import Settings
from app.database import SessionLocal
from app.models import Alert, Station, Telemetry
from app.services.mqtt_subscriber import start_mqtt_subscriber, stop_mqtt_subscriber
from station_support import device_token, ordering_fields


@pytest.fixture
def subscriber(client, monkeypatch):
    station_id = "MQTT_PREFLIGHT"
    with SessionLocal() as db:
        db.add(Station(station_id=station_id, station_name="MQTT test", status="active"))
        db.commit()
    calls = []
    monkeypatch.setattr(mqtt.Client, "connect_async", lambda self, *a, **k: calls.append("connect"))
    monkeypatch.setattr(mqtt.Client, "loop_start", lambda self: calls.append("start"))
    monkeypatch.setattr(mqtt.Client, "loop_stop", lambda self: calls.append("stop"))
    monkeypatch.setattr(mqtt.Client, "disconnect", lambda self: calls.append("disconnect"))
    subscriber = start_mqtt_subscriber(Settings(
        mqtt_host="127.0.0.1", mqtt_username="test-backend", mqtt_password="test-broker-only", mqtt_tls=False,
    ))
    assert isinstance(subscriber, mqtt.Client)
    assert subscriber.callback_api_version == mqtt.CallbackAPIVersion.VERSION2
    assert calls == ["connect", "start"]
    yield subscriber, station_id
    stop_mqtt_subscriber(subscriber)
    assert calls[-2:] == ["disconnect", "stop"]
    with SessionLocal() as db:
        # Children first: PostgreSQL enforces every foreign key into this station's rows.
        from station_support import purge_station
        purge_station(db, station_id)
        db.commit()


def deliver(subscriber, topic_station_id, sequence, depth, **changes):
    payload = {
        **ordering_fields(topic_station_id, sequence),
        "station_id": topic_station_id, "sequence_no": sequence, "water_depth_cm": depth,
        "rainfall_mm": 0, "sensor_quality": "valid" if depth is not None else "invalid",
        "device_uptime_ms": sequence * 10000, "firmware_version": "0.2.0",
    }
    payload.update(changes)
    subscriber.on_message(subscriber, None, SimpleNamespace(
        topic=f"agapay/stations/{topic_station_id}/telemetry",
        payload=json.dumps({"ingest_token":device_token(topic_station_id),"telemetry":payload}).encode(),
    ))


def test_real_paho_callback_persists_and_deduplicates(subscriber):
    sub, station = subscriber
    deliver(sub, station, 1, 60)
    deliver(sub, station, 1, 100)  # Changed retry must not escalate the episode.
    deliver(sub, station, 2, None)
    with SessionLocal() as db:
        # Explicit order: PostgreSQL does not return rows in insertion order.
        rows = list(db.scalars(select(Telemetry).where(Telemetry.station_id == station).order_by(Telemetry.sequence_no)))
        episode = db.scalar(select(Alert).where(Alert.station_id == station))
        assert len(rows) == 2
        assert rows[0].water_depth_cm == 60
        assert rows[1].sensor_quality == "invalid" and rows[1].water_depth_cm is None
        assert episode.current_severity == "ADVISORY" and episode.latest_sequence_no == 1


def test_real_paho_callback_rejects_malformed_and_mismatched_telemetry(subscriber):
    sub, station = subscriber
    deliver(sub, station, 1, 20, sensor_quality="invalid")
    deliver(sub, station, 2, 20, station_id="OTHER_STATION")
    sub.on_message(sub, None, SimpleNamespace(
        topic=f"agapay/stations/{station}/telemetry", payload=b"{invalid json",
    ))
    with SessionLocal() as db:
        assert db.scalar(select(Telemetry.id).where(Telemetry.station_id == station)) is None


def test_paho_dependency_is_declared():
    assert "paho-mqtt==2.1.0" in Path(__file__).parents[1].joinpath("requirements.txt").read_text()
