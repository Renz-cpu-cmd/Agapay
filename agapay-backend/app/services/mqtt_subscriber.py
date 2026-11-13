import json
import logging
from pathlib import Path
import re
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.database import SessionLocal
from app.station_schemas import MqttRainEnvelope, MqttTelemetryEnvelope
from app.services.rain_gauge_service import RainGaugeStore
from app.services.station_security import MAX_INGRESS_BYTES, prepare_ingress
from app.services.telemetry_service import ConflictingTelemetryError, DuplicateTelemetryError, UnknownStationError, ingest_telemetry
from app.services.exercise_telemetry import ingest_exercise
from app.services.ingress_provenance import trusted_ingress
from app.models import StationIdentity
from app.services.broker_health import observe as observe_broker
from app.services.broker_health import observe_subscription


log = logging.getLogger(__name__)
TOPIC_PATTERN = re.compile(r"^agapay/(?:(exercises)/)?stations/([A-Z0-9_-]{3,50})/telemetry$")
RAIN_TOPIC_PATTERN = re.compile(r"^agapay/(?:(exercises)/)?stations/([A-Z0-9_-]{3,50})/rain$")


def start_mqtt_subscriber(settings: Settings) -> Any:
    import paho.mqtt.client as mqtt

    # Broker credentials/ACL are an independent control, not device identity.
    if not settings.mqtt_username or not settings.mqtt_password.get_secret_value():
        raise ValueError("MQTT ingestion requires a dedicated authenticated broker account")
    if settings.environment != "development" and not settings.mqtt_tls:
        raise ValueError("MQTT ingestion requires TLS outside development")

    observe_broker("connecting")
    pending_subscriptions=set()

    def on_disconnect(client, userdata, flags, reason_code, properties):
        observe_broker("disconnected")
        pending_subscriptions.clear();observe_subscription('unconfirmed')

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        observe_broker("connected" if reason_code == 0 else "disconnected")
        pending_subscriptions.clear();observe_subscription('unconfirmed')
        if reason_code == 0:
            def required(topic):
                result=client.subscribe(topic,qos=1)
                if isinstance(result,tuple) and result[0]==0:pending_subscriptions.add(result[1])
                else:observe_subscription('rejected')
            required(settings.mqtt_topic)
            if settings.environment=='development':client.subscribe("agapay/exercises/stations/+/telemetry", qos=1)
            if settings.rain_gauge_enabled:
                required(settings.rain_gauge_topic)
                if settings.environment=='development':client.subscribe("agapay/exercises/stations/+/rain", qos=1)
            log.info("MQTT subscriptions requested")
        else:
            log.error("MQTT connection failed: %s", reason_code)

    def on_subscribe(client,userdata,mid,reason_codes,properties):
        if mid not in pending_subscriptions:return
        failed=not reason_codes or any(getattr(code,'is_failure',False) or isinstance(code,int) and code>=128 for code in reason_codes)
        pending_subscriptions.discard(mid)
        if failed:observe_subscription('rejected')
        elif not pending_subscriptions:
            from app.services.broker_health import subscription_snapshot
            if subscription_snapshot(settings)!='rejected':observe_subscription('confirmed')

    def on_message(client, userdata, message) -> None:
        rain_match = RAIN_TOPIC_PATTERN.fullmatch(message.topic)
        water_match = TOPIC_PATTERN.fullmatch(message.topic)
        match = rain_match or water_match
        if match is None:
            log.warning("Rejected MQTT topic outside the station ingress contract")
            return
        if rain_match and not settings.rain_gauge_enabled:
            return
        if len(message.payload) > MAX_INGRESS_BYTES or getattr(message, "retain", False):
            log.warning("Rejected oversized or retained MQTT ingress")
            return
        station_id = match.group(2)
        stream = "exercise" if match.group(1) else "operational"
        db = SessionLocal()
        try:
            if rain_match:
                envelope = MqttRainEnvelope.model_validate_json(message.payload)
                event = envelope.rain
                if event.station_id != station_id:
                    raise ValueError("Station mismatch")
                if event.data_source == "simulated_rain_gauge" and not settings.rain_gauge_allow_simulator:
                    raise ValueError("Simulator disabled")
                # Acquire the same station lock used by configuration/revocation
                # before reading the expected calibration revision.
                credential = prepare_ingress(db, envelope.ingest_token.get_secret_value(), station_id, "mqtt", "rain", settings)
                calibration = settings.rain_gauge_calibrations.get(station_id)
                from app.device_config import current_configuration
                configuration=current_configuration(db,station_id)
                if configuration:
                    calibration=configuration.installation['rain_mm_per_tip']
                    if event.schema_version!=2 or event.calibration_version!=configuration.config_hash:
                        raise ValueError("Applied rain calibration does not match reviewed station configuration")
                elif event.schema_version==2:
                    raise ValueError("Versioned rain requires a reviewed station configuration")
                if calibration is None:
                    raise ValueError("Calibration missing")
                identity = db.get(StationIdentity, station_id)
                context = trusted_ingress(db, station_id, identity.version, identity.device_id, credential.id, "mqtt", stream)
                expected_source = "physical_rain_gauge" if context["source_class"] == "physical_device" else "simulated_rain_gauge"
                if event.data_source != expected_source:
                    raise ValueError("Rain source does not match registry")
                # Hold the station lock until journal commit; revocation waits.
                RainGaugeStore(Path(settings.rain_gauge_store_path)).ingest(event, calibration, provenance=context)
                db.commit()
                prefix = "agapay/exercises" if stream == "exercise" else "agapay"
                client.publish(f"{prefix}/stations/{station_id}/rain-ack", json.dumps({
                    "boot_id": event.boot_id, "cumulative_tip_count": event.cumulative_tip_count,
                    "packet_sequence": event.packet_sequence, "device_uptime_ms": event.device_uptime_ms,
                }), qos=1, retain=False)
            else:
                envelope = MqttTelemetryEnvelope.model_validate_json(message.payload)
                payload = envelope.telemetry
                if payload.station_id != station_id:
                    raise ValueError("Station mismatch")
                credential = prepare_ingress(db, envelope.ingest_token.get_secret_value(), station_id, "mqtt", "telemetry", settings)
                ingest = ingest_exercise if stream == "exercise" else ingest_telemetry
                if stream == "operational":
                    from app.services.depth_ack import acknowledgement, acknowledged_duplicate
                    try:
                        stored = ingest(db, payload, credential_id=credential.id, transport="mqtt",
                                        historical=envelope.delivery_mode == "backfill")
                    except ConflictingTelemetryError:
                        raise
                    except DuplicateTelemetryError:
                        # Authentication/revocation/identity checks ran before dedup.
                        # Lost ACKs are retried and acknowledged only for exact content.
                        stored = acknowledged_duplicate(db, payload)
                    client.publish(f"agapay/stations/{station_id}/telemetry-ack",
                                   json.dumps(acknowledgement(payload,json.loads(message.payload)["telemetry"])), qos=1, retain=False)
                else:
                    if envelope.delivery_mode != "live":
                        raise ValueError("Exercise journal replay is not enabled")
                    stored = ingest(db, payload, credential_id=credential.id, transport="mqtt")
                log.info("Stored MQTT %s telemetry %s/%s", stream, station_id, payload.sequence_no)
        except ConflictingTelemetryError:
            db.rollback()
            log.warning("Rejected conflicting MQTT telemetry for %s", station_id)
        except DuplicateTelemetryError:
            db.rollback()
            log.info("Ignored duplicate MQTT telemetry for %s", station_id)
        except (UnknownStationError, ValidationError, ValueError, HTTPException, OSError):
            db.rollback()
            # Errors/SQL parameters may contain the secret envelope: no traceback.
            log.warning("Rejected MQTT ingress for station %s; no acknowledgement", station_id)
        except Exception:
            db.rollback()
            log.error("MQTT ingress persistence failed for station %s; no acknowledgement", station_id)
        finally:
            db.close()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.mqtt_client_id)
    client.on_connect, client.on_message, client.on_disconnect = on_connect, on_message, on_disconnect
    client.on_subscribe=on_subscribe
    if settings.mqtt_tls:
        from app.services.transport_security import mqtt_context
        client.tls_set_context(mqtt_context(settings))
    client.username_pw_set(settings.mqtt_username, settings.mqtt_password.get_secret_value())
    client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.loop_start()
    if settings.forecast_downlink_enabled:
        from app.services.forecast_downlink import start_publisher
        client._agapay_forecast_stop = start_publisher(client, settings)
    return client


def stop_mqtt_subscriber(client: Any) -> None:
    observe_broker("disconnected")
    stop = getattr(client, "_agapay_forecast_stop", None)
    if stop is not None:
        stop.set()
    client.disconnect()
    client.loop_stop()
