F28: [bounded durable depth history and application ACK rollout](../agapay-docs/security/F28-F29/README.md). Requires an already provisioned LittleFS partition; no auto-format or flash.

# AGAPAY Firmware

F15/F16 add explicit rainfall products and reviewed installation hashes. Firmware fallback geometry is an unvalidated 150 cm bench profile; it is not a drop-in update for a 120 cm mounting. See [contracts, preservation migration, header export and physical acceptance](../agapay-docs/security/F15-F16/README.md).

`agapay-firmware/src/main.cpp` is the **canonical integrated ESP32 firmware**.
It reads physical JSN-SR04T and tipping-bucket sensors; it no longer generates simulated telemetry.
The Arduino sketches under `examples/` and `../sketch_sep19a/` are historical bring-up/bench references, not the official backend publisher.

The water publisher uses the v2 boot/acquisition contract. Configure the exact
commissioned device ID and configuration version alongside the station token;
see [F03/F04 installation and migration](../agapay-docs/security/F03-F04/README.md).
Before UTC synchronization, water messages are historical and cannot restore LIVE.

The backend also requires a reviewed source class and stream. Follow
[F05/F06 source review](../agapay-docs/security/F05-F06/README.md) before activating
an existing station; a firmware-version string cannot establish physical provenance.

## Wiring

| Component | ESP32 pin |
|---|---:|
| JSN-SR04T TRIG | GPIO 5 |
| JSN-SR04T ECHO | GPIO 18 through verified voltage protection |
| Rain gauge | GPIO 4, `INPUT_PULLUP`, FALLING interrupt |
| Active-low buzzer driver | GPIO 25 (LOW on, HIGH off) |
| Green / yellow / red LED | GPIO 26 / 27 / 14 |

Disconnect sensors for the historical Blink/library-only checks. Verify echo voltage protection before physical integration testing.

## Configure and build

Copy `include/secrets.example.h` to `include/secrets.h` only if absent, then configure Wi-Fi and MQTT locally. Also configure a commissioned station token in ignored `include/ingest_secrets.h` using `ingest_secrets.example.h`. See [station authentication and rollout](../agapay-docs/security/F01-F02/README.md). These files are ignored; never commit or print their real values. Missing ingestion configuration withholds network publication while local sensing continues. Do not copy passwords back into the historical sketch.

```powershell
if (-not (Test-Path include/secrets.h)) { Copy-Item include/secrets.example.h include/secrets.h }
if (-not (Test-Path include/ingest_secrets.h)) { Copy-Item include/ingest_secrets.example.h include/ingest_secrets.h }
python -m platformio run
# Only when the correct physical board/port is connected:
python -m platformio run --target upload
python -m platformio device monitor --baud 115200
```

Run these commands from `agapay-firmware`. Placeholder-only configuration permits compilation but does not authorize ingestion. Existing local credential files are preserved. The current firmware uses **plaintext `WiFiClient`, without TLS**; adding authentication does not encrypt transport. Use controlled private development infrastructure; authenticated, certificate-verified device TLS remains deployment work. Public anonymous MQTT is not supported by the updated ingestion path.

## Acquisition and local decisions

1. Approximately once per second, start five ultrasonic probes, spaced at least 60 ms apart using `millis()`. Each `pulseIn()` is bounded to 30 ms. Only the 2/10 microsecond trigger pulses and a 1 ms task yield use delays.
2. Exclude timeouts and distances outside the development 20–450 cm usable range. Require at least three valid probes, sort them, and take the middle item (upper median for four), preserving the bench sketch's filtering rule.
3. Compute `water_depth_cm = SENSOR_HEIGHT_CM - measured_distance_cm`. Reject negative, nonfinite, or otherwise impossible depth instead of converting it to zero. Raw median distance is logged to Serial, never added to the MQTT payload.
4. Classify valid **depth** using provisional 60/85/100 cm advisory/warning/evacuate thresholds. NORMAL lights green; ADVISORY and WARNING light yellow; EVACUATE lights red and activates the LOW-triggered buzzer.
5. Invalid samples publish `water_depth_cm: null`, `sensor_quality: "invalid"`, and retain the previous valid local alert outputs. Startup is UNKNOWN (all LEDs off, buzzer off) until the first valid measurement; sensor failure does not manufacture NORMAL. A previously valid NORMAL remains NORMAL on failure; there is no separate hardware fault indicator yet.

