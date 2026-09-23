# Physical firmware validation

## Reproduce

From the repository root, build the ESP32 target:

```powershell
python -m platformio run -d agapay-firmware
```

The build requires the ignored `include/secrets.h`; a copy of the placeholder template is sufficient for compilation only. Never use the test fakes to build/upload a board image.

Host tests compile **the actual `src/main.cpp`** against GPIO, clock, Preferences, queue, Wi-Fi and MQTT fakes; serialization uses real ArduinoJson. Install a C++17 compiler (or `python -m pip install ziglang`) and `jsonschema` in the Python environment containing backend dependencies. Then:

```powershell
& agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Python314/python.exe -m ziglang c++'
# Alternatively use --cxx 'clang++' or --cxx 'g++'. Set the Python path to your compiler installation.
# If PlatformIO dependencies are not yet installed, --arduinojson can point to an existing ArduinoJson src directory.
```

Generated payloads, test executable, mock forwarding headers and compiler diagnostics stay under ignored `agapay-firmware/.pio/host-tests/`. No real credentials or network traffic are used by host tests.

Run existing backend regressions from `agapay-backend`:

```powershell
& .venv/Scripts/python.exe -m pytest tests/test_api.py tests/test_monitoring.py -q
```

## Coverage and limits

- Timeout, too-close/too-far echo, median-of-five with at least three valid inputs (including four-input upper median), and insufficient readings.
- Distance-to-depth conversion, genuine zero depth, negative/nonfinite/out-of-range rejection.
- All threshold boundaries, active-low buzzer, offline LED operation, invalid-sensor retention of EVACUATE, and UNKNOWN at boot.
- One-second sampling, spaced pings, 32-bit clock rollover, 50 ms debounce, first tip, counter reset, zero/one/two tips, and a tip injected immediately after snapshot unlock.
- Ordinary reboot IDs, sequential IDs above 32 bits, block exhaustion, NVS open/write failure, and boot-counter exhaustion.
- Actual main-loop reporting windows, latest-only queue replacement, rejected impossible rain totals, and offline/stale/failed send behavior.
- Six firmware-generated JSON packets (valid/invalid sensor crossed with zero/one/two tips) validated against `docs/mqtt-telemetry.schema.json` and **the existing** FastAPI `TelemetryCreate`. The historical raw-distance extra field is rejected by both contracts.

Host fakes verify logic and contract behavior, not electrical timing, actual ISR concurrency, physical NVS persistence, network task scheduling, or MQTT delivery. A firmware build establishes compile/link compatibility only. No board upload or physical sensor/LED/buzzer test has been performed in this task. Complete the README calibration/acceptance steps before claiming hardware verification.

## Results recorded 2026-09-23

- **PlatformIO compile/link: PASS**, DOIT ESP32 DEVKIT V1, Espressif32 7.1.3, Arduino ESP32 framework 4.20017.260907, ArduinoJson 7.4.3, PubSubClient 2.8.0. RAM 45,440 / 327,680 bytes (13.9%); flash 761,317 / 1,310,720 bytes (58.1%). Build used ignored placeholder-only credentials. The source timestamp was checked against the compiled object after the final source edit.
- **Host firmware logic: PASS**, including interval-range rejection and delivery gating. Built with Zig C++ and ArduinoJson 7.4.3; six generated JSON packets passed both existing contracts.
- **Backend regression: 8 passed**, `tests/test_api.py` and `tests/test_monitoring.py`. One existing FastAPI/Starlette TestClient dependency deprecation warning.
- **Git whitespace check: PASS**. Local `secrets.h` is ignored and untracked; `secrets.example.h` remains tracked. See `security-review.md` for the historical credential exposure.
- **Physical validation: NOT PERFORMED.** No board was flashed; no physical sensor measurements, actual network-outage timing, or live MQTT-to-FastAPI delivery were claimed.
