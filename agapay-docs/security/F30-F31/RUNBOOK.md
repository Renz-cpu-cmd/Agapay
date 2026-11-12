# Workflow health and response

These are configurable engineering defaults, not an LGU response agreement or a field availability certification. Assign a real duty owner and test the monitoring receiver before deployment.

## What each endpoint means

| Endpoint | Meaning | Access |
|---|---|---|
| `/live` | API event loop can answer; no database/broker/model dependency | Probe |
| `/health` | Legacy database connectivity probe only | Probe |
| `/ready` | Reviewed schema HEAD and every explicitly required capability is healthy | Probe; 503 otherwise |
| `/api/operations/status` | Sanitized workflow degradation and original check time | Signed-in residents/staff |
| `/api/operations/diagnostics` | Dependency, queue, worker, ingress and metric details | Staff |
| `/api/operations/metrics` | Low-cardinality five-minute workflow metrics and active fault codes | Dedicated private scrape bearer |

HTTP liveness alone never establishes station measurement freshness, delivery receipt or physical device operation. Optional disabled capabilities are shown as disabled; required disabled capabilities prevent readiness. A storage/read-model failure can make monitoring unavailable while `/live` remains available. Never configure a liveness restart policy from `/ready`: a broker outage should not cause an API restart loop.

## Installation order

1. Back up the database and verify restoration. Apply reviewed migrations offline using `python -m app.migrations`; do not reset or seed. Revision `0002_workflow_runtime` adds worker progress, bounded shared products, minute metric buckets and operator fault state. Revision 0001 is unchanged.
2. Complete the protected production environment template, PostgreSQL trust anchor, broker ACL/credentials, SMTP, storage ownership and HTTPS proxy. Populate `operations_required` with the capabilities the deployment actually promises. The example requires monitoring, broker/rain ingestion and account mail. Resident push remains explicitly disabled until configured.
3. Start API, dedicated ingestion, read-model, diagnostics, identity-mail and drill workers from `agapay-backend/deploy/compose.production.yaml`. Start the notification delivery profile only with its provider configured. One MQTT owner; no competing client IDs. This compose template targets a Linux host and external managed PostgreSQL.
4. Rain storage must exist with its reviewed schema and writable persistent directory. The ordinary ingestion journal initialization can create an empty journal; it does not establish any measurement or calibration. The diagnostic worker never creates a missing journal. Check the configured free-space reserve against actual traffic and disk size.
5. Install the example Prometheus scrape and rules from `agapay-backend/deploy/monitoring/`, replacing hosts and supplying a private token file. Restrict scraper access at the reverse proxy; validate certificates. Configure a real Alertmanager receiver and duty routing separately. No external receiver is enabled or message sent by this change.
6. Verify `/live`, `/ready`, staff System Health, a real authenticated station sample, decision history, intended delivery/provider acceptance and resident receipt independently. Record a deployment fault drill before making availability claims.

## Provisional budgets

| Signal | Default / interpretation |
|---|---|
| Required worker progress | Last successful bounded tick and heartbeat within 45 seconds |
| External broker observation | Dedicated heartbeat expires after 15 seconds; successful CONNACK and every required SUBACK are distinct |
| Pending/stalled delivery age | 60 seconds; configurable 10–600 seconds |
| Live ingress | Per commissioned active station; measurement eligibility and receipt age remain separate |
| Ingestion latency | Measured time to durable commit; p95 <=5 seconds after >=20 live samples in the five-minute window |
| HTTP error budget | Five-minute 5xx fraction <=1% after >=20 monitored requests; provisional, not a monthly availability promise |
| Shared monitoring | Two-second product TTL, proactive refresh at half TTL; at most two extra seconds of explicitly degraded last-known data during an overlapping refresh |
| Blocked producer | Lease expires after 30 seconds; late producer cannot overwrite a takeover result |
| Storage | 16 MiB minimum reserve in the example; writable rollback-only transaction plus sibling fsync probe every diagnostic tick |

Histograms report conservative bucket upper bounds, not exact p95/p99 estimates. Metrics flush at most every five seconds, persist seven days in shared minute buckets, and have a bounded in-memory failure buffer. A process crash can lose up to a flush interval of instrumentation. Diagnostics and queue state remain authoritative over any missing metric. Application metrics do not measure OS battery use, TCP transit, push receipt or resident comprehension.

