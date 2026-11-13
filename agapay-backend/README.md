F28/F29: [depth history, explicit migrations and managed deployment](../agapay-docs/security/F28-F29/README.md). Startup now requires the migration ledger and never seeds demo data.

# AGAPAY Backend

F15/F16 add explicit rainfall products and reviewed installation hashes. Firmware fallback geometry is an unvalidated 150 cm bench profile; it is not a drop-in update for a 120 cm mounting. See [contracts, preservation migration, header export and physical acceptance](../agapay-docs/security/F15-F16/README.md).

F12â€“F14 add independent channel health, measured-time rise estimates and bounded persisted history/event reports. See [contracts, history-index migration and verification](../agapay-docs/security/F12-F14/README.md).

F09â€“F11 add provisional hysteresis/recovery policy, distinct issuer notice lifecycles and explicit notification subscriptions. See [implementation, setup and verification](../agapay-docs/security/F09-F11/README.md).

FastAPI telemetry foundation and persistent account services for AGAPAY.

For first-administrator setup, web/mobile login, roles, and account endpoints, see [Accounts setup](../agapay-docs/ACCOUNTS_SETUP.md).

Station writes now require admin provisioning and a separate station ingestion credential.
See [F01/F02 commissioning, authentication and rollout](../agapay-docs/security/F01-F02/README.md)
before running an existing publisher. Existing station data is preserved; no device
is implicitly authorized by the seeded station row.

Water ingestion now requires the v2 boot/measurement metadata. Existing databases
need the explicit preservation migration before startup; see
[F03/F04 ordering and rollout](../agapay-docs/security/F03-F04/README.md).

[F05/F06 source registry and freshness](../agapay-docs/security/F05-F06/README.md)
adds required admin source review, isolated exercise ingestion and separate
heartbeat/retained-depth clocks. Existing identities are not automatically
classified physical. HTTP simulators use `/api/exercises/telemetry`.

## What is implemented

- FastAPI application and interactive OpenAPI documentation
- SQLAlchemy 2 database layer
- Explicit development-only `STATION_001` demo bootstrap
- Strict telemetry validation matching the MQTT contract
- Boot-scoped duplicate/conflict protection and atomic current-state ordering
- Separate acquisition/receipt timestamps; late samples remain historical
- Latest and historical telemetry endpoints
- Scenario-driven HTTP virtual-station sender
- Authenticated monitoring snapshot with freshness, source, severity, trend, and history
- Optional MQTT subscriber scaffold

Persistent practice SOS with owner/staff access, idempotent submissions and audited status transitions is documented in [Practice SOS setup](../agapay-docs/SOS_SETUP.md).

Authentication, resident registration, profiles, revocable sessions, and administrator user management are implemented alongside `stations` and `telemetry`. The [prediction interface](../agapay-docs/PREDICTION_INTERFACE.md) supplies 30/60/90-minute availability responses and explicit development previews. No trained ML model is configured. Bounded persisted water-depth reports are documented in the F12â€“F14 guide above; they do not replace a complete operational incident report.

## Start on Windows

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# For a NEW database; existing installations first verify a private copy and stop writers.
python -m app.migrations --apply --writers-stopped --backup-confirmed
# Optional development demo; review seed metadata first.
python -m app.bootstrap_demo --apply
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

In a second activated PowerShell window:

```powershell
python simulator\simulate_http.py --scenario flash-flood --count 16 --interval 2
```

No hardware is required for the simulator, but it needs a commissioned station and
`AGAPAY_STATION_INGEST_TOKEN` with HTTP scope. The web and mobile apps need a
normal local account to read the protected monitoring snapshot. See the
[virtual-station guide](../agapay-docs/TELEMETRY_SIMULATOR.md) for every scenario.

## Useful endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | API and database health |
| GET | `/api/stations` | List registered stations |
| POST | `/api/stations` | Register a station |
| POST | `/api/telemetry` | Validate and store one reading |
| GET | `/api/telemetry/{station_id}/latest` | Latest reading |
| GET | `/api/telemetry/{station_id}?limit=20` | Recent history |
| GET | `/api/monitoring/stations?history_limit=60` | Authenticated app-ready monitoring snapshot |
| GET | `/api/predictions/{station_id}` | Authenticated forecast availability and development previews |

## Database progression

