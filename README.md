# Agapay
A Mini-Capstone of App Development

## Automated quality gates

[AGAPAY CI](.github/workflows/ci.yml) runs all five jobs on pushes to `main` and
`feature/day1-foundation`, and pull requests targeting either branch. It can also
be run manually. Jobs use Python 3.12 (matching the backend Dockerfile), Node 24,
and stable Flutter 3.38.7 / Dart 3.10.7. No application credentials or external
database/MQTT services are required.

Run these checks locally from the indicated directory with the same tool versions:

| Job | Directory | Commands |
|---|---|---|
| Backend Tests | `agapay-backend` | `python -m pip install -r requirements-dev.txt`, then `python -m pytest -q` |
| ESP32 Firmware Build | Repository root | `python -m pip install "platformio==6.2.0"`, then `python -m platformio run --project-dir agapay-firmware --environment esp32doit-devkit-v1` |
| Firmware Contract Tests | Repository root | `python -m pip install -r agapay-backend/requirements.txt "jsonschema>=4,<5" "platformio==6.2.0"`, `python -m platformio pkg install --project-dir agapay-firmware --environment esp32doit-devkit-v1`, then `python agapay-firmware/tests/run_host_tests.py --cxx g++` |
| Next.js Build | `agapay-web` | `npm ci`, `npm run typecheck`, `npm run build` |
| Flutter Analyze & Test | `agapay-mobile` | `flutter pub get`, `flutter analyze`, `flutter test` |

Use a Python virtual environment. Before compiling firmware locally, copy
`agapay-firmware/include/secrets.example.h` to the ignored `secrets.h` **only if
the local file does not already exist**. CI copies the placeholder template in
its disposable checkout; it never receives real Wi-Fi/MQTT credentials or uploads
a board image. On Windows, use the compiler alternative documented in
[firmware validation](agapay-firmware/docs/validation.md).

Backend tests use their isolated SQLite database and fakes. The web build works
with an empty `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` and no running backend. Flutter
analysis/tests do not need the ignored Maps key file. Local `.env` / `.env.local`,
`secrets.h`, `.pio`, `.next`, and Flutter build outputs must stay untracked.

These gates validate software tests, types, static analysis, ESP32 compile/link
compatibility, and firmware-generated JSON against both the shared JSON Schema
and FastAPI `TelemetryCreate`. They do **not** validate physical sensors,
calibration, flood thresholds, wiring, ESP32 flashing, network delivery, real
Google Maps services, an emulator/device, or deployment readiness. Firmware host
tests use fakes and never replace the [physical acceptance checks](agapay-firmware/README.md).

The five job names identify failures in pull requests. Enforcing them as required
merge checks additionally needs a repository branch rule; this workflow does not
change branch protection.
