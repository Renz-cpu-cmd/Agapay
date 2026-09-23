from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4
import json
import sys

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Alert, AlertTransition, Station, Telemetry, User
from app.schemas import TelemetryCreate
from app.services import telemetry_service
from app.services.alert_classifier import classify_depth
from app.services.monitoring_service import monitoring_snapshot
from app.services.telemetry_service import DuplicateTelemetryError, ingest_telemetry
from test_accounts import account, headers, reset_accounts, staff


@pytest.fixture
def station(client):
    station_id = "ALERT_" + uuid4().hex[:12].upper()
    with SessionLocal() as db:
        db.add(Station(station_id=station_id, station_name="Isolated alert test station"))
        db.commit()
    return station_id


def payload(station, sequence, depth):
    return dict(station_id=station, sequence_no=sequence, water_depth_cm=depth,
                rainfall_mm=0, sensor_quality="invalid" if depth is None else "valid",
                device_uptime_ms=sequence * 1000, firmware_version="0.2.0")


def send(client, station, sequence, depth):
    response = client.post("/api/telemetry", json=payload(station, sequence, depth))
    assert response.status_code == 201, response.text
    return response.json()


def episodes(station):
    with SessionLocal() as db:
        return db.scalars(select(Alert).where(Alert.station_id == station).order_by(Alert.id)).all()


def transitions(station):
    with SessionLocal() as db:
        return db.scalars(select(AlertTransition).where(AlertTransition.station_id == station)
                          .order_by(AlertTransition.id)).all()


@pytest.mark.parametrize("depth,expected", [
    (0, "NORMAL"), (59.999, "NORMAL"), (60, "ADVISORY"), (84.999, "ADVISORY"),
    (85, "WARNING"), (99.999, "WARNING"), (100, "EVACUATE"), (150, "EVACUATE"),
    (None, None),
])
def test_exact_boundaries_and_unknown(depth, expected):
    configured = Station(threshold_advisory_cm=60, threshold_warning_cm=85, threshold_evacuate_cm=100)
    assert classify_depth(configured, depth) == expected


@pytest.mark.parametrize("depth", [0, 59, None])
def test_normal_or_invalid_without_episode_creates_nothing(client, station, depth):
    send(client, station, 1, depth)
    assert episodes(station) == [] and transitions(station) == []
    with SessionLocal() as db:
        item = next(s for s in monitoring_snapshot(db, stale_after_seconds=30, history_limit=20).stations
                    if s.station_id == station)
        assert item.alert_tier == (None if depth is None else "NORMAL")


@pytest.mark.parametrize("depth,severity", [(60, "ADVISORY"), (85, "WARNING"), (100, "EVACUATE")])
def test_direct_rise_starts_one_episode(client, station, depth, severity):
    sample = send(client, station, 1, depth)
    episode, = episodes(station)
    transition, = transitions(station)
    assert episode.current_severity == episode.highest_severity == severity
    assert episode.status == "ACTIVE" and episode.source == "sensor"
    assert episode.trigger_telemetry_id == episode.latest_telemetry_id == sample["id"]
    assert episode.trigger_depth_cm == episode.latest_depth_cm == depth
    assert episode.trigger_sequence_no == episode.latest_sequence_no == 1
    assert episode.triggered_at == episode.last_transition_at and episode.resolved_at is None
    assert (transition.previous_severity, transition.new_severity) == ("NORMAL", severity)
    assert transition.telemetry_id == sample["id"] and transition.water_depth_cm == depth


def test_complete_lifecycle_is_one_episode_and_retains_peak(client, station):
    for sequence, depth in enumerate([20, 60, 85, 100, 90, 65, 20], 1):
        send(client, station, sequence, depth)
    episode, = episodes(station)
    history = transitions(station)
    assert episode.status == "RESOLVED" and episode.current_severity == "NORMAL"
    assert episode.highest_severity == "EVACUATE"
    assert episode.trigger_depth_cm == 60 and episode.latest_depth_cm == 20
    assert episode.trigger_sequence_no == 2 and episode.latest_sequence_no == 7
    assert episode.resolved_at == episode.last_transition_at == history[-1].transitioned_at
    assert [t.new_severity for t in history] == ["ADVISORY", "WARNING", "EVACUATE", "WARNING", "ADVISORY", "NORMAL"]
    assert [t.previous_severity for t in history] == ["NORMAL", "ADVISORY", "WARNING", "EVACUATE", "WARNING", "ADVISORY"]
    assert {t.alert_id for t in history} == {episode.id}
    assert [t.sequence_no for t in history] == list(range(2, 8))