Sensor acquisition and GPIO decisions stay on the Arduino task. A separate ESP32 FreeRTOS task exclusively owns Wi-Fi/PubSubClient. Retry schedules use `millis()`; synchronous DNS/TCP/MQTT calls can wait on the network task without blocking local sensing. Network-task creation failure disables telemetry but keeps local operation running.

## Rainfall and telemetry

GPIO 4 counts debounced falling edges (50 ms) using an ISR-safe ESP32 critical section. Every 10 seconds, the main task atomically copies **and resets** the count. A concurrent tip belongs to exactly one reporting window. `rainfall_mm = interval_tips * RAIN_MM_PER_TIP`; zero tips produce zero, one tip 0.70 mm, two tips 1.40 mm. This is never lifetime rainfall. A nonfinite/negative interval or one above the schema limit of 1000 mm is rejected with a diagnostic, rather than clamped or transmitted.

The live report contains the most recently completed ultrasonic sample and original acquisition time. Its one-slot network queue still replaces unsent live reports and drops stale reports after two seconds; QoS 0 socket success is not a database receipt. Separately, a 10-second depth journal retains up to 360 unacknowledged immutable observations in provisioned LittleFS and replays them strictly as historical data until an application ACK follows commit. History unavailability, capacity evictions, corrupt/write-failed records and handoff gaps are reported explicitly. The independent rain journal retains cumulative tips using its existing NVS/ACK contract; water replay never manufactures rainfall intervals. See the F28 guide for exact limits and device acceptance.

Persistent Preferences key `agapay/boot_no` reserves one million sequence numbers per boot. A block is persisted before use; exhaustion reserves another block. NVS failure suppresses publication while local sensing continues. Ordinary restarts increase IDs; erasing NVS/reflashing with flash erase needs deliberate station sequence recovery. Gaps from dropped reports are expected.

Topic: `agapay/stations/STATION_001/telemetry` (generated from `STATION_ID`). Backend subscription: `agapay/stations/+/telemetry`. Register that station and enable/configure the backend MQTT subscriber against the same broker.

```json
{"station_id":"STATION_001","sequence_no":1000001,"water_depth_cm":42.7,"rainfall_mm":0.7,"sensor_quality":"valid","device_uptime_ms":10000,"firmware_version":"0.2.0"}
```

See [contract](docs/mqtt-telemetry.md) and [JSON Schema](docs/mqtt-telemetry.schema.json). No battery, raw distance, cumulative rain, or bench tier fields are transmitted.

## Calibration and physical acceptance still required

- Measure `SENSOR_HEIGHT_CM` from the installed transducer to the chosen zero-depth datum. **120 cm is an uncalibrated development assumption.** Keep backend station metadata consistent.
- Validate the actual sensor's usable range, blind zone, echo timing, surface/angle effects, and repeatability. The sketch's 20–450 cm limits are provisional. At 120 cm height the 20 cm blind-zone boundary allows at most 100 cm measured depth: EVACUATE lies at that boundary and may not be reliably reachable given echo resolution. Validate mounting/range/thresholds together before deployment. An object inside the blind zone yields INVALID and holds the last tier; it cannot establish a new higher tier.
- Verify the delivered gauge's `RAIN_MM_PER_TIP` using a measured water volume and catchment area. **0.70 mm/tip is provisional**, not physically confirmed here. Check debounce against real contact bounce and tip rate.
- Agree site depth thresholds with the project stakeholders, then update firmware and backend station settings together. No remote threshold synchronization exists. Firmware deliberately retains backend defaults 60/85/100 cm, rather than the historical sketch's 60/35/25 cm distance tiers (which would imply 60/85/95 cm depth at 120 cm mounting).
- Confirm LED wiring and LOW-triggered buzzer; force a high alert, disconnect Wi-Fi/broker, and disconnect ECHO to verify alert retention. Also test invalid-at-boot UNKNOWN behavior.
- Check actual serial JSON through a private broker into FastAPI; verify zero/one/two tips across reporting boundaries, boot sequence persistence, and prolonged network failures while local alerts keep responding.

## Validation

See [validation instructions and scope](docs/validation.md). Host tests exercise the actual `src/main.cpp` with mocked hardware/network/Preferences and real ArduinoJson serialization. They are not physical sensor or FreeRTOS concurrency certification.


Separate TLS release profile with protected configuration, verified CA/hostname and no demo-transport fallback: [F26-F27 implementation, rollout and verification](../agapay-docs/security/F26-F27/README.md). Field deployment acceptance remains pending.
