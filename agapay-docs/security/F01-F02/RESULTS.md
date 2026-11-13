# F01/F02 implementation verification

Completed October 21, 2026, Asia/Manila. Changes remain uncommitted in the existing working tree; unrelated staged/unstaged work was preserved.

## Final observed checks

| Check | Result | Log |
|---|---|---|
| Complete backend regression suite on final source | **298 passed**, 23 existing dependency/provider deprecation warnings, 201.24 seconds | `backend-tests-complete.txt` |
| Isolated Mosquitto ACL integration | Passed as part of the full suite; no skip | Same full-suite log; `tests/test_station_broker_acl.py` |
| ESP32 default target compile/link | Passed; RAM 45,848 / 327,680 bytes, flash 785,813 / 1,310,720 bytes | `firmware-build.txt` |
| Actual firmware host logic and payload contracts, default | Passed | `firmware-host-default.txt` |
| Actual firmware host logic and payload contracts, cardboard profile | Passed | `firmware-host-bench.txt` |
| Unprovisioned firmware behavior | Both publications withheld; local sensing preserved | `firmware-host-unprovisioned.txt` |
| Python compilation of changed application/publisher modules | Passed | `compileall -q` completed without errors |
| Scoped Git whitespace check | Passed | `git diff --check` completed without errors |
| Real firmware ingestion header tracking | Ignored and untracked; no real token file was created | `git check-ignore` / `git ls-files` checks |

The security suite verifies:

- Anonymous, invalid, staff/resident session, expired, revoked, wrong-station, wrong-transport and uncommissioned/stale-binding rejection, with no telemetry/episode/transition/outbox/heartbeat mutation.
- Valid HTTP, MQTT water and MQTT rain paths, durable rain deduplication/ACK behavior and secret redaction.
- Retained and oversized message rejection, HTTP streaming-body limits, shared database quotas across transports/sessions, duplicate-attempt charging and window recovery.
- Rechecking expiry/revocation after the quota commit, so a credential change in that interval cannot be bypassed.
- Admin-only creation and all credential/commission/audit operations; atomic uniqueness handling, required metadata, version conflicts, recorded actors/reasons and before/after coordinates/configuration.
- Pending stations can complete commissioning with reviewed coordinates through the API; no station recreation or manual SQL is needed.
- Additive migration preserves an existing station record and is repeatable.
- HTTPS and backend MQTT TLS requirements outside development; a real private loopback broker rejects anonymous/wrong-password clients and cross-station/spoofed-ACK operations.
- Simulator authorization without token logging, and firmware missing-token behavior without changing local sensing, rain/sequence persistence or physical thresholds.

## Commands actually run

From `agapay-backend`:

```powershell
& .venv-auth/Scripts/python.exe -m pytest tests -q --basetemp .pytest_cache/f01-f02-complete --tb=short
```

From the repository root:

```powershell
& C:/Python314/python.exe -m platformio run --project-dir agapay-firmware --environment esp32doit-devkit-v1
& agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Python314/python.exe -m ziglang c++'
& agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Python314/python.exe -m ziglang c++' --bench-profile
& agapay-backend/.venv/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Python314/python.exe -m ziglang c++' --unprovisioned
```

Python and compiler tests used existing environments with host access. No dependency upgrade was performed. PlatformIO completed the build, then reported that its optional upgrade check could not reach the network; the compile/link exit was successful. The first broad regression run found three old monitoring fixtures that still posted anonymously; those fixtures were updated to use synthetic station credentials. Subsequent full runs passed; the final 298-test log is authoritative over the intermediate logs in this folder.

## Activation status and limits

**Code implemented and locally verified; live activation is pending.** The original audit/backlog records this distinction. No live database migration, broker/password/ACL reload, service restart, station commissioning, production token creation, credential installation, ESP32 flash, NVS erase, external notification send, commit or push was performed.

Follow the [rollout guide](README.md) to activate deliberately. Old unauthenticated publishers will be rejected when the updated backend is started. The current firmware's plaintext development transport is not a certificate-validated production TLS client. Physical calibration, the default alarm-range limitation F16, trusted physical provenance beyond credential possession, delayed-sample ordering and other audit findings remain separate work.

Backend tests, host fakes and a compiled image do not establish physical sensor accuracy, field alert readiness, broker configuration on the live topology or phone notification receipt. Public read-only station/telemetry access was deliberately retained; no web/mobile measurement response shape was changed. Web/mobile UI suites were not rerun for this backend/firmware security change.
