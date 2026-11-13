# F15/F16 verification — October 22, 2026

Local implementation on `feature/day1-foundation`, HEAD `67f85e0`. Existing staged, unstaged and untracked work was preserved. [Contracts and rollout](README.md) describe the preservation migration and reviewed header export. **F16 physical acceptance remains pending**, as recorded in [PHYSICAL-ACCEPTANCE.md](PHYSICAL-ACCEPTANCE.md).

| Check | Observed final result | Evidence |
|---|---|---|
| Complete backend and ML suites | **432 passed**, 23 dependency deprecation warnings, 334.86 seconds | [backend-tests-final.log](backend-tests-final.log) |
| Complete web Node suite | **37 passed** | [web-tests.log](web-tests.log) |
| Next.js production build, TypeScript and route generation | Passed | [web-build.log](web-build.log) |
| Complete Flutter suite | **110 passed** | [mobile-tests.log](mobile-tests.log) |
| Flutter analysis | No issues found | [mobile-analyze.log](mobile-analyze.log) |
| New mobile rainfall/configuration tests | **3 passed** | [mobile-interval-targeted.log](mobile-interval-targeted.log) |
| Actual firmware host acquisition and JSON contracts | Passed | [firmware-host.log](firmware-host.log) |
| Explicit cardboard boot profile host checks | Passed | [firmware-host-bench.log](firmware-host-bench.log) |
| Unprovisioned firmware publication guard | Passed | [firmware-host-unprovisioned.log](firmware-host-unprovisioned.log) |
| ESP32 compile/link for depth and cardboard environments | **Both succeeded** | [firmware-build.log](firmware-build.log) |
| Tracked and new-file whitespace checks | Passed; existing LF/CRLF normalization notices only | `git diff --check` and explicit checks of new implementation/docs files |

Backend acceptance tests cover geometry margin without lowering critical depth, stale configuration writes, administrator authorization, canonical hashes, absent/wrong applied hashes, historical-only mismatch/exercise samples, preserved unresolved episodes, delayed samples not replacing the applied-profile view, nullable v3 rainfall, explicit-interval conservation/time validation, overlapping cumulative snapshots, counter resets, reboot/outage recovery and mixed calibration accounting. Versioned MQTT rain uses the reviewed per-station coefficient and rejects a different hash before creating journal data or ACKing it. An isolated migration test preserves telemetry ID 42, its original rainfall and an inbound foreign-key reference, then verifies idempotence.

Web tests verify that ambiguous water-envelope rain is unavailable, journal zero remains numeric zero with interval/source/coverage, and the selected station coefficient replaces the former hardcoded 0.70 label. Existing ordering, freshness, history/export, unknown-state, authority and subscription checks remain included. The production build completed TypeScript and route generation. One existing Node module-type warning remains in rainfall tests.

Mobile tests cover null legacy rain, independent journal zero and age/error handling, source/coverage notes, station-specific gauge labels/colors/geometry and rainfall interval metadata even when no completed chart hours exist. Earlier account, unknown startup/outage, exercise isolation, notification, theme and narrow-layout coverage is retained.

Firmware host checks execute the real source with fake GPIO/echo/network/NVS boundaries and the real ArduinoJson library. Five integer-pulse bursts cross normal, advisory, warning and critical tiers under the unvalidated 150 cm bench geometry. The 2916/2915 microsecond boundary produces warning/critical respectively with near-range margin; a mixed burst containing a blind-zone echo becomes a fault. Tests verify fault blinking, retained critical red/buzzer output, self-test refusal, valid recovery, offline acquisition, persistence/reboot/ACK behavior, captured output profile, authentication publication guard and generated v3 water/v2 rain JSON against JSON Schema and FastAPI validators. This is software execution, not physical echo, sound, sensor-range or rain-volume evidence.

Commands used from the indicated folders:

```powershell
# agapay-backend
.\.venv-auth\Scripts\python.exe -u -m pytest tests app/ml/tests -q --basetemp .pytest_cache/f15-f16-final2 --tb=short

# agapay-web
node --test test/*.cjs test/*.mjs
npx tsc --noEmit
npm run build -- --webpack

# agapay-mobile
C:/flutter/bin/flutter.bat test
C:/flutter/bin/flutter.bat analyze

# repository root; installed local toolchains
agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Python314/python.exe -m ziglang c++'
agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Python314/python.exe -m ziglang c++' --bench-profile
agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Python314/python.exe -m ziglang c++' --unprovisioned
C:/Python314/python.exe -m platformio run --project-dir agapay-firmware --environment esp32doit-devkit-v1 --environment esp32-cardboard-demo
```

Earlier logs overlap these final checks and must not be added to their totals. Initial runs exposed obsolete fixture assumptions, an isolated missing unique index, an account-fixture reset, local schema-reference resolution and a redundant Dart assertion; these were corrected. Toolchain discovery used the installed global Zig/PlatformIO runtime; no dependency upgrade was performed.

No live migration/reset/reseed, reviewed station activation, broker/service restart, firmware upload/NVS erase, physical wiring/range/volume operation, external notification, native mobile installation, deployment, commit or push was performed. The fallback 150 cm prototype header is **not** an approved replacement for a 120 cm physical mounting. Real installation geometry, fault-policy review, coefficient measurements and the installed device/configuration profile remain required before field claims.
