from datetime import timedelta

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Station, Telemetry, utc_now
from test_accounts import account, headers, reset_accounts


STATION = "MONITOR_TEST"


@pytest.fixture
def access(client):
    with SessionLocal() as db:
        db.query(Telemetry).filter(Telemetry.station_id == STATION).delete()
        station = db.scalar(select(Station).where(Station.station_id == STATION))
        if station is None:
            station = Station(
                station_id=STATION,
                station_name="Monitoring contract station",
                threshold_advisory_cm=60,
                threshold_warning_cm=85,
                threshold_evacuate_cm=100,
            )
            db.add(station)
        station.status = "active"
        station.last_ping = None
        station.firmware_version = None
        db.commit()
    return headers(client.post("/api/auth/register", json=account()))


def post(client, sequence, depth, quality="valid", rainfall=0.7):
    return client.post(
        "/api/telemetry",
        json={
            "station_id": STATION,
            "sequence_no": sequence,
            "water_depth_cm": depth,
            "rainfall_mm": rainfall,
            "sensor_quality": quality,
            "device_uptime_ms": sequence * 1000,
            "firmware_version": "0.2.0-simulator",
        },
    )


def monitored_station(client, access):
    response = client.get("/api/monitoring/stations?history_limit=20", headers=access)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return next(item for item in response.json()["stations"] if item["station_id"] == STATION)


def test_snapshot_requires_account_and_represents_no_data(client, access):
    assert client.get("/api/monitoring/stations").status_code == 401
    item = monitored_station(client, access)
    assert item["connection_status"] == "no_data"
    assert item["is_online"] is False
    assert item["alert_tier"] is None
    assert item["current_depth_cm"] is None
    assert item["source"] == "none"


def test_live_snapshot_classifies_thresholds_trend_and_history(client, access):
    assert post(client, 1, 58).status_code == 201
    assert post(client, 2, 64, rainfall=1.4).status_code == 201
    item = monitored_station(client, access)
    assert item["connection_status"] == "online"
    assert item["alert_tier"] == "ADVISORY"
    assert item["trend"] == "rising_rapidly"
    assert item["current_depth_cm"] == 64
    assert item["latest_rainfall_mm"] == 1.4
    assert item["source"] == "simulator"
    assert [sample["sequence_no"] for sample in item["history"]] == [1, 2]


def test_invalid_sample_preserves_last_valid_severity_without_claiming_a_value(client, access):
    assert post(client, 1, 88).status_code == 201
    assert post(client, 2, None, quality="invalid", rainfall=0).status_code == 201
    item = monitored_station(client, access)
    assert item["sensor_quality"] == "invalid"
    assert item["latest_depth_cm"] is None
    assert item["current_depth_cm"] == 88
    assert item["alert_tier"] == "WARNING"


def test_freshness_and_administrative_state_are_separate_from_severity(client, access):
    assert post(client, 1, 104).status_code == 201
    with SessionLocal() as db:
        saved = db.scalar(select(Station).where(Station.station_id == STATION))
        saved.last_ping = utc_now() - timedelta(minutes=5)
        db.commit()
    item = monitored_station(client, access)
    assert item["connection_status"] == "offline"
    assert item["is_stale"] is True
    assert item["alert_tier"] == "EVACUATE"

    with SessionLocal() as db:
        saved = db.scalar(select(Station).where(Station.station_id == STATION))
        saved.status = "maintenance"
        db.commit()
    item = monitored_station(client, access)
    assert item["connection_status"] == "maintenance"
    assert item["alert_tier"] == "EVACUATE"