The default database is the temporary local file `agapay_dev.db`, which is excluded from Git. It proves the complete validation and persistence flow without requiring a database server on Day 1.

PostgreSQL/Supabase remains the AGAPAY target. After PostgreSQL is ready:

1. Install `requirements-postgres.txt`.
2. Change `AGAPAY_DATABASE_URL` in `.env`, for example:

   `AGAPAY_DATABASE_URL=postgresql+psycopg://agapay_user:password@localhost:5432/agapay`

3. Restart FastAPI.

Before deployment, add Alembic migrations and use a secret manager rather than committing credentials.

## Optional local MQTT subscriber

After a local/private broker is ready:

1. Install `requirements-mqtt.txt`.
2. Set `AGAPAY_MQTT_ENABLED=true` and the broker settings in `.env`.
3. Restart FastAPI.

The subscriber listens to `agapay/stations/+/telemetry`, checks that the topic station matches the payload, validates the same Pydantic model used by HTTP, and stores through the same service.

Do not send sensitive or real deployment data through a public anonymous broker.

## Run tests

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

## Persistent sensor alerts

Sensor flood alerts are stored in `alerts` as episodes and in `alert_transitions`
as an audit trail. The shared `classify_depth()` function uses each station's
existing advisory/warning/evacuate depth thresholds; monitoring uses that same
function. Thresholds remain **provisional development settings pending physical
and site calibration**. No new thresholds, hysteresis, or multi-sample
confirmation delays are introduced; valid escalations are immediate.

A VALID non-NORMAL reading starts an ACTIVE episode, including a direct jump to
WARNING or EVACUATE. Further valid readings update that episode's current severity
and latest depth/reference. Its highest severity never decreases. Only severity
changes create transitions. A VALID NORMAL reading records the final transition
and marks the episode RESOLVED. A later rise starts a distinct episode. Resolved
episodes retain their original trigger, peak, final depth, and timestamps.

INVALID telemetry is stored but does not create, resolve, downgrade, or otherwise
modify an episode. Missing data is not NORMAL. Station `inactive`/`maintenance`
status and connectivity are administrative concerns: changing them cannot rewrite
sensor history; valid telemetry received in those states still follows the same
lifecycle. Existing monitoring freshness/history behavior is preserved, including
unknown severity when no valid reading is available in its requested history window.

Both HTTP and MQTT call the same ingestion service. Telemetry is flushed first,
then its episode/transition changes are committed **in the same transaction**.
A processing failure rolls everything back, including the station's last ping.
A station write lock serializes concurrent ingestion; a database unique index
allows at most one ACTIVE episode per station. The existing station/sequence
constraint rejects duplicate telemetry (HTTP 409; MQTT ignores duplicates), and
a unique telemetry reference prevents duplicate transitions. Even a retry with
changed content under the same sequence cannot alter alert history.

Processing follows serialized server receipt order, matching existing monitoring
semantics; sequence numbers identify duplicates rather than enforcing source-time
ordering. Timestamps are server UTC receive times, not physical measurement times.
`source="sensor"` means telemetry-generated rather than manually authored; accepted
simulator telemetry also exercises this engine and is not proof of physical data.

### Staff read API

Every route requires an active authenticated **admin or officer** bearer session.
Missing/invalid/expired sessions return 401; residents return 403. Responses use
explicit Pydantic contracts and `Cache-Control: no-store`. No alert mutation or
acknowledgment endpoints are exposed; SOS acknowledgment remains separate.

| Method | Path | Result |
|---|---|---|
| GET | `/api/alerts` | Episode history, newest trigger first |
| GET | `/api/alerts/active` | ACTIVE episodes only |
| GET | `/api/alerts/{alert_id}` | Episode details (404 if absent) |
| GET | `/api/alerts/{alert_id}/transitions` | Transition history, oldest first (404 if episode absent) |

Lists return `{items, total}` and accept `limit` (1â€“100, default 50) and `offset`
(default 0). Episode lists support `station_id` and `severity` (current severity);
`/api/alerts` additionally accepts `status=ACTIVE|RESOLVED`. An unknown station
filter returns an empty page. Resolved episodes have current severity NORMAL and
retain their highest severity separately. Transition pages include previous/new
severity, depth, telemetry ID/sequence, and UTC timestamp. Episode details include
trigger/latest telemetry IDs/sequences and depths, trigger/last-transition times,
and optional resolution time. Use the existing `/docs` OpenAPI schemas for fields.

