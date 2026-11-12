from station_support import device_headers, ordering_fields


def valid_payload(sequence_no: int = 1000001) -> dict:
    return {
        **ordering_fields("STATION_001", sequence_no),
        "station_id": "STATION_001",
        "sequence_no": sequence_no,
        "water_depth_cm": 42.7,
        "rainfall_mm": 0.7,
        "sensor_quality": "valid",
        "device_uptime_ms": sequence_no,
        "firmware_version": "0.1.0",
    }


def test_health_and_seed_station(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "connected"}

    stations = client.get("/api/stations")
    assert stations.status_code == 200
    assert any(item["station_id"] == "STATION_001" for item in stations.json())


def test_store_latest_and_deduplicate(client):
    payload = valid_payload()
    access = device_headers("STATION_001")
    created = client.post("/api/telemetry", json=payload, headers=access)
    assert created.status_code == 201
    assert created.json()["sequence_no"] == payload["sequence_no"]

    duplicate = client.post("/api/telemetry", json=payload, headers=access)
    assert duplicate.status_code == 409

    latest = client.get("/api/telemetry/STATION_001/latest")
    assert latest.status_code == 200
    assert latest.json()["water_depth_cm"] == 42.7
    assert latest.json()["recorded_at"].endswith("Z")


def test_reject_invalid_quality_pair_and_unvalidated_battery(client):
    invalid_pair = valid_payload(sequence_no=1000002)
    invalid_pair["sensor_quality"] = "invalid"
    response = client.post("/api/telemetry", json=invalid_pair, headers=device_headers("STATION_001"))
    assert response.status_code == 422

    with_battery = valid_payload(sequence_no=1000003)
    with_battery["battery_pct"] = 75
    response = client.post("/api/telemetry", json=with_battery, headers=device_headers("STATION_001"))
    assert response.status_code == 422


def test_accept_invalid_sensor_with_null_depth(client):
    payload = valid_payload(sequence_no=1000004)
    payload["sensor_quality"] = "invalid"
    payload["water_depth_cm"] = None
    response = client.post("/api/telemetry", json=payload, headers=device_headers("STATION_001"))
    assert response.status_code == 201
    assert response.json()["water_depth_cm"] is None
