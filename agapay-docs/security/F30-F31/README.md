# F30–F31 implementation

Implemented workflow diagnostics and bounded shared reads across FastAPI, web and resident mobile. See [RUNBOOK.md](RUNBOOK.md) for deployment configuration, fault codes, budgets and response actions; [RESULTS.md](RESULTS.md) records observed verification and limits.

The API separates liveness, dependency readiness and protected diagnostics. Required capability checks cover database schema, worker progress, broker subscription acknowledgement, rain storage writes, model artifacts and notification/account-mail queues. Commissioned active stations are checked individually for ingress silence. Structured HTTP/sample/decision/delivery correlation, bounded shared metrics, persistent operator faults and private Prometheus rules support the response workflow. Web System Health exposes dependency failures independently of station channels; monitoring responses give both clients a sanitized degraded state.

Monitoring products are shared in the database across API workers. A canonical 120-point product serves both web and trimmed 20-point mobile responses. Station and point budgets bound producer queries; single-station projection initialization reads only that station. Audited configuration/account/lifecycle changes invalidate product generations, while every request still checks the current account session and role. The web proxy delegates that check once per request to the backend using a restriction-only staff header.

The read-model worker refreshes before expiry. Concurrent cold readers can wait at most two seconds for the same result. Monitoring alone may serve at most two seconds of explicitly degraded last-known data during another producer's refresh, preserving every original timestamp; a changed configuration generation cannot use that grace. Inference never extends its validity through this fallback. Database leases recover failed producers and reject late results after takeover. Expensive rainfall inference is shared by versioned inputs/artifacts, with bounded cache retention; time-dependent projection adjustment retains its short validity.

Visible web feeds coalesce requests, abort suspended reads, resume immediately and bound retry backoff. Hybrid feeds exist only while a component subscribes to that station. Mobile monitoring, hybrid, forecast and community-alert controllers pause timers in the background, reject old generations and refresh on resume; retained data continues to age. The old encrypted monitoring cache remains readable without renewing its saved time. Mobile stays resident-only. Polling uses measured bounded intervals; no SSE delivery guarantee is claimed or added without a demonstrated benefit.

Reproduce the synthetic benchmark from `agapay-backend` with the installed backend environment:

```powershell
.venv-auth/Scripts/python.exe -u scripts/benchmark_read_models.py --mode uncached --output ../agapay-docs/security/F30-F31/benchmark-uncached.json
.venv-auth/Scripts/python.exe -u scripts/benchmark_read_models.py --mode shared --output ../agapay-docs/security/F30-F31/benchmark-shared.json
.venv-auth/Scripts/python.exe -u scripts/benchmark_read_models.py --mode mobile --output ../agapay-docs/security/F30-F31/benchmark-mobile.json
```

Each command creates and removes its own synthetic database, disables broker/delivery providers and never opens the development database. Run modes sequentially without competing builds/tests. The default workload is 20 stations ×120 records, 40 signed-in synthetic residents, two rounds (80 reads), ten concurrent requests; cold contention is reported separately. The shared modes include a proactive producer in a dedicated measured process. Results are single-process SQLite ASGI measurements, including auth, queries, serialization and instrumentation; they exclude TCP, BFF, rendering, native battery, field ingestion and push receipt. There is no deployment or field-capacity claim.
