# MQTT Telemetry Contract v2

October 22 follow-up: firmware 0.3.0 uses the [F15/F16 v3 rainfall/configuration contract](../../agapay-docs/security/F15-F16/README.md). The current fallback is an explicitly unvalidated 150 cm bench geometry; historical 120 cm examples below remain archived context. No device was flashed or physically calibrated by this change.


See [F03/F04 ordering and rollout](../../agapay-docs/security/F03-F04/README.md) for required migration, metadata, and timestamp semantics. The example bodies are synthetic documentation, not live measurements. MQTT wraps each body in `{"ingest_token":"<station token>","telemetry":{...}}`.

## Topic

- Device publishes to `agapay/stations/{station_id}/telemetry`.
- Backend subscribes to `agapay/stations/+/telemetry`.
- The topic station ID must exactly match `payload.station_id`.

## Delivery behavior

- PubSubClient publishes current prototype messages at QoS 0.
- Telemetry messages are not retained.
- A report is published every 2 seconds during development.
- The backend deduplicates by station/configuration/boot/sequence, distinguishes conflicting retries, and atomically orders current state by boot ordinal, sequence, acquisition uptime and measured UTC.
- The ESP32 continues sensor acquisition and local alerts even when MQTT is unavailable.
- Public anonymous brokers are only for dummy development data. Deployment-style testing requires authentication and verified TLS; the current firmware uses plaintext WiFiClient and does not yet implement TLS.

## Fields

| Field | Type | Meaning |
|---|---|---|
| `station_id` | string | Registered station identifier, initially `STATION_001` |
| `sequence_no` | integer | Sequence within a durable boot/session |
| `water_depth_cm` | number or null | Absolute water depth in centimeters; null when the ultrasonic sample is invalid |
| `rainfall_mm` | number | Rain in the current 2-second reporting window; provisional calibration is 0.70 mm per tip (requires physical verification) |
| `sensor_quality` | `valid` or `invalid` | Whether the water-depth sample can be trusted |
| `device_uptime_ms` | integer | 64-bit `esp_timer_get_time()/1000` at acquisition |
| `firmware_version` | string | Firmware semantic version; physical integration is `0.2.0` |

Required v2 fields are `schema_version=2`, commissioned `config_version`/`source_id`, persisted `boot_sequence`, stable `boot_id`, and timezone-aware `measured_at` (null before clock synchronization). `received_at` is server receipt; `recorded_at` equals measurement time for synchronized v2 observations. Null/legacy timestamps are receipt-based historical compatibility fields and never current. `battery_pct` is prohibited until a battery measurement circuit is built and calibrated.

## Canonical physical firmware

`../src/main.cpp` computes water depth from mounting height minus median ultrasonic distance. The 120 cm height and 60/85/100 cm depth thresholds remain uncalibrated development settings. Invalid readings use null depth and retain the last valid local tier (UNKNOWN at startup).

Every 2 seconds an atomic rain counter snapshot/reset closes the window, regardless of connectivity. Offline/failed/stale intervals are dropped with a Serial diagnostic; the latest-only task queue can replace unsent intervals. Rain from those windows is not merged into subsequent reports. This is a best-effort QoS 0 stream, without durable replay or backend acknowledgements. The firmware preserves the sensor acquisition time/64-bit uptime in the queued report, separate from its publishing boundary. Unsynchronized samples are historical only. Retained water/rain is dropped before persistence, including reconnect deliveries.

The JSON Schema and FastAPI `TelemetryCreate` now require v2 metadata. Station registration, matching broker settings and enabled backend MQTT subscription are still required. Backend station calibration/threshold edits do not automatically update firmware constants.

## Durable depth replay (F28)

An optional envelope `delivery_mode` is `live` or `backfill`. Firmware journals a separate 10-second cadence, up to 360 unacknowledged observations; the two-second live stream is not a complete recoverable history. Backfill always preserves the original observation. ACK topic: `agapay/stations/<station>/telemetry-ack`, payload `{station_id, config_version, boot_id, sequence_no, persisted: true, telemetry: original_observation}`. ACK follows commit and exact duplicate validation. Only an ACK matching both the key and complete original observation removes a slot. Historical ingress never updates current state/alerts. See the F28/F29 guide for filesystem provisioning, gaps, resource limits and remaining device tests.