Schema upgrades are explicit and version checked; follow the F28/F29 guide. Startup preserves existing episodes without replaying them. Historical depth backfill never reclassifies current hazards or enqueues notifications. Field deployment and provider acceptance remain separate.

### Community read API

`/api/alerts` remains the **staff-only operational API**, including richer
telemetry diagnostics. Residents still receive 403 on every operational alert
read. The separate `/api/community-alerts` API accepts active authenticated
**resident, officer, or admin** accounts using the existing bearer sessions.
Missing, invalid, expired, revoked, or inactive-account sessions receive 401.
Community responses, including errors, use `Cache-Control: no-store`. There is
no anonymous access or alert mutation/acknowledgment endpoint.

| Method | Path | Result |
|---|---|---|
| GET | `/api/community-alerts/active` | Active persistent sensor episodes |
| GET | `/api/community-alerts` | Active and resolved episodes; use `status=RESOLVED` for history |
| GET | `/api/community-alerts/{alert_id}` | Safe episode detail with a bounded transition page; 404 if absent |

Both lists return `{items, total}`. They accept `station_id`, `limit` (default 50,
range 1â€“100), and `offset` (default 0, minimum 0). The general list additionally
accepts `status=ACTIVE|RESOLVED`. Ordering is newest `triggered_at` first, then
descending episode ID for ties. `total` counts matching episodes before pagination;
an unknown station or exhausted page returns an empty `items` list. Offset pages
can shift while new episodes arrive; clients should refresh rather than treat
them as an immutable snapshot.

Each episode exposes only:

- `id`, `station_id`, `station_name`, nullable `barangay` and `municipality`
- `status`, `severity`, `source="sensor"`
- `trigger_depth_cm`, `latest_depth_cm`
- `triggered_at`, `last_transition_at`, nullable `resolved_at` (UTC timestamps)

**Severity is current severity while ACTIVE and highest incident severity while
RESOLVED.** It is ADVISORY, WARNING, or EVACUATE; resolved history never presents
NORMAL as its incident tier. `status` distinguishes ongoing and ended episodes.
Trigger depth is the first alert reading, not a peak depth. Latest depth is the
last valid episode reading while active, or the final NORMAL recovery reading
after resolution. Peak severity does not imply a stored peak depth.

Detail adds `transitions: {items, total}`. Use `transition_limit` (default 50,
range 1â€“100) and `transition_offset` (default 0, minimum 0) to page the timeline.
Transitions follow chronological ingestion order, with the internal transition
ID breaking timestamp ties. Their public fields are only `previous_severity`,
`new_severity`, `water_depth_cm`, and `transitioned_at`. A direct
NORMAL â†’ EVACUATE transition is returned as recorded. Telemetry IDs, telemetry
foreign keys, sequence numbers, transition IDs, actor/account/session information,
and authentication data are excluded from the community contract.

The existing `Alert` and `AlertTransition` records remain authoritative. Reads
do not classify telemetry or alter the engine. Invalid telemetry does not resolve,
downgrade, or update an episode, so the community API retains the previous state
and last valid depth; that depth may be stale. Resolution is not a new all-clear
notification and does not guarantee that an area is safe.

Feeds cover registered AGAPAY stations without automatically filtering by the
resident profile's barangay. Explicit station filtering is optional. Station
names/areas reflect current metadata, not a historical metadata snapshot.
Inactive or maintenance station settings do not hide or resolve stored episodes.
Historical device/simulator origin is **not stored** and is not inferred from
current firmware metadata. `source="sensor"` means telemetry-generated, not
physically verified. An EVACUATE sensor tier is not an official LGU evacuation
order; physical/site calibration of the provisional thresholds remains outstanding.

Flutter consumes this Community Alert API through its authenticated client.
Loading, unavailable, active and resolved states are distinct. The FCM adapter is available behind explicit configuration; actual delivery is
unverified. Station/area subscriptions and optional delivery evidence are implemented;
physical receipt and flood-exposure geofencing remain unverified.

## Notification foundation

Device registration and a transactional escalation outbox now prepare resident
push delivery. The Firebase Admin HTTP v1 adapter is implemented; the default
provider remains disabled and no real delivery is verified. See [external FCM setup](docs/firebase-fcm-setup.md). See [notification architecture and local worker checks](docs/notifications.md)
for API contracts, session-linked explicit revocation, retry/ambiguity policy, payload safety,
and the external Firebase setup still required.

