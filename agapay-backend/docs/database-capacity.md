# PostgreSQL connection and monitoring-cache policy (R2)

The measurements were taken on synthetic data, using a disposable loopback PostgreSQL 16.15
instance on a 16-thread Windows laptop. They describe this workload on this machine, **not**
production capacity. The targets below are **provisional engineering targets**: AGAPAY has no
formally agreed station count, user load or availability objective yet.

## Root cause of pool saturation

- **The database was not the bottleneck.** With the old 15-connection pool, 80–88% of samples
  showed every connection checked out. Yet PostgreSQL never had more than 4–6 backends
  actually executing, and showed no lock waits, deadlocks or server errors.
- **The pool's connections were busy doing nothing.** Up to 15 connections at a time sat
  `idle in transaction`.
- **They were waiting for Python, not for PostgreSQL.** All 24 request threads in one Python
  process share one interpreter lock (GIL), and the process ran at about 1.2 CPU cores
  throughout. Each thread therefore held its connection while it waited for CPU between
  statements.
- **Pool size made no difference to throughput.** Throughput stayed at 9.2–10.2 samples/s with
  10, 12, 15 or 25 connections:
  - More connections removed the pool wait but lengthened holds and slowed snapshot builds.
  - Fewer connections lengthened the waits and the ingestion tail.
- **More processes did help.** Two API processes, the same pool per process and the same
  workload reached 12.4–14.1 samples/s.
- **Sessions are not leaking.** Every run ended with 0 connections checked out and no connection
  left idle in a transaction. Error paths return their connections; tests cover this.
- **Snapshot rebuilds were already single-flight.** Holding a database lease, there is about
  one build per refresh interval, not one per reader.
- **The cache served stale data far too often.** A snapshot was rebuilt only after it expired.
  27% of monitoring reads were therefore "last-known" (correctly labelled), and a rebuild
  longer than the TTL plus the 2 s grace plus the 2 s wait produced a 503. That happened once in
  an earlier run.

## Selected configuration (defaults)

| Setting | Default | Notes |
|---|---|---|
| `AGAPAY_DATABASE_POOL_SIZE` / `AGAPAY_DATABASE_MAX_OVERFLOW` | 5 / 10 (API processes) | Unchanged. Measured: a larger pool does not help, a smaller one hurts the tail. |
| Background worker pool | 2 / 1 | Default for `worker_service` and `ingestion_worker` processes, unless set explicitly (`app/process_pool.py`). |
| `AGAPAY_DATABASE_POOL_TIMEOUT_SECONDS` | 10 (was 30) | An exhausted pool answers `503 Retry-After: 2`; nothing was written. |
| `AGAPAY_DATABASE_POOL_RECYCLE_SECONDS` | -1 | `pool_pre_ping` already replaces dead connections after a server restart. |
| `AGAPAY_READ_MODEL_SECONDS` | 2 | Unchanged freshness. |
| `AGAPAY_READ_MODEL_REFRESH_AHEAD` | true (new) | One reader rebuilds in the last half-life while others keep the unexpired value. |
| `AGAPAY_READ_MODEL_STALE_SECONDS` | 2 (max 5) | Bounded last-known grace. Always `degraded` / `READ_MODEL_REBUILDING`, with original timestamps. |
| `AGAPAY_READ_MODEL_WAIT_SECONDS` | 2 (max 5) | Then `503 Retry-After: 1`. Never unlabelled stale data. |

## Connection budget (all processes)

Each process has its own pool, so the budget is the sum over processes.

| Process | Count | Per process | Maximum |
|---|---|---|---|
| API (`serve_production`, uvicorn) | 2 | 5 + 10 | 30 |
| MQTT ingestion worker | 1 | 2 + 1 | 3 |
| `worker_service` (notifications, identity mail, SOS drills, read model, diagnostics, forecasts) | up to 6 | 2 + 1 | 18 |
| Operator CLIs (migrations, recovery), one at a time | 1 | 5 + 10, uses 1–2 | ~2 |
| **Total** | | | **~53** |

- **Server limit.** A stock PostgreSQL installation has `max_connections = 100`, with 3
  `superuser_reserved_connections`, leaving 97 usable. Against 97 there are more than 40 slots
  left for administration, monitoring and backups. The drill instance was configured with 200.
  Always check the target's actual setting (`SHOW max_connections`).
- **Before this change** every worker process defaulted to 15 connections: 9 × 15 = 135
  possible connections, above the server limit.
- **Raising API workers or pool sizes** must keep `sum(processes × (pool_size + max_overflow))`
  below `max_connections - superuser_reserved_connections - admin headroom`.
- **Request threads outnumber connections.** Each uvicorn worker runs up to 40 request threads
  but has only 15 connections. Excess requests wait up to the pool timeout, then receive a 503.

## Provisional targets for this workload

These targets were met on the test laptop:
- 0 monitoring 503s and 0 pool timeouts per benchmark run;
- at most 1% of monitoring reads shown as last-known;
- no lost telemetry, duplicate sequences or duplicate active alert episodes;
- ingestion p99 under 3 s.

**Production sizing must be measured on target hardware against the intended number of stations
and operators.** Scale out API processes rather than pool size, since the bottleneck is
CPU-bound Python, not PostgreSQL.
