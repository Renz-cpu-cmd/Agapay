"""Single MQTT owner, separate from multi-process HTTP serving."""
import signal
import logging
from threading import Event
from app.process_pool import background_defaults
background_defaults()  # Single MQTT owner: small dedicated pool unless explicitly configured.
from app.serve_production import preflight  # noqa: E402
from app.services.mqtt_subscriber import start_mqtt_subscriber, stop_mqtt_subscriber


def main():
    settings = preflight()
    if not settings.mqtt_enabled or settings.mqtt_external_subscriber or not settings.mqtt_status_path:
        raise SystemExit('Dedicated ingestion service requires MQTT explicitly enabled')
    stop = Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    client = start_mqtt_subscriber(settings)
    from app.services.broker_health import publish_shared
    from app.services import observability as obs
    try:
        while not stop.is_set():
            try:
                publish_shared(settings.mqtt_status_path, 'connected' if client.is_connected() else 'disconnected')
            except OSError:
                logging.warning('Shared ingestion heartbeat unavailable; observation will expire; ingestion continues')
            obs.heartbeat('ingestion','healthy' if client.is_connected() else 'failed','broker_connection')
            obs.flush(force=True)
            stop.wait(5)
    finally:
        stop_mqtt_subscriber(client)
        try:publish_shared(settings.mqtt_status_path, 'disconnected')
        except OSError:pass
        obs.heartbeat('ingestion','stopped');obs.flush(force=True)


if __name__ == '__main__':
    main()