def test_invalid_samples_preserve_all_episode_fields_and_last_valid_monitoring(client, station):
    from app.alert_schemas import AlertRead
    send(client, station, 1, 85)
    original = AlertRead.model_validate(episodes(station)[0]).model_dump()
    for sequence in range(2, 5):
        send(client, station, sequence, None)
        assert AlertRead.model_validate(episodes(station)[0]).model_dump() == original
    assert len(transitions(station)) == 1
    with SessionLocal() as db:
        item = next(s for s in monitoring_snapshot(db, stale_after_seconds=30, history_limit=20).stations
                    if s.station_id == station)
        assert item.alert_tier == "WARNING" and item.current_depth_cm == 85
        assert item.sensor_quality == "invalid" and item.latest_depth_cm is None
    send(client, station, 5, 105)
    send(client, station, 6, 10)
    assert [t.new_severity for t in transitions(station)] == ["WARNING", "EVACUATE", "NORMAL"]
    assert len(episodes(station)) == 1


def test_same_severity_updates_latest_depth_without_transition(client, station):
    send(client, station, 1, 86)
    before = episodes(station)[0]
    send(client, station, 2, 95)
    after = episodes(station)[0]
    assert before.id == after.id and after.latest_depth_cm == 95
    assert after.trigger_depth_cm == 86 and after.latest_sequence_no == 2
    assert before.last_transition_at == after.last_transition_at
    assert len(transitions(station)) == 1


def test_resolved_history_unchanged_and_later_rise_creates_new_episode(client, station):
    send(client, station, 1, 90)
    send(client, station, 2, 10)
    send(client, station, 3, None)
    send(client, station, 4, 20)
    first, = episodes(station)
    assert first.latest_sequence_no == 2 and first.latest_depth_cm == 10
    send(client, station, 5, 85)
    one, two = episodes(station)
    assert one.id != two.id and one.status == "RESOLVED" and two.status == "ACTIVE"
    assert two.highest_severity == "WARNING" and two.trigger_sequence_no == 5


def test_duplicate_sample_and_changed_retry_never_mutate_history(client, station):
    send(client, station, 1, 100)
    send(client, station, 2, 90)
    for depth in [100, 0, None]:
        assert client.post("/api/telemetry", json=payload(station, 1, depth)).status_code == 409
    episode, = episodes(station)
    assert episode.current_severity == "WARNING" and episode.highest_severity == "EVACUATE"
    assert episode.latest_sequence_no == 2 and len(transitions(station)) == 2
    with SessionLocal() as db:
        assert len(db.scalars(select(Telemetry).where(Telemetry.station_id == station)).all()) == 2


def test_station_specific_thresholds_and_exact_boundaries(client, station):
    with SessionLocal() as db:
        configured = db.scalar(select(Station).where(Station.station_id == station))
        configured.threshold_advisory_cm, configured.threshold_warning_cm, configured.threshold_evacuate_cm = 10, 20, 30
        db.commit()
    for sequence, depth in enumerate([9.99, 10, 20, 30], 1):
        send(client, station, sequence, depth)
    assert [t.new_severity for t in transitions(station)] == ["ADVISORY", "WARNING", "EVACUATE"]
    with SessionLocal() as db:
        item = next(s for s in monitoring_snapshot(db, stale_after_seconds=30, history_limit=20).stations
                    if s.station_id == station)
        assert item.alert_tier == "EVACUATE"


@pytest.mark.parametrize("administrative_status", ["inactive", "maintenance"])
def test_administrative_status_does_not_rewrite_sensor_history(client, station, administrative_status):
    send(client, station, 1, 100)
    original = episodes(station)[0]
    with SessionLocal() as db:
        db.scalar(select(Station).where(Station.station_id == station)).status = administrative_status
        db.commit()
    send(client, station, 2, None)
    assert episodes(station)[0].current_severity == "EVACUATE"
    assert episodes(station)[0].last_transition_at == original.last_transition_at
    send(client, station, 3, 90)
    send(client, station, 4, 0)
    episode, = episodes(station)
    assert episode.status == "RESOLVED" and episode.highest_severity == "EVACUATE"
    assert [t.new_severity for t in transitions(station)] == ["EVACUATE", "WARNING", "NORMAL"]


def test_alert_failure_rolls_back_telemetry_station_and_episode(client, station, monkeypatch):
    real_process = telemetry_service.process_sensor_alert
    def fail_after_processing(*args):
        real_process(*args)
        args[0].flush()
        raise RuntimeError("simulated transaction failure")
    monkeypatch.setattr(telemetry_service, "process_sensor_alert", fail_after_processing)
    with SessionLocal() as db, pytest.raises(RuntimeError):
        ingest_telemetry(db, TelemetryCreate(**payload(station, 1, 100)))
    with SessionLocal() as db:
        assert db.scalar(select(Station).where(Station.station_id == station)).last_ping is None
        assert db.scalar(select(Telemetry.id).where(Telemetry.station_id == station)) is None
    assert not episodes(station) and not transitions(station)
    monkeypatch.setattr(telemetry_service, "process_sensor_alert", real_process)
    send(client, station, 1, 100)
    assert len(episodes(station)) == len(transitions(station)) == 1


