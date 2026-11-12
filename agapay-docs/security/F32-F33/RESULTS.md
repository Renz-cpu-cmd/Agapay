# Observed verification — 2026-10-22

## Rain read benchmark

Disposable synthetic data: one station, five-second zero-rain heartbeats, **518,401 raw events** over 30 days, and **44,521 hourly summary rows** including five years of generated older summaries. The database was 491,544,576 bytes. No live database, journal, broker or gauge was accessed. The original raw-scanning snapshot is frozen in `tests/rain_reference.py` solely as a differential/benchmark oracle.

| Warm local read, 10 iterations | Original raw snapshot | Indexed rollup snapshot |
|---|---:|---:|
| Median seconds | 3.610896 | 0.004928 |
| Slowest observed seconds | 3.913398 | 0.006491 |
| Total CPU seconds | 36.046875 | 0.046875 |
| Approximate SQLite VM instruction callbacks | 10,092,000 | Below 1,000 per statement |

The quiet two-day comparison had a 2.476807-second original median and 0.004852-second optimized median. Original and optimized completed-hour products and lifetime rain agreed. The 30-day zero-rain workload exercises quiet journal growth and lifetime scans; separate differential tests cover nonzero tips, gaps, recovery, calibration changes and source separation. EXPLAIN plans use the hourly primary key, partial tip index, partial non-recovered anchor index and gap-overlap index. The low VM callback count is not zero SQL work: the callback threshold is 1,000 instructions per statement.

These timings were run without overlapping builds/test suites, with warm local SQLite reads. Bulk-generated rows and synthesized older summaries do not measure ingestion throughput, fleet capacity, disk endurance, power use or managed-store durability. Ten iterations do not establish production p95/p99 service objectives. See [rain-benchmark.json](rain-benchmark.json) and [benchmark script](../../../agapay-backend/scripts/benchmark_rain_journal.py).

## Regression and preservation

- Full backend/ML regression: **595 passed, 1 skipped**, 23 dependency deprecation warnings (`backend-full.log`). The skipped real-PostgreSQL concurrency test requires an explicitly configured test engine.
- Final contracts after additional archive guards, committed-cut reads and transport-expiry cases: **93 passed** (`backend-final-contracts.log`), including channel/forecast behavior while a legacy journal awaits upgrade. A focused ordering failure exposed a missing rain-test account reset; the fixture was isolated before rerunning. The supplementary rain run passed **19 tests**, including create-only CLI restore and the retired-boot ACK guard (`backend-supplementary-final.log`).
- Web: **68 passed** (`web-unit.log`); optimized production Next.js build and TypeScript passed (`web-build.log`). Behavioral tests cover independent unknown callback stages, officer read-only controls, hash-only evidence submission, no automatic 409 retry, exact-origin/session enforcement and bounded filter forwarding.
- Flutter: **163 passed** (`flutter-full-final.log`); analyzer **no issues** (`flutter-analyze-final.log`). Coverage includes encrypted-storage abstraction recovery after restart, original client time, public capability submission without API authorization, duplicate stages, withdrawal/expiry, account-generation rejection, explicit acknowledgement conflicts, and scrollable 320px light/dark evidence screens. Tests use in-memory substitutes for encrypted storage and synthetic network/providers; native secure-storage and OS background behavior require the phone drill.
- Main database copy-only upgrade to revision **0003_delivery_evidence** preserved every original compared row/column. Source was opened read-only; SQLite integrity and foreign keys passed. Original counts: 1 station, 131 telemetry, 6 users, 4 sessions, 7 SOS, 3 alerts, 5 transitions, 3 notification events and 4 deliveries (`copy-upgrade.log`). The copy is excluded from Git because it can contain personal data.

Rain tests compare optimized versus original hour products, source/calibration boundaries and missingness; preserve valid zero; roll back raw/counter/summary changes together on injected failure; verify no MQTT ACK before summary commit; check old exact packet idempotency versus conflicts and uncommitted packets; and reject corrupt archives. Both interruption points during archival leave committed hot rows intact. A portable backup/restore retains exact old-packet ACK behavior and cumulative totals. A concurrent writer cannot mix newer session metadata into an older summary read. Floating-point millimeter sums use the tolerance documented in the runbook; counts and missingness compare exactly.

Notification interruption tests stop after claim, after durable attempt preparation, after provider return and before result commit. None permits automatic reclaim/replay. A callback can add app-reported evidence while raw PROCESSING/UNKNOWN remains ambiguous. Consent revocation and same-installation token rotation are distinct. Reconciliation is role-scoped, version-checked and audited; stale decisions never overwrite newer receipt evidence. Provider acceptance, app Received, Opened and explicit resident Acknowledged remain independent stages. SDK transport tests use a local fake HTTP server or mocked official SDK send, with synthetic credentials; there is no Firebase network send.

## Remaining deployment evidence

Controlled real-phone receipt/open/acknowledgement, foreground/background/terminated callbacks, native encrypted-storage recovery, PostgreSQL concurrency, operator alert receiver, deployed supervision, archive-volume power-loss durability and off-host restore remain pending. Firebase [delivery stages](https://firebase.google.com/docs/cloud-messaging/understand-delivery) and [Flutter callback constraints](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages) guide that drill. An app callback is not independent proof of screen display or resident safety.

No operational database/journal upgrade, archive of live data, real notification worker/provider call, external message, production deployment, firmware flash, commit or push was performed. The original 48 staged paths remain staged as found. Historical ambiguous deliveries were untouched. Follow [RUNBOOK.md](RUNBOOK.md) before activating these changes.
