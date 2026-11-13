# F03/F04 verification — October 21, 2026

Local source on `feature/day1-foundation`, starting HEAD `67f85e0`. Existing staged/unstaged work was preserved. No commit or push was made.

| Check | Observed result | Evidence |
|---|---|---|
| Full backend suite, final source | **330 passed**, 23 dependency deprecation warnings, 317.76 seconds | [backend-tests-verified.txt](backend-tests-verified.txt) |
| ESP32 release compilation | SUCCESS; RAM 46,180 / 327,680 bytes; flash 800,033 / 1,310,720 bytes | [firmware-build.txt](firmware-build.txt) |
| Firmware host, default profile | PASS | [firmware-host-default.txt](firmware-host-default.txt) |
| Firmware host, bench profile | PASS | [firmware-host-bench.txt](firmware-host-bench.txt) |
| Firmware host, unprovisioned profile | PASS; no water/rain publish, sensing continues | [firmware-host-unprovisioned.txt](firmware-host-unprovisioned.txt) |
| Migration failure after original table DROP | PASS; transaction restores readings, IDs, alert/outbox references and old schema | [migration-rollback.txt](migration-rollback.txt) |
| Python compilation / synthetic documentation examples | PASS; both examples satisfy v2 JSON Schema and FastAPI | Run locally with compileall / JSON Schema / TelemetryCreate |
| Scoped `git diff --check` | PASS | No whitespace errors |

The final backend command, from `agapay-backend`, is:

```powershell
.\.venv-auth\Scripts\python.exe -m pytest tests -q --basetemp .pytest_cache/f03-f04-verified --tb=short
```

Coverage includes the original 1001/105 cm → 1000/1 cm probe, immutable late history, operational latest/monitoring preservation, durable sequence/uptime high-water marks even for unsynchronized/stale history, reused ORM-session refresh after another worker commits, rebooted sequence reuse, retired boot rejection for current state, boot-ID/ordinal conflicts, payload-vs-exact-duplicate distinctions, source/configuration binding, UTC/future/overflow/nonfinite validation, upgrade cutoff, simultaneous HTTP/MQTT reordering and duplicate/conflict races, and first-subscription/reconnect retained rejection.

Migration tests use disposable SQLite databases and preserve legacy values, primary IDs, alert/outbox references and receipt times. They verify check-only behavior, idempotence, boot-scoped uniqueness, FK integrity, refusal of unexpected custom indexes and transactional rollback. The complete suite also checks existing auth, alerts, monitoring, notifications, forecasts, rain integration and isolated Mosquitto ACL enforcement.

Firmware host tests compile the actual source against fakes; actual serialized telemetry/rain envelopes are validated against JSON Schema and Pydantic. The v2 assertions cover exact boot/source/configuration identity, measured-time output, null unsynchronized time, and uptime beyond 32-bit millis wrap. These tests never access a physical ESP32.

Earlier logs are retained as intermediate evidence; use `backend-tests-verified.txt` as the authoritative full-suite result. Suite totals overlap and must not be added together.

## Activation boundary

The [rollout guide](README.md) documents the explicit SQLite migration, reviewed identity/version installation, publisher upgrade, clock and failure behavior, and controlled activation checks. No live migration, reset/reseed, broker/service restart, station credential installation, device flash/NVS erase, physical sensor/clock test, or external notification was performed. SQLite concurrency was tested locally; this does not constitute PostgreSQL migration verification or production field readiness. Production device TLS remains separate work.
