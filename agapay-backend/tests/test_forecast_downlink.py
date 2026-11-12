"""Advisory forecast downlink to station displays: gated copy of read_latest, compact, never partial."""
from datetime import timedelta
import json
import threading

from app.database import SessionLocal
from app.models import Station, StationIdentity, utc_now
from app.prediction_schemas import HORIZONS, PredictionResponse
from app.services import forecast_downlink as downlink

CONFIG = 'c' * 64


def prediction(status='available', *, ttl=120, bounded=True, config=CONFIG, now=None):
    now = now or utc_now()
    available = status == 'available'
    points = [dict(horizon_minutes=h, target_at=now + timedelta(minutes=h) if available else None,
                   water_depth_cm=80.0 + h / 10 if available else None,
                   lower_depth_cm=(76.04 + h / 10 if bounded else None) if available else None,
                   upper_depth_cm=(84.96 + h / 10 if bounded else None) if available else None) for h in HORIZONS]
    return PredictionResponse.model_validate(dict(
        station_id='STATION_001', status=status, reason='synthetic', source='model' if available else 'none',
        checked_at=now, generated_at=now - timedelta(seconds=20) if available else None,
        valid_until=now + timedelta(seconds=ttl) if available else None, model_version='m' * 64 if available else None,
        input_status='usable', sample_count=12, valid_sample_count=12, timestamp_basis='device_measured',
        input_last_recorded_at=now if available else None, preview_allowed=False, forecasts=points,
        configuration_hash=config if available else None))


def test_available_forecast_is_compact_bounded_and_advisory():
    now = utc_now()
    body = downlink.message(prediction(now=now), now)
    assert body['status'] == 'available' and body['advisory_only'] is True and body['v'] == 1
    assert body['points'] == [[30, 83.0, 79.0, 88.0], [60, 86.0, 82.0, 91.0], [90, 89.0, 85.0, 94.0]]
    assert body['ttl_s'] == 120 and body['valid_until'] - body['published_at'] == 120 and body['config'] == CONFIG
    assert len(body['model']) == 16 and len(downlink.payload(prediction(now=now), now)) <= downlink.MAX_BYTES


def test_unavailable_states_never_carry_numbers():
    for status in ('not_trained', 'unavailable', 'insufficient_data', 'stale_data', 'invalid_data', 'service_error'):
        body = downlink.message(prediction(status))
        assert body['status'] == status and 'points' not in body and 'valid_until' not in body


def test_partial_unbounded_or_unbound_forecasts_are_downgraded_not_sent():
    now = utc_now()
    assert downlink.message(prediction(bounded=False, now=now), now)['status'] == 'unavailable', 'no interval, no numbers'
    assert downlink.message(prediction(config=None, now=now), now)['status'] == 'unavailable', 'unknown configuration'
    later = now + timedelta(seconds=121)  # expired between read_latest and publication
    assert downlink.message(prediction(now=now), later)['status'] == 'unavailable'
    long_lived = downlink.message(prediction(ttl=99999, now=now), now)
    assert long_lived['ttl_s'] == downlink.MAX_TTL_SECONDS


class Client:
    def __init__(self, connected=True):
        self.sent, self.connected = [], connected

    def publish(self, topic, data, qos, retain):
        self.sent.append((topic, json.loads(data), qos, retain))

    def is_connected(self):
        return self.connected


def _identity(db, station_id, state):
    db.add(Station(station_id=station_id, station_name='Synthetic downlink ' + station_id))
    db.flush()
    db.add(StationIdentity(station_id=station_id, device_id='dev-' + station_id, state=state,
                           reference_datum='synthetic datum', calibration_note='synthetic'))


def test_publish_all_covers_commissioned_stations_only_and_isolates_failures(monkeypatch):
    with SessionLocal() as db:
        _identity(db, 'DOWNLINK_A', 'commissioned')
        _identity(db, 'DOWNLINK_B', 'commissioned')
        _identity(db, 'DOWNLINK_C', 'pending')
        db.commit()
    import app.services.forecast_registry as registry

    def read_latest(db, station_id, preview_allowed):
        assert preview_allowed is False, 'devices only ever receive operational, never preview, forecasts'
        if station_id == 'DOWNLINK_B':
            raise RuntimeError('synthetic registry failure')
        return prediction('not_trained').model_copy(update={'station_id': station_id})
    monkeypatch.setattr(registry, 'read_latest', read_latest)
    client = Client()
    try:
        assert downlink.publish_all(client, SessionLocal) == 1
        assert [(t, b['status'], q, r) for t, b, q, r in client.sent] == [
            ('agapay/stations/DOWNLINK_A/forecast', 'not_trained', 1, False)], 'not retained; B failed alone; C not commissioned'
    finally:
        with SessionLocal() as db:
            db.query(StationIdentity).filter(StationIdentity.station_id.like('DOWNLINK_%')).delete(synchronize_session=False)
            db.query(Station).filter(Station.station_id.like('DOWNLINK_%')).delete(synchronize_session=False)
            db.commit()


def test_publisher_runs_only_while_connected_and_stops(monkeypatch):
    calls = threading.Event()
    monkeypatch.setattr(downlink, 'publish_all', lambda client, factory: calls.set())

    class Settings:
        forecast_downlink_seconds = 0.05
    offline = Client(connected=False)
    stop = downlink.start_publisher(offline, Settings())
    assert not calls.wait(0.3), 'nothing is attempted while the broker is unreachable'
    stop.set()
    stop = downlink.start_publisher(Client(), Settings())
    assert calls.wait(1)
    stop.set()


def test_broker_acl_lets_each_station_read_only_its_own_forecast():
    from app.broker_acl import render
    acl = render([dict(station_id='STATION_001', active=True, source_class='physical_device')])
    assert 'user STATION_001\n' in acl and 'topic read agapay/stations/STATION_001/forecast' in acl
    assert 'topic write agapay/stations/STATION_001/forecast' not in acl, 'a station can never forge forecasts'
    assert 'topic write agapay/stations/+/forecast' in acl.split('user backend-ingest')[1]
