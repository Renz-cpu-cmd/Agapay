# F26–F27 verification results

Observed October 22, 2026. The source changes preserve existing staged work. No live database, broker listener, device credential, NVS or physical installation was changed. No firmware upload, deployment, commit or push occurred.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Complete backend regression | **535 passed**, 23 dependency deprecation warnings | [backend-full.log](backend-full.log) |
| Final TLS/configuration/ACL focused checks | **20 passed**, 2 dependency deprecation warnings | [transport-tests.log](transport-tests.log) |
| Mobile complete regression | **152 passed** | [mobile-full.log](mobile-full.log) |
| Flutter static analysis | **No issues found** | [mobile-analyze.log](mobile-analyze.log) |
| Flutter release web compilation | Passed; synthetic HTTPS origin only | [mobile-build.log](mobile-build.log) |
| Web unit/contract tests | **58 passed** | [web-tests.log](web-tests.log) |
| Next.js production webpack build | Passed; dynamic page rendering and request proxy included | [web-build.log](web-build.log) |
| Built production HTML/CSP | Passed; **11 scripts** including theme startup carry matching nonce; new request gets a new nonce; required headers and private/no-store verified | [csp-runtime.log](csp-runtime.log) |
| Development firmware host tests | Passed: actual firmware acquisition, GPIO, rain journal, offline queues, sequences and schemas against fakes | [firmware-host.log](firmware-host.log) |
| Release firmware host tests | Passed, including CA installation, handshake budget, no unsynchronized MQTT connection and disabled runtime distance demo | [firmware-release-host.log](firmware-release-host.log) |
| Negative release compile guards | Both expected rejections passed: bench profile and unprovisioned station | [firmware-negative-guards.log](firmware-negative-guards.log) |
| Actual ESP32 release toolchain | **Compiled successfully**, synthetic isolated headers/CA; 48,204 bytes static RAM and 944,605 bytes flash | [esp32-release-build.log](esp32-release-build.log) |
| Existing ESP32 development profiles | Both ordinary and cardboard builds succeeded | [esp32-development-builds.log](esp32-development-builds.log) |
| Derived audit backlog | All 40 findings retained; F26/F27 implementation and deployment-pending states recorded | [prioritized-backlog.csv](../../audits/2026-10-21/prioritized-backlog.csv) |

The backend full run included 20 new transport cases. The final focused run additionally verifies the small duplicate-identity guard and stricter production-ACL read/forgery assertions added after that full run. Database-backed tests were run serially against the disposable fixture, never against the live database. Test totals are separate suites; repeated runs must not be added together. Early development logs, including mobile fixture failures subsequently corrected, are superseded by the final logs above.

## What was established

- One shared mobile snapshot/selection and immutable channel views drive home, map, detail and forecast context. Invalid/retained depth differs from heartbeat connectivity and independent rainfall. Account-generation guards reject old results; overlapping refreshes do not create a second polling stream. Timer-driven marker expiry is exercised before any successful network refresh. Forecast selection follows the shared station.
- Release URL checks reject HTTP, emulator/loopback/local origins, credentials and ambiguous paths/queries. Mobile release compilation used the reserved `https://api.agapay.invalid` endpoint solely to verify compilation. It is not a deployed API and was not contacted.
- Python TLS contexts require hostname/certificate verification and TLS 1.2 minimum. An isolated Mosquitto listener with synthetic CA/server keys negotiated TLS 1.2 or 1.3 with at least 128-bit cipher strength. Wrong CA, wrong hostname and expired server certificate fail. Anonymous, wrong-password and revoked-old-password connections fail.
- Explicit production ACLs permit a device's own measurement publishes/acknowledgement reads and block cross-station, exercise and spoofed-ack operations. Backend-ingest cannot forge water telemetry. Cross-station acknowledgement reads are filtered. Password revocation is tested after disconnect/restart of that isolated listener, not by assuming password reload closes old sessions.
- Production configuration rejects plaintext broker ports, absent TLS/broker credentials, the development client ID and incomplete client-certificate/key pairs. Broker passwords are redacted in settings representations. ACL rendering rejects malformed IDs, simulator identities in operational scope and conflicting duplicate IDs.
- Firmware release profile compiles the real `WiFiClientSecure` code using the installed Arduino-ESP32 TLS implementation. Local SDK source was inspected for required certificate verification, hostname installation and verify-result rejection. Host adapters do not perform a physical ESP32 handshake; the separate real broker test exercises Python/Paho TLS. No physical-device TLS success is claimed.
- CSP is enforced with per-document random nonces, including framework/inline theme scripts. Client-supplied nonce/CSP is overwritten. Provider resource allowances, Maps-specific eval exception and security headers have contract tests. Built HTML is checked on a private ephemeral listener without cookies or form submission. No real Maps quota/API-key acceptance or full browser provider interaction was claimed.

## Commands

Run from the repository root unless a command first changes directory. These checks use synthetic fixtures; none flashes hardware or changes a running broker.

```powershell
# Backend: run serially; the pytest fixture owns a disposable database.
Set-Location agapay-backend
.venv-auth/Scripts/python.exe -u -m pytest -q --tb=short
Set-Location ..

# Actual firmware on host fakes and negative release guards.
agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Python314/python.exe -m ziglang c++'
agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Python314/python.exe -m ziglang c++' --release-profile
agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/check_release_guards.py
# Actual ESP32 compiler with isolated synthetic config; never upload this artifact.
agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/build_release_fixture.py
C:/Python314/python.exe -m platformio run --project-dir agapay-firmware --environment esp32doit-devkit-v1 --environment esp32-cardboard-demo

Set-Location agapay-web
node --test test/*.cjs test/*.mjs
npm run build -- --webpack
npm run check:csp
Set-Location ../agapay-mobile
C:/flutter/bin/flutter.bat analyze --no-pub
C:/flutter/bin/flutter.bat test --no-pub
# Reserved compile-only endpoint; replace through reviewed deployment configuration for real releases.
C:/flutter/bin/flutter.bat build web --no-pub --dart-define=AGAPAY_API_URL=https://api.agapay.invalid
Set-Location ..
```

The guarded production web launcher is `npm run start:production`, after explicit production environment and origin configuration. The existing local `start`/`dev` commands remain local workflows. Production service managers must use the guarded entry points and reviewed environment files, not silently inherit development defaults.

## Remaining deployment acceptance

Actual field broker configuration was not inspected or changed. Real DNS/SAN/CA validation, confidential traffic on the intended network, private-key/header/artifact access controls, connected-client revocation, CA rotation, firewall rules, native installed-device startup and outage behavior, real API-origin certificate validation and configured 2D/3D Maps/CSP behavior still need deployment evidence. Static RAM/flash sizes are compile output, not physical peak TLS heap or long-running device stability measurements. The original physical commissioning/calibration gates remain open.

All 48 previously staged paths remain staged, on branch `feature/day1-foundation` at HEAD `67f85e0`. No unrelated work was staged or reverted. An earlier automatic-approval usage failure prevented one test invocation from executing; after the user confirmed the issue was resolved, validation resumed normally. That failed invocation is not counted as test evidence.
