"""F03/F04: operational state follows measurement order across transports/boots."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, inspect, select

from app.database import SessionLocal
from app.models import (Alert, AlertTransition, NotificationEvent, Station, StationTelemetryState,
                        Telemetry, TelemetryBoot, utc_now)
from app.migrate_telemetry_ordering import migrate, require_ordering_schema
from app.services.monitoring_service import monitoring_snapshot
from app.services.telemetry_service import latest_telemetry
from station_support import ingest_authenticated as ingest_telemetry
from app.schemas import TelemetryCreate
from test_accounts import reset_accounts
from test_alerts import payload
from test_station_security import device, mqtt_transport, deliver, token_headers


def send(client, device, reading):
    return client.post("/api/telemetry", headers=token_headers(device[2]), json=reading)


def snapshot(station_id):
    with SessionLocal() as db:
        state = db.get(StationTelemetryState, station_id)
        station = db.scalar(select(Station).where(Station.station_id == station_id))
        alert = db.scalar(select(Alert).where(Alert.station_id == station_id).order_by(Alert.id.desc()))
        return (station.last_ping, station.firmware_version, state.latest_telemetry_id if state else None,
                (alert.status, alert.current_severity, alert.latest_telemetry_id, alert.last_transition_at) if alert else None,
                db.scalar(select(func.count()).select_from(AlertTransition).where(AlertTransition.station_id == station_id)),
                db.scalar(select(func.count()).select_from(NotificationEvent)))


def test_original_1001_then_1000_probe_keeps_evacuation_and_current_depth(client, device):
    station_id = device[0]
    high, late = payload(station_id, 1001, 105), payload(station_id, 1000, 1)
    assert send(client, device, high).json()["eligible_for_current"] is True
    before = snapshot(station_id)
    stored = send(client, device, late)
    assert stored.status_code == 201
    assert stored.json()["eligible_for_current"] is False
    assert stored.json()["disposition"] == "late_measurement"
    assert snapshot(station_id) == before
    latest = client.get(f"/api/telemetry/{station_id}/latest").json()
    assert latest["sequence_no"] == 1001 and latest["water_depth_cm"] == 105
    with SessionLocal() as db:
        monitored = next(s for s in monitoring_snapshot(db, stale_after_seconds=30, history_limit=20, station_ids=[device[0]]).stations
                         if s.station_id == station_id)
        assert monitored.current_depth_cm == 105 and monitored.alert_tier == "EVACUATE"
        assert [s.sequence_no for s in monitored.history] == [1001]
    assert len(client.get(f"/api/telemetry/{station_id}").json()) == 2


@pytest.mark.parametrize("changes,reason", [
    ({"device_uptime_ms": 0}, "out_of_order"),
    ({"sequence_no": 1}, "out_of_order"),
    ({"measured_at": None}, "unsynchronized"),
    ({"measured_at": "2000-01-01T00:00:00Z"}, "stale_measurement"),
])
def test_historical_samples_cannot_update_heartbeat_firmware_alert_or_outbox(client, device, changes, reason):
    station_id = device[0]
    assert send(client, device, payload(station_id, 2, 105)).status_code == 201
    before = snapshot(station_id)
    reading = {**payload(station_id, 3, 0), "firmware_version": "9.9.9", **changes}
    response = send(client, device, reading)
    assert response.status_code == 201 and response.json()["disposition"] == reason
    assert snapshot(station_id) == before


def test_exact_duplicate_and_conflicting_content_are_distinct_and_immutable(client, device):
    reading = payload(device[0], 1, 105)
    original = send(client, device, reading).json()
    before = snapshot(device[0])
    exact = send(client, device, reading)
    conflict = send(client, device, {**reading, "water_depth_cm": 1})
    metadata_conflict = send(client, device, {**reading, "firmware_version": "1.0.0"})
    assert exact.status_code == conflict.status_code == metadata_conflict.status_code == 409
    assert "exact retry" in exact.text and "Conflicting" in conflict.text + metadata_conflict.text
    assert snapshot(device[0]) == before
    assert client.get(f"/api/telemetry/{device[0]}/latest").json() == original


def test_reboot_allows_sequence_reset_but_never_reactivates_previous_boot(client, device):
    station_id = device[0]
    assert send(client, device, payload(station_id, 1001, 105)).status_code == 201
    old = payload(station_id, 1002, 1)
    reboot = {**payload(station_id, 1003, 90), "sequence_no": 1, "device_uptime_ms": 100,
              "boot_id": "TEST_BOOT_002", "boot_sequence": 2}
    assert send(client, device, reboot).json()["eligible_for_current"] is True
    before = snapshot(station_id)
    # Even a later UTC timestamp cannot reactivate an old boot's delayed traffic.
    old["measured_at"] = (utc_now() - timedelta(seconds=1)).isoformat()
    assert send(client, device, old).json()["disposition"] == "retired_boot"
    assert snapshot(station_id) == before
    assert client.get(f"/api/telemetry/{station_id}/latest").json()["boot_id"] == "TEST_BOOT_002"
    assert send(client, device, {**reboot, "boot_id": "COLLIDING_BOOT", "sequence_no": 2}).status_code == 409
    assert send(client, device, {**reboot, "boot_sequence": 3, "sequence_no": 2}).status_code == 409


def test_first_unsynchronized_or_stale_sample_is_history_without_live_or_alert(client, device):
    station_id = device[0]
    for sequence, measured in [(1, None), (2, "2000-01-01T00:00:00Z")]:
        response = send(client, device, {**payload(station_id, sequence, 105), "measured_at": measured})
        assert response.status_code == 201 and not response.json()["eligible_for_current"]
    assert snapshot(station_id)[:4] == (None, None, None, None)
    assert client.get(f"/api/telemetry/{station_id}/latest").status_code == 404


@pytest.mark.parametrize("historical_time", [None, "2000-01-01T00:00:00Z"])
def test_historical_high_water_mark_also_prevents_lower_sequence_becoming_current(client, device, historical_time):
    station_id = device[0]
    assert send(client, device, {**payload(station_id, 1001, 105), "measured_at": historical_time}).status_code == 201
    lower = {**payload(station_id, 1000, 1), "measured_at": (utc_now()-timedelta(seconds=1)).isoformat()}
    assert send(client, device, lower).json()["disposition"] == "out_of_order"
    assert snapshot(station_id)[:4] == (None, None, None, None)
    newer = {**payload(station_id, 1002, 105), "measured_at": utc_now().isoformat()}
    assert send(client, device, newer).json()["eligible_for_current"] is True


def test_reused_orm_session_refreshes_high_water_after_another_worker_commits(client, device):
    station_id = device[0]
    with SessionLocal() as db:
        ingest_telemetry(db, TelemetryCreate(**{**payload(station_id, 1001, 105), "measured_at": None}))
        cached = db.get(TelemetryBoot, (station_id, 1, "TEST_BOOT_001"))
        assert cached.highest_sequence == 1001
        assert send(client, device, {**payload(station_id, 1003, 105), "measured_at": None}).status_code == 201
        lower = TelemetryCreate(**{**payload(station_id, 1002, 1), "measured_at": utc_now().isoformat()})
        assert ingest_telemetry(db, lower).disposition == "out_of_order"
        assert cached.highest_sequence == 1003 and latest_telemetry(db, station_id) is None


def test_upgrade_floor_does_not_resolve_legacy_episode_with_pre_upgrade_measurement(client, device):
    station_id = device[0]
    assert send(client, device, payload(station_id, 1, 105)).status_code == 201
    with SessionLocal() as db:
        db.query(StationTelemetryState).filter_by(station_id=station_id).delete()
        db.commit()
    before = snapshot(station_id)
    reading = {**payload(station_id, 2, 1), "measured_at": (utc_now()-timedelta(seconds=20)).isoformat()}
    assert send(client, device, reading).json()["disposition"] == "pre_upgrade_measurement"
    assert snapshot(station_id) == before


@pytest.mark.parametrize("http_depth,mqtt_depth", [(105, 105), (105, 1)])
def test_concurrent_cross_transport_duplicate_or_conflict_only_has_one_winner(client, device, mqtt_transport, http_depth, mqtt_depth):
    station_id = device[0]
    start = Barrier(2)
    reading = payload(station_id, 1, http_depth)
    def http():
        start.wait(timeout=10)
        assert send(client, device, reading).status_code in (201, 409)
    def mqtt():
        start.wait(timeout=10)
        deliver(mqtt_transport[0], station_id, {"ingest_token": device[2]["ingest_token"],
                                               "telemetry": {**reading, "water_depth_cm": mqtt_depth}})
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(http), executor.submit(mqtt)]
        for future in futures:
            future.result(timeout=20)
    with SessionLocal() as db:
        rows = list(db.scalars(select(Telemetry).where(Telemetry.station_id == station_id)))
        assert len(rows) == 1
        assert latest_telemetry(db, station_id).id == rows[0].id
        alert = db.scalar(select(Alert).where(Alert.station_id == station_id))
        assert (alert.current_severity if alert else "NORMAL") == ("EVACUATE" if rows[0].water_depth_cm == 105 else "NORMAL")


@pytest.mark.parametrize("change", [
    {"schema_version": 1}, {"measured_at": "2026-01-01T12:00:00"},
    {"sequence_no": 9223372036854775808}, {"boot_sequence": 0},
    {"device_uptime_ms": 9223372036854775808}, {"water_depth_cm": float("inf")},
])
def test_invalid_ordering_contract_is_rejected(client, device, change):
    reading = {**payload(device[0], 1, 105), **change}
    if "water_depth_cm" in change:
        # Send explicit JSON infinity to test the server parser, not httpx encoding.
        import json
        result = client.post("/api/telemetry", headers={**token_headers(device[2]), "Content-Type": "application/json"},
                             content=json.dumps(reading))
    else:
        result = send(client, device, reading)
    assert result.status_code == 422
    assert snapshot(device[0])[:4] == (None, None, None, None)


@pytest.mark.parametrize("change", [{"source_id": "OTHER_DEVICE"}, {"config_version": 99}])
def test_source_identity_and_configuration_are_bound_to_commissioning(client, device, change):
    assert send(client, device, {**payload(device[0], 1, 105), **change}).status_code == 403
    assert snapshot(device[0])[:4] == (None, None, None, None)


def test_future_clock_is_rejected_and_receipt_is_separate_from_measurement(client, device):
    reading = payload(device[0], 1, 105)
    assert send(client, device, {**reading, "measured_at": (utc_now()+timedelta(minutes=1)).isoformat()}).status_code == 422
    data = send(client, device, reading).json()
    assert data["recorded_at"] == data["measured_at"]
    assert data["received_at"] > data["measured_at"]


@pytest.mark.parametrize("iteration", range(6))
def test_concurrent_http_mqtt_low_sequence_cannot_win_over_high(client, device, mqtt_transport, iteration):
    station_id = device[0]
    sub = mqtt_transport[0]
    start = Barrier(2)
    high, low = payload(station_id, 1001, 105), payload(station_id, 1000, 1)
    def http():
        start.wait(timeout=10)
        response = send(client, device, high if iteration % 2 else low)
        assert response.status_code == 201
    def mqtt():
        start.wait(timeout=10)
        deliver(sub, station_id, {"ingest_token": device[2]["ingest_token"],
                                  "telemetry": low if iteration % 2 else high})
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(http), executor.submit(mqtt)]
        for future in futures:
            future.result(timeout=20)
    assert client.get(f"/api/telemetry/{station_id}/latest").json()["sequence_no"] == 1001
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Telemetry).where(Telemetry.station_id == station_id)) == 2
        alert = db.scalar(select(Alert).where(Alert.station_id == station_id))
        assert alert.current_severity == "EVACUATE" and alert.status == "ACTIVE"


def test_retained_first_subscription_and_reconnect_cannot_touch_operational_state(client, device, mqtt_transport):
    station_id, _, issued = device
    sub = mqtt_transport[0]
    retained = {"ingest_token": issued["ingest_token"], "telemetry": payload(station_id, 1, 105)}
    sub.on_connect(sub, None, None, 0, None)
    before = snapshot(station_id)
    deliver(sub, station_id, retained, retain=True)
    assert snapshot(station_id) == before
    with SessionLocal() as db:
        assert db.scalar(select(TelemetryBoot).where(TelemetryBoot.station_id == station_id)) is None
    assert send(client, device, payload(station_id, 2, 105)).status_code == 201
    with SessionLocal() as db:
        station = db.scalar(select(Station).where(Station.station_id == station_id))
        station.last_ping = utc_now() - timedelta(minutes=5)
        db.scalar(select(Telemetry).where(Telemetry.station_id == station_id)).received_at = utc_now() - timedelta(minutes=5)
        db.commit()
    before = snapshot(station_id)
    sub.on_connect(sub, None, None, 0, None)  # resubscription on reconnect
    retained["telemetry"] = payload(station_id, 3, 1)  # unseen sequence, fresh-looking clock
    deliver(sub, station_id, retained, retain=True)
    assert snapshot(station_id) == before
    with SessionLocal() as db:
        station = next(s for s in monitoring_snapshot(db, stale_after_seconds=30, history_limit=20, station_ids=[device[0]]).stations
                       if s.station_id == station_id)
        assert station.connection_status == "offline" and station.alert_tier == "EVACUATE"
        assert len(station.history) == 1


def legacy_database(path):
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as c:
        c.exec_driver_sql("CREATE TABLE stations (station_id VARCHAR(50) PRIMARY KEY, last_ping DATETIME)")
        c.exec_driver_sql("INSERT INTO stations VALUES ('MIGRATION_TEST', '2026-01-01 00:00:00')")
        c.exec_driver_sql("CREATE TABLE telemetry (id INTEGER PRIMARY KEY, station_id VARCHAR(50) REFERENCES stations(station_id), "
                         "sequence_no BIGINT NOT NULL, water_depth_cm FLOAT, rainfall_mm FLOAT NOT NULL, sensor_quality VARCHAR(20) NOT NULL, "
                         "device_uptime_ms BIGINT NOT NULL, recorded_at DATETIME NOT NULL, "
                         "CONSTRAINT uq_telemetry_station_sequence UNIQUE(station_id, sequence_no))")
        c.exec_driver_sql("INSERT INTO telemetry VALUES (42,'MIGRATION_TEST',1001,105,0,'valid',1234,'2026-01-01 00:00:00')")
        c.exec_driver_sql("CREATE TABLE preserved_alerts (id INTEGER PRIMARY KEY, sample_id INTEGER REFERENCES telemetry(id), meaning TEXT)")
        c.exec_driver_sql("INSERT INTO preserved_alerts VALUES (7,42,'EVACUATE')")
        c.exec_driver_sql("CREATE TABLE preserved_outbox (id INTEGER PRIMARY KEY, alert_id INTEGER REFERENCES preserved_alerts(id))")
        c.exec_driver_sql("INSERT INTO preserved_outbox VALUES (8,7)")
    return engine


def test_migration_preserves_ids_references_legacy_time_and_data_and_is_idempotent(tmp_path):
    engine = legacy_database(tmp_path / "legacy.db")
    with pytest.raises(RuntimeError):
        require_ordering_schema(engine)
    assert migrate(engine)[0] is True
    assert "measured_at" not in {c["name"] for c in inspect(engine).get_columns("telemetry")}
    assert migrate(engine, apply=True)[0] is True
    require_ordering_schema(engine)
    assert migrate(engine, apply=True) == (False, [])
    with engine.begin() as c:
        assert c.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert c.exec_driver_sql("SELECT id, water_depth_cm, recorded_at, received_at, measured_at, disposition, eligible_for_current FROM telemetry").one() == (
            42, 105, "2026-01-01 00:00:00", "2026-01-01 00:00:00", None, "legacy", 0)
        assert c.exec_driver_sql("SELECT * FROM preserved_alerts").one() == (7, 42, "EVACUATE")
        assert c.exec_driver_sql("SELECT * FROM preserved_outbox").one() == (8, 7)
        assert c.exec_driver_sql("SELECT last_ping FROM stations").scalar() == "2026-01-01 00:00:00"
        # Distinct boots can now safely reuse a sequence without deleting history.
        c.exec_driver_sql("INSERT INTO telemetry (id, station_id, sequence_no, boot_id, water_depth_cm, rainfall_mm, sensor_quality, device_uptime_ms, recorded_at, received_at) "
                         "VALUES (43,'MIGRATION_TEST',1001,'BOOT_TWO',1,0,'valid',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
    engine.dispose()


def test_migration_refuses_custom_schema_without_partial_changes(tmp_path):
    engine = legacy_database(tmp_path / "custom.db")
    with engine.begin() as c:
        c.exec_driver_sql("CREATE INDEX custom_depth ON telemetry(water_depth_cm)")
    with pytest.raises(ValueError, match="Custom"):
        migrate(engine, apply=True)
    with engine.connect() as c:
        assert c.exec_driver_sql("SELECT id, water_depth_cm FROM telemetry").one() == (42, 105)
        assert c.exec_driver_sql("SELECT COUNT(*) FROM preserved_alerts").scalar() == 1
    assert "measured_at" not in {c["name"] for c in inspect(engine).get_columns("telemetry")}
    assert not inspect(engine).has_table("telemetry_ordering_upgrade")
    engine.dispose()