@pytest.mark.parametrize("duplicate", [True, False])
def test_concurrent_ingestion_uses_one_episode(client, station, duplicate):
    start = Barrier(2)
    def ingest(sequence):
        with SessionLocal() as db:
            start.wait(timeout=10)
            try:
                ingest_telemetry(db, TelemetryCreate(**payload(station, sequence, 90)))
                return "stored"
            except DuplicateTelemetryError:
                return "duplicate"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(ingest, [1, 1 if duplicate else 2]))
    assert sorted(results) == (["duplicate", "stored"] if duplicate else ["stored", "stored"])
    assert len(episodes(station)) == len(transitions(station)) == 1
    with SessionLocal() as db:
        samples = db.scalars(select(Telemetry).where(Telemetry.station_id == station).order_by(Telemetry.id)).all()
        assert len(samples) == (1 if duplicate else 2)
        assert episodes(station)[0].latest_telemetry_id == samples[-1].id


def test_database_constraints_prevent_duplicate_active_episode_and_transition(client, station):
    send(client, station, 1, 90)
    episode = episodes(station)[0]
    transition = transitions(station)[0]
    send(client, station, 2, 95)
    with SessionLocal() as db:
        values = {c.name: getattr(episode, c.name) for c in Alert.__table__.columns if c.name != "id"}
        sample = db.scalar(select(Telemetry).where(Telemetry.station_id == station, Telemetry.sequence_no == 2))
        values.update(trigger_telemetry_id=sample.id, trigger_sequence_no=2)
        db.add(Alert(**values))
        with pytest.raises(IntegrityError, match="alerts.station_id"):
            db.commit()
        db.rollback()
        db.add(AlertTransition(**{c.name: getattr(transition, c.name) for c in AlertTransition.__table__.columns if c.name != "id"}))
        with pytest.raises(IntegrityError, match="alert_transitions.telemetry_id"):
            db.commit()
        db.rollback()


@pytest.mark.parametrize("role", ["admin", "officer"])
def test_staff_history_active_filters_detail_and_transitions(client, station, role):
    access = staff(client, role)
    for seq, depth in enumerate([90, 100, 0, 60], 1):
        send(client, station, seq, depth)
    history = client.get(f"/api/alerts?station_id={station}", headers=access)
    assert history.status_code == 200 and history.headers["cache-control"] == "no-store"
    assert history.json()["total"] == 2
    active, resolved = history.json()["items"]
    assert active["status"] == "ACTIVE" and resolved["status"] == "RESOLVED"
    assert resolved["current_severity"] == "NORMAL" and resolved["highest_severity"] == "EVACUATE"
    for field in ["triggered_at", "last_transition_at", "resolved_at"]:
        assert resolved[field].endswith("Z")
    assert client.get(f"/api/alerts/active?station_id={station}", headers=access).json()["items"] == [active]
    assert client.get(f"/api/alerts?station_id={station}&status=RESOLVED&severity=NORMAL", headers=access).json()["items"] == [resolved]
    assert client.get(f"/api/alerts?station_id={station}&limit=1&offset=1", headers=access).json() == {"items": [resolved], "total": 2}
    assert client.get("/api/alerts?station_id=NONEXISTENT", headers=access).json() == {"items": [], "total": 0}
    assert client.get(f"/api/alerts/{resolved['id']}", headers=access).json() == resolved
    response = client.get(f"/api/alerts/{resolved['id']}/transitions?limit=1&offset=1", headers=access)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["total"] == 3
    transition, = response.json()["items"]
    assert transition["previous_severity"] == "WARNING" and transition["new_severity"] == "EVACUATE"
    assert transition["sequence_no"] == 2 and transition["water_depth_cm"] == 100
    assert transition["transitioned_at"].endswith("Z") and transition["telemetry_id"] > 0
    for url in ["/api/alerts/9999999", "/api/alerts/9999999/transitions"]:
        assert client.get(url, headers=access).status_code == 404
    for query in ["limit=0", "limit=101", "offset=-1", "status=UNKNOWN", "severity=UNKNOWN"]:
        assert client.get("/api/alerts?" + query, headers=access).status_code == 422
    assert client.post("/api/alerts", headers=access, json={}).status_code == 405
    assert client.patch(f"/api/alerts/{active['id']}", headers=access, json={}).status_code == 405


