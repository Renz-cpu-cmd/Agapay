# AGAPAY Firmware

`agapay-firmware/src/main.cpp` is the **canonical integrated ESP32 firmware**.
It reads physical JSN-SR04T and tipping-bucket sensors; it no longer generates simulated telemetry.
The Arduino sketches under `examples/` and `../sketch_sep19a/` are historical bring-up/bench references, not the official backend publisher.

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

Copy `include/secrets.example.h` to `include/secrets.h`, then configure Wi-Fi and MQTT locally. `secrets.h` is ignored by Git; never commit it. The template contains placeholders only. Do not copy passwords back into the historical sketch.

```powershell
Copy-Item include/secrets.example.h include/secrets.h
python -m platformio run
# Only when the correct physical board/port is connected:
python -m platformio run --target upload
python -m platformio device monitor --baud 115200
```

Run these commands from `agapay-firmware`. A placeholder-only secrets file permits compilation but will not connect. Existing username/password configuration is preserved. The current firmware uses **plaintext `WiFiClient`, without TLS**; adding a username does not encrypt transport. Public anonymous MQTT is suitable only for development dummy data. Use controlled private bench infrastructure for physical readings; authenticated, certificate-verified TLS remains deployment work.

## Acquisition and local decisions

1. Approximately once per second, start five ultrasonic probes, spaced at least 60 ms apart using `millis()`. Each `pulseIn()` is bounded to 30 ms. Only the 2/10 microsecond trigger pulses and a 1 ms task yield use delays.
2. Exclude timeouts and distances outside the development 20–450 cm usable range. Require at least three valid probes, sort them, and take the middle item (upper median for four), preserving the bench sketch's filtering rule.
3. Compute `water_depth_cm = SENSOR_HEIGHT_CM - measured_distance_cm`. Reject negative, nonfinite, or otherwise impossible depth instead of converting it to zero. Raw median distance is logged to Serial, never added to the MQTT payload.
4. Classify valid **depth** using provisional 60/85/100 cm advisory/warning/evacuate thresholds. NORMAL lights green; ADVISORY and WARNING light yellow; EVACUATE lights red and activates the LOW-triggered buzzer.
5. Invalid samples publish `water_depth_cm: null`, `sensor_quality: "invalid"`, and retain the previous valid local alert outputs. Startup is UNKNOWN (all LEDs off, buzzer off) until the first valid measurement; sensor failure does not manufacture NORMAL. A previously valid NORMAL remains NORMAL on failure; there is no separate hardware fault indicator yet.

Sensor acquisition and GPIO decisions stay on the Arduino task. A separate ESP32 FreeRTOS task exclusively owns Wi-Fi/PubSubClient. Retry schedules use `millis()`; synchronous DNS/TCP/MQTT calls can wait on the network task without blocking local sensing. Network-task creation failure disables telemetry but keeps local operation running.

## Rainfall and telemetry

GPIO 4 counts debounced falling edges (50 ms) using an ISR-safe ESP32 critical section. Every 10 seconds, the main task atomically copies **and resets** the count. A concurrent tip belongs to exactly one reporting window. `rainfall_mm = interval_tips * RAIN_MM_PER_TIP`; zero tips produce zero, one tip 0.70 mm, two tips 1.40 mm. This is never lifetime rainfall. A nonfinite/negative interval or one above the schema limit of 1000 mm is rejected with a diagnostic, rather than clamped or transmitted.

The report contains the most recently completed ultrasonic sample and the reporting-boundary uptime. The one-slot task queue keeps the latest completed interval. If the network task is busy, an older unsent interval is replaced and logged; offline, stale (10 seconds old), or failed publications are logged and dropped. Outage rainfall is **not merged** into a later window. There is no durable offline replay; reboot also loses in-memory tips. QoS 0 success means socket submission, not backend storage. These limits preserve the existing best-effort prototype contract and must be considered in field testing.

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