Station lifecycle administration, persistent preferences, English-only language and verified geographic context: [F17-F19 contracts and rollout](../agapay-docs/security/F17-F19/README.md).

Account recovery/invitations, staff MFA, session management, shared abuse controls and versioned mutation audits: [F20-F21 contracts and deployment](../agapay-docs/security/F20-F21/README.md).

Atomic SOS location/lifecycle versions and configurable response drills: [F22-F23 contracts and rollout](../agapay-docs/security/F22-F23/README.md). Operational dispatch remains disabled.


Versioned authority-maintained shelters, road reports, preparedness references and read-only exact-payload SOS receipts: [F24-F25 contracts, rollout and remaining device acceptance](../agapay-docs/security/F24-F25/README.md). Live inventory starts empty; generic routes do not certify flood-safe access.


Verified production MQTT contexts, reviewed HTTPS origins and explicit physical-device broker ACL staging: [F26-F27 implementation, rollout and verification](../agapay-docs/security/F26-F27/README.md). Field deployment acceptance remains pending.

## Workflow readiness and shared reads (F30–F31)

Use `/live` for dependency-free liveness and `/ready` for schema plus explicitly required workflow capabilities. Protected `/api/operations/diagnostics` and separately authenticated `/api/operations/metrics` report broker SUBACK, worker progress, rain storage, model and delivery faults. Apply revision 0002 offline before serving; the production template adds dedicated read-model and diagnostics workers. Follow the [workflow runbook](../agapay-docs/security/F30-F31/RUNBOOK.md) and [verification results](../agapay-docs/security/F30-F31/RESULTS.md). A 200 liveness response does not establish live observations or received notifications.

## Rain retention and notification evidence (F32–F33)

Schema HEAD is now `0003_delivery_evidence`; existing rain journals independently require explicit version-3 upgrade. Rain snapshots use indexed transactional rollups; verified bounded archival and portable backup/restore preserve counters and ACK semantics. System Health exposes scoped delivery evidence and audited reconciliation without resend. Resident mobile adds optional encrypted received/open callback recovery and explicit versioned acknowledgement. Follow the [contracts, maintenance runbook and verification results](../agapay-docs/security/F32-F33/README.md). No provider or maintenance timer is automatically activated.

## Reviewed forecast publication (F34–F35)

Main schema HEAD is `0004_forecast_registry`. Operational predictions read one immutable published station product; the supervised publisher accepts only independently reviewed, site/datum/calibration-bound JSON adapters. The offline water-depth pipeline evaluates a transparent candidate against persistence and rate baselines using whole withheld events and actual observation availability. No real field model is trained or approved by installation. Private rainfall/basin experiments cannot change resident products. See [data prerequisites, registry, contracts and rollout](../agapay-docs/security/F34-F35/README.md).


### Event uncertainty and reproducible profiles (F36–F37)

Forecast approval now also requires separately calibrated event intervals, reviewed decision tradeoffs and subgroup/baseline evidence. Out-of-domain or expired publisher input gates withhold older products. The default policy remains provisional; no field model is supplied. CI separates core/ML/hybrid dependencies, generates synthetic integration artifacts, checks all forecast contracts, audits dependencies and exercises browser/container/PostgreSQL jobs. See [F36–F37 verification](../agapay-docs/security/F36-F37/RESULTS.md) and [runbook](../agapay-docs/security/F36-F37/RUNBOOK.md) for exact commands and remaining field/hosted acceptance.

F40 adds versioned privacy cases/holds, reviewed resident erasure, bounded retention/access-review tools, production ownership attestation and encrypted quarantined recovery. Main schema HEAD is `0005_privacy_recovery`; apply migrations only through reviewed offline rollout. See [contracts and review package](../agapay-docs/security/F40/README.md), [runbook](../agapay-docs/security/F40/OPERATIONS-RUNBOOK.md) and [observed verification](../agapay-docs/security/F40/RESULTS.md). Real organizational approval and production restore acceptance remain pending.

Resident notice reads support exact area/status filters and current terminal records before bounded pagination, with echoed scope, original check time and has-more metadata. See [resident home/alerts contracts and verification](../agapay-docs/design/resident-decisions/README.md).
