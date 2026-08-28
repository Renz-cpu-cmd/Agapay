import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.database import SessionLocal
from app.schemas import TelemetryCreate
from app.services.telemetry_service import (
    DuplicateTelemetryError,
    UnknownStationError,
    ingest_telemetry,
)


log = logging.getLogger(__name__)
TOPIC_PATTERN = re.compile(r"^agapay/stations/([A-Z0-9_-]{3,50})/telemetry$")


def start_mqtt_subscriber(settings: Settings) -> Any:
    import paho.mqtt.client as mqtt

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            client.subscribe(settings.mqtt_topic, qos=1)
            log.info("MQTT subscribed to %s", settings.mqtt_topic)
        else:
            log.error("MQTT connection failed: %s", reason_code)

    def on_message(client, userdata, message) -> None:
        match = TOPIC_PATTERN.fullmatch(message.topic)
        if match is None:
            log.warning("Rejected unexpected MQTT topic: %s", message.topic)
            return

        db = SessionLocal()
        try:
            raw_payload = json.loads(message.payload.decode("utf-8"))
            payload = TelemetryCreate.model_validate(raw_payload)
            topic_station_id = match.group(1)
            if topic_station_id != payload.station_id:
                raise ValueError("Topic station_id does not match payload station_id")
            ingest_telemetry(db, payload)
            log.info(
                "Stored MQTT telemetry %s/%s",
                payload.station_id,
                payload.sequence_no,
            )
        except DuplicateTelemetryError:
            db.rollback()
            log.info("Ignored duplicate MQTT telemetry from %s", message.topic)
        except (UnknownStationError, ValidationError, ValueError, json.JSONDecodeError):
            db.rollback()
            log.exception("Rejected MQTT telemetry from %s", message.topic)
        except Exception:
            db.rollback()
            log.exception("MQTT processing failed for %s", message.topic)
        finally:
            db.close()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.mqtt_client_id,
    )
    client.on_connect = on_connect
    client.on_message = on_message

    if settings.mqtt_tls:
        client.tls_set()
    if settings.mqtt_username:
        client.username_pw_set(
            settings.mqtt_username,
            settings.mqtt_password,
        )

    client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.loop_start()
    return client


def stop_mqtt_subscriber(client: Any) -> None:
    client.disconnect()
    client.loop_stop()
