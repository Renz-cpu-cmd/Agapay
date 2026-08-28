# AGAPAY Firmware

ESP32 firmware for the AGAPAY Community Flood & Disaster Early-Warning System.

## Confirmed pins

| AGAPAY component | ESP32 pin |
|---|---:|
| JSN-SR04T TRIG | GPIO 5 |
| JSN-SR04T ECHO | GPIO 18 through verified voltage protection |
| Hall-effect tipping-bucket rain gauge | GPIO 4 with `INPUT_PULLUP` |
| Buzzer driver input | GPIO 25 |
| Green LED | GPIO 26 |
| Yellow LED | GPIO 27 |
| Red LED | GPIO 14 |

Do not connect sensors or the buzzer during the Day-1 Blink and library checks.

## Arduino IDE tests

- `examples/01_blink/01_blink.ino` verifies board, cable, port, compilation, and upload.
- `examples/02_library_check/02_library_check.ino` verifies ArduinoJson and PubSubClient and prints the agreed telemetry JSON.

## PlatformIO scaffold

The official repository structure uses `src/main.cpp` and `platformio.ini`. Copy `include/secrets.example.h` to `include/secrets.h` and replace its placeholders before building the MQTT firmware. Never commit `include/secrets.h`.

The current scaffold uses simulated measurements so software integration can proceed before sensor wiring. Real sensor acquisition will replace `readSimulatedTelemetry()` during the hardware phase; local alert logic must remain independent of Wi-Fi and MQTT state.

## MQTT contract

- Publish topic: `agapay/stations/{station_id}/telemetry`
- Backend subscription: `agapay/stations/+/telemetry`
- Payload specification: `docs/mqtt-telemetry.md`
- Machine-readable JSON Schema: `docs/mqtt-telemetry.schema.json`
