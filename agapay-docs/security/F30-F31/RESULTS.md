# Verification results — 2026-10-22

The implementation is locally verified software. Production PostgreSQL, actual broker/TLS fault injection, monitoring-receiver acknowledgement, native battery/network profiling and physical receipt-to-render latency remain deployment acceptance work.

## Synthetic load

20 stations with 120 synthetic observations each; 40 authenticated residents, 80 steady reads, ten concurrent requests. All external providers were disabled. Shared modes use a separate producer process; total CPU and SQL include that process. The earlier thread-only producer experiment caused stalls and is retained in the intermediate logs; it is not the final deployment topology.

| Measure | Uncached baseline | Shared web | Shared mobile |
|---|---:|---:|---:|
| Successful steady reads | 80/80 | 80/80 | 80/80 |
| SQL statements | 29,992 | 1,465 | 1,092 |
| Total CPU seconds | 111.641 | 5.469 | 4.141 |
| Total response bytes | 36,927,280 | 36,917,600 | 12,156,058 |
| Mean successful response bytes | 461,591 | 461,470 | 151,951 |
| API p95 seconds | 9.064 | 0.551 | 0.551 |
| API p99 seconds | 9.380 | 0.573 | 0.757 |
| Snapshot-age p95 seconds | 8.167 | 2.106 | 2.008 |
| Snapshot-age p99 seconds | 8.892 | 2.141 | 2.190 |
| Commit-to-first-API-visible probe seconds | 0.404 | 1.478 | 0.845 |
| Explicit last-known refresh responses | 0 | 0 | 1 |
| Successful cold reads | 10/10 | 10/10 | 10/10 |

At this test scale, shared web used 95.1% fewer SQL statements and 95.1% less total CPU than uncached reads. Mobile responses were 67.1% smaller than the full web history. These are observed single-run comparisons, not capacity guarantees. Warm-up and model/database initialization are excluded from steady CPU; cold requests are reported separately. Background producer SQL is attributed by query timestamps within the steady interval. Windows CPU includes the launcher and owned interpreter process tree.

API latency includes ASGI routing, current session/role validation, database work and serialization. It excludes TCP/TLS, the Next.js proxy, rendering, radio transfer and physical sensor acquisition. The commit visibility probe is one bounded polling experiment, not a p95/p99 field-lag measurement. Snapshot age preserves the original server check time, including explicitly labeled last-known grace. Real device sampling, notification/provider receipt and battery behavior need separate measurement.

## Client request budgets

| Visible feed | Before | After |
|---|---|---|
| Web monitoring | Every 1 second | Every 3 seconds; hidden/offline paused |
| Web live hybrid | About 750 ms after completion | 3 seconds after completion; subscribed views only |
| Web historical hybrid | Rapid shared polling | 15 seconds after completion |
| Mobile hybrid | 1.5 seconds | 3 seconds; 15 seconds after error; background paused |
| Mobile community alerts | 5 seconds | 10 seconds; background paused |
| Mobile monitoring | 120 records per station, 5-second polling | 20 records per station; 5-second foreground polling |

Theoretical visible web monitoring requests fall 67%, and live hybrid requests 75%, before coalescing/backoff. Those arithmetic request budgets are not measured native radio or battery savings. SOS retains its five-second foreground interval and existing conflict/idempotency behavior.

## Verification record

- Final complete backend/ML regression: **578 passed, 1 skipped**, 23 dependency deprecation warnings; see `backend-full-final.log`. The skipped test requires an explicitly configured real PostgreSQL test engine.
- Focused faults/cache/ordering/migration regression before the final producer changes: 62 passed; final cache and worker changes are covered by the final full run.
- Flutter: **155 tests passed**; final analysis reports **no issues** (`flutter-full.log`, `flutter-analyze-final.log`).
- Web: **65 tests passed**; final optimized Next.js production build passed, including its TypeScript check (`web-unit-final.log`, `web-build-final.log`).
- Copy-only migration: all original rows preserved, SQLite integrity and foreign keys checked. Source opened read-only; only `preserved-upgrade.db` was upgraded. Original counts: 1 station, 131 telemetry rows, 6 users, 4 sessions, 7 SOS requests, 3 alerts, 5 transitions, 3 notification events and 4 deliveries.
- Fault tests cover unusable database readiness with live liveness, stopped/stale workers, rejected broker authentication/SUBACK, missing artifacts, rain journal interruption, denied/full storage via ENOSPC injection, old/uncertain delivery state, budget burn and role/scraper boundaries. They do not exhaust the user's disk or interrupt live services.
- Cache tests cover timestamp preservation, atomic concurrent producer claims, bounded waiting/grace, generation changes, stale lease takeover and late-output rejection, cache capacity recovery, pre-expiry refresh and session revocation.
- Mobile/browser tests cover paused timers, resume, dropped old generations, forecast mode switching, original encrypted-cache retention and unknown/expired diagnostics.

No production deployment, notification receiver activation, live database migration, firmware flash, credential rotation, external message, commit or push was performed. Existing staged changes were preserved.
