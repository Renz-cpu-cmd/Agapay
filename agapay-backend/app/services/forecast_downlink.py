"""Advisory forecast downlink to station displays (agapay/stations/<id>/forecast).

The message is a compact copy of what /api/predictions/<id> already serves through
forecast_registry.read_latest: every deployment, review, identity, freshness and clock gate
stays in one place. Nothing is computed here, and a forecast never feeds alerts, LEDs,
buzzers or notifications on either side.

Not retained: a retained message could reach a device long after it was published, and a
device without a synchronized clock cannot judge its age. A fresh message every
``forecast_downlink_seconds`` lets a reconnecting display catch up within one interval.
"""
import json
import logging
import threading

from sqlalchemy import select

from app.models import StationIdentity, utc_now
from app.prediction_schemas import PredictionResponse

log = logging.getLogger(__name__)
TOPIC = 'agapay/stations/{station_id}/forecast'
SCHEMA_VERSION = 1
MAX_TTL_SECONDS = 7200
MAX_BYTES = 768  # well inside the firmware's 2 KB MQTT buffer


def message(prediction: PredictionResponse, now=None) -> dict:
    """Station-facing summary. Numbers only for an `available`, unexpired, fully bounded forecast."""
    now = now or utc_now()
    published = int(now.timestamp())
    body = dict(v=SCHEMA_VERSION, station_id=prediction.station_id, status=prediction.status, advisory_only=True,
                published_at=published)
    if prediction.status != 'available':
        return body
    points = [[p.horizon_minutes, round(p.water_depth_cm, 1), round(p.lower_depth_cm, 1), round(p.upper_depth_cm, 1)]
              for p in prediction.forecasts
              if p.water_depth_cm is not None and p.lower_depth_cm is not None and p.upper_depth_cm is not None]
    valid_until = int(prediction.valid_until.timestamp()) if prediction.valid_until else 0
    generated = int(prediction.generated_at.timestamp()) if prediction.generated_at else 0
    if not points or not prediction.configuration_hash or not generated or valid_until <= published:
        return dict(body, status='unavailable')  # Never send partial or expired numbers.
    return dict(body, generated_at=generated, valid_until=valid_until, ttl_s=min(valid_until - published, MAX_TTL_SECONDS),
                config=prediction.configuration_hash, model=(prediction.model_version or '')[:16], points=points)


def payload(prediction: PredictionResponse, now=None) -> bytes:
    data = json.dumps(message(prediction, now), separators=(',', ':')).encode()
    if len(data) > MAX_BYTES:
        raise ValueError('Forecast downlink exceeds the station display budget')
    return data


def stations(db):
    return list(db.scalars(select(StationIdentity.station_id).where(StationIdentity.state == 'commissioned')
                           .order_by(StationIdentity.station_id)))


def publish_all(client, session_factory, now=None) -> int:
    """One pass over commissioned stations. A failing station never blocks the others."""
    from app.services.forecast_registry import read_latest
    sent = 0
    with session_factory() as db:
        for station_id in stations(db):
            try:
                data = payload(read_latest(db, station_id, False), now)
                client.publish(TOPIC.format(station_id=station_id), data, qos=1, retain=False)
                sent += 1
            except Exception:
                db.rollback()
                log.warning('Forecast downlink skipped for station %s', station_id)
    return sent


def start_publisher(client, settings, session_factory=None):
    """Background loop owned by the MQTT ingestion client; returns the stop event."""
    if session_factory is None:
        from app.database import SessionLocal as session_factory
    stop = threading.Event()

    def run():
        while not stop.wait(settings.forecast_downlink_seconds):
            if client.is_connected():
                try:
                    publish_all(client, session_factory)
                except Exception:
                    log.warning('Forecast downlink pass failed; retrying next interval')
    threading.Thread(target=run, name='agapay-forecast-downlink', daemon=True).start()
    return stop