## Fault response

| Code / symptom | Inspect and respond |
|---|---|
| `NOTIFICATIONS_WORKER_*`, `IDENTITY_MAIL_WORKER_*`, `READ_MODEL_WORKER_*` | Inspect worker service, last successful tick and database connectivity. Restore the correct service; verify progress rather than process existence. A slow batch also consumes the progress budget. |
| `BROKER_DISCONNECTED`, `BROKER_SUBSCRIPTION_REJECTED`, `BROKER_SUBSCRIPTION_UNCONFIRMED`, `BROKER_HEARTBEAT_STALE` | Inspect TLS trust, station/backend identities, ACLs, CONNACK/SUBACK and the single ingestion owner. A connected TCP client without acknowledged subscriptions is insufficient. |
| `RAIN_STORAGE_FULL`, `RAIN_WRITE_FAILED`, `RAIN_JOURNAL_UNAVAILABLE`, `RAIN_JOURNAL_MISSING`, `RAIN_WRITE_PROBE_STALE` | Check persistent mount, quota/free space, permissions, journal integrity and diagnostic worker. Preserve the journal/WAL and pending device ACK state. Do not delete/reset it to clear readiness. |
| `MODEL_ARTIFACT_UNAVAILABLE` | Restore the reviewed artifact set/runtime and verify its manifest. Keep projections unavailable; do not substitute synthetic forecasts. |
| `NOTIFICATION_QUEUE_OLD`, `NOTIFICATION_DELIVERY_STALLED` | Inspect provider availability and correlation IDs. Confirm the delivery worker is progressing. |
| `NOTIFICATION_DELIVERY_UNCERTAIN`, `IDENTITY_MAIL_DELIVERY_UNCERTAIN` | Review provider evidence and original intent. An unknown acceptance is never automatically replayed; follow the existing deliberate recovery/new-intent workflow. |
| `IDENTITY_MAIL_QUEUE_OLD` | Inspect SMTP, worker and token expiry. Expired/superseded recovery intents must remain unusable. |
| `OPERATIONAL_INGRESS_STALE` | Inspect each active station's heartbeat and last-valid measurement separately. Maintain unresolved incidents and original timestamps. Maintenance/commissioning state is a separate dimension. |
| `READ_MODEL_REBUILDING`, `READ_MODEL_PRODUCER_STALLED` | Retain the timestamped last-known view. Investigate repeated rebuilds, process progress, pool/CPU pressure and station/history budgets. After the bounded grace, callers receive 503/Retry-After and preserve their previous timestamps. |
| `READ_MODEL_STATION_BUDGET_EXCEEDED` / capacity response | Reduce selected station/history scope or review capacity with measurements. Never truncate silently or raise budgets without a load test. |
| Ingestion/error-budget burn | Follow structured `X-Request-ID`; telemetry, decision and delivery logs also share `observation-<telemetry_id>`. Compare source time, commit, decision, outbox, provider acceptance and actual receipt as separate stages. |
| Scrape `up=0` / database unavailable | Readiness is unknown or failed, not healthy. Inspect API, schema, database/network, credentials and monitoring transport. `/live` can remain 200. |

The diagnostic worker reconciles persistent active/resolved fault state and logs state changes. Prometheus emits a sustained-fault alert after 30 seconds plus scrape/evaluation delay. Receiver reachability, acknowledgement, routing and escalation must be tested on the intended installation. Existing sensor/SOS/resident notification paths are not reused for operator alerts.

## Repeatable acceptance drill

Use an isolated restored database, synthetic station namespace, test broker/identities, fake notification provider, disposable artifact directory and a quota-limited test volume. Stop each required worker; reject broker authentication and then SUBACK; rename a test artifact; exhaust/deny only the disposable rain volume; interrupt database access. Capture the specific code, readiness result, System Health/resident degraded state, original observation time, alert opening/receiver/acknowledgement and recovery/resolution. Confirm no historical telemetry or ambiguous delivery was replayed. The automated suite injects these faults without filling the user's real disk or interrupting live services; a real PostgreSQL/TLS/receiver/device drill remains a separate deployment gate.
