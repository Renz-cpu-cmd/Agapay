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
- Public anonymous brokers are only for dummy development data. Deployment-style testing uses authentication and TLS.

## Fields

| Field | Type | Meaning |
|---|---|---|
| `station_id` | string | Registered station identifier, initially `STATION_001` |
| `sequence_no` | integer | Per-station message identifier used for deduplication |
| `water_depth_cm` | number or null | Absolute water depth in centimeters; null when the ultrasonic sample is invalid |
| `rainfall_mm` | number | Rain added since the previous publish; confirmed hardware increment is 0.70 mm per tip |
| `sensor_quality` | `valid` or `invalid` | Whether the water-depth sample can be trusted |
| `device_uptime_ms` | integer | ESP32 uptime from `millis()` |
| `firmware_version` | string | Firmware semantic version, starting at `0.1.0` |

The backend supplies its own UTC `recorded_at` receive timestamp. `battery_pct` is prohibited until a battery measurement circuit is built and calibrated.