def test_all_alert_reads_require_active_staff_account(client, station):
    send(client, station, 1, 90)
    episode = episodes(station)[0]
    resident = headers(client.post("/api/auth/register", json=account()))
    officer = staff(client, "officer")
    urls = ["/api/alerts", "/api/alerts/active", f"/api/alerts/{episode.id}", f"/api/alerts/{episode.id}/transitions"]
    for url in urls:
        assert client.get(url).status_code == 401
        assert client.get(url, headers={"Authorization": "Bearer invalid-test-token"}).status_code == 401
        assert client.get(url, headers=resident).status_code == 403
    with SessionLocal() as db:
        db.scalar(select(User).where(User.role == "officer")).is_active = False
        db.commit()
    for url in urls:
        assert client.get(url, headers=officer).status_code == 401


def test_unknown_station_preserves_http_behavior(client):
    response = client.post("/api/telemetry", json=payload("MISSING_ALERT_STATION", 1, 100))
    assert response.status_code == 404
    assert not episodes("MISSING_ALERT_STATION")


def test_mqtt_callback_and_http_share_episode_and_duplicate_handling(client, station, monkeypatch):
    # Fake the broker client only. Invoke the actual subscriber callback/service.
    from app.config import Settings
    from app.services.mqtt_subscriber import start_mqtt_subscriber
    class FakeMqttClient:
        def __init__(self, *args, **kwargs): pass
        def connect_async(self, *args, **kwargs): pass
        def loop_start(self): pass
    mqtt = SimpleNamespace(Client=FakeMqttClient, CallbackAPIVersion=SimpleNamespace(VERSION2=2))
    monkeypatch.setitem(sys.modules, "paho", SimpleNamespace(mqtt=SimpleNamespace(client=mqtt)))
    monkeypatch.setitem(sys.modules, "paho.mqtt", SimpleNamespace(client=mqtt))
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", mqtt)
    subscriber = start_mqtt_subscriber(Settings(mqtt_username="", mqtt_password="", mqtt_tls=False))
    def deliver(sequence, depth):
        message = SimpleNamespace(topic=f"agapay/stations/{station}/telemetry",
                                  payload=json.dumps(payload(station, sequence, depth)).encode())
        subscriber.on_message(subscriber, None, message)
    deliver(1, 85)
    deliver(1, 85)
    deliver(2, None)
    send(client, station, 3, 100)
    deliver(4, 0)
    assert len(episodes(station)) == 1 and episodes(station)[0].status == "RESOLVED"
    assert [t.new_severity for t in transitions(station)] == ["WARNING", "EVACUATE", "NORMAL"]


def test_concurrent_severity_changes_retain_peak_and_serialized_order(client, station):
    send(client, station, 1, 60)
    start = Barrier(2)
    def ingest(reading):
        sequence, depth = reading
        with SessionLocal() as db:
            start.wait(timeout=10)
            ingest_telemetry(db, TelemetryCreate(**payload(station, sequence, depth)))
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(ingest, [(2, 90), (3, 105)]))
    with SessionLocal() as db:
        readings = db.scalars(select(Telemetry).where(Telemetry.station_id == station).order_by(Telemetry.id)).all()
    episode, = episodes(station)
    history = transitions(station)
    assert episode.highest_severity == "EVACUATE"
    assert episode.latest_telemetry_id == readings[-1].id
    assert episode.current_severity == ("WARNING" if readings[-1].water_depth_cm == 90 else "EVACUATE")
    assert [t.telemetry_id for t in history] == [t.id for t in readings]
    assert all(before.new_severity == after.previous_severity for before, after in zip(history, history[1:]))


def test_existing_episode_transition_and_station_update_roll_back_together(client, station, monkeypatch):
    from app.alert_schemas import AlertRead
    send(client, station, 1, 85)
    before = AlertRead.model_validate(episodes(station)[0]).model_dump()
    with SessionLocal() as db:
        ping_before = db.scalar(select(Station).where(Station.station_id == station)).last_ping
    real_process = telemetry_service.process_sensor_alert
    def fail_after_processing(*args):
        real_process(*args)
        args[0].flush()
        raise RuntimeError("simulated failure after transition insert")
    monkeypatch.setattr(telemetry_service, "process_sensor_alert", fail_after_processing)
    with SessionLocal() as db, pytest.raises(RuntimeError):
        ingest_telemetry(db, TelemetryCreate(**payload(station, 2, 100)))
    assert AlertRead.model_validate(episodes(station)[0]).model_dump() == before
    assert len(transitions(station)) == 1
    with SessionLocal() as db:
        assert db.scalar(select(Station).where(Station.station_id == station)).last_ping == ping_before
        assert db.scalar(select(Telemetry.id).where(Telemetry.station_id == station, Telemetry.sequence_no == 2)) is None
