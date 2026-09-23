# MQTT Telemetry Contract v1

## Topic

- Device publishes to `agapay/stations/{station_id}/telemetry`.
- Backend subscribes to `agapay/stations/+/telemetry`.
- The topic station ID must exactly match `payload.station_id`.

## Delivery behavior

- PubSubClient publishes current prototype messages at QoS 0.
- Telemetry messages are not retained.
- A new reading is published every 10 seconds during development.
- The backend deduplicates using `(station_id, sequence_no)`.
- The ESP32 continues sensor acquisition and local alerts even when MQTT is unavailable.
- Public anonymous brokers are only for dummy development data. Deployment-style testing requires authentication and verified TLS; the current firmware uses plaintext WiFiClient and does not yet implement TLS.

## Fields

| Field | Type | Meaning |
|---|---|---|
| `station_id` | string | Registered station identifier, initially `STATION_001` |
| `sequence_no` | integer | Per-station message identifier used for deduplication |
| `water_depth_cm` | number or null | Absolute water depth in centimeters; null when the ultrasonic sample is invalid |
| `rainfall_mm` | number | Rain in the current 10-second reporting window; provisional calibration is 0.70 mm per tip (requires physical verification) |
| `sensor_quality` | `valid` or `invalid` | Whether the water-depth sample can be trusted |
| `device_uptime_ms` | integer | ESP32 uptime from `millis()` |
| `firmware_version` | string | Firmware semantic version; physical integration is `0.2.0` |

The backend supplies its own UTC `recorded_at` receive timestamp. `battery_pct` is prohibited until a battery measurement circuit is built and calibrated.

## Canonical physical firmware

`../src/main.cpp` computes water depth from mounting height minus median ultrasonic distance. The 120 cm height and 60/85/100 cm depth thresholds remain uncalibrated development settings. Invalid readings use null depth and retain the last valid local tier (UNKNOWN at startup).

Every 10 seconds an atomic rain counter snapshot/reset closes the window, regardless of connectivity. Offline/failed/stale intervals are dropped with a Serial diagnostic; the latest-only task queue can replace unsent intervals. Rain from those windows is not merged into subsequent reports. This is a best-effort QoS 0 stream, without durable replay or backend acknowledgements. The backend's receive timestamp is not an acquisition timestamp. The firmware records the interval boundary in `device_uptime_ms`.

The JSON Schema and FastAPI `TelemetryCreate` remain unchanged. Station registration, matching broker settings and enabled backend MQTT subscription are still required. Backend station calibration/threshold edits do not automatically update firmware constants.
