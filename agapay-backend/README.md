# AGAPAY Backend

FastAPI telemetry foundation and persistent account services for AGAPAY.

For first-administrator setup, web/mobile login, roles, and account endpoints, see [Accounts setup](../agapay-docs/ACCOUNTS_SETUP.md).

## What is implemented

- FastAPI application and interactive OpenAPI documentation
- SQLAlchemy 2 database layer
- Automatically seeded `STATION_001` virtual UCU irrigation station
- Strict telemetry validation matching the MQTT contract
- Duplicate protection using `(station_id, sequence_no)`
- UTC receive timestamps
- Latest and historical telemetry endpoints
- Scenario-driven HTTP virtual-station sender
- Authenticated monitoring snapshot with freshness, source, severity, trend, and history
- Optional MQTT subscriber scaffold

Persistent practice SOS with owner/staff access, idempotent submissions and audited status transitions is documented in [Practice SOS setup](../agapay-docs/SOS_SETUP.md).

Authentication, resident registration, profiles, revocable sessions, and administrator user management are implemented alongside `stations` and `telemetry`. The [prediction interface](../agapay-docs/PREDICTION_INTERFACE.md) supplies 30/60/90-minute availability responses and explicit development previews. No trained ML model is configured. Push delivery, WebSockets, operational reports, and ML training remain later phases.

## Start on Windows

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

In a second activated PowerShell window:

```powershell
python simulator\simulate_http.py --scenario flash-flood --count 16 --interval 2
```

No hardware or simulator account is required. The web and mobile apps need a
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

Lists return `{items, total}` and accept `limit` (1–100, default 50) and `offset`
(default 0). Episode lists support `station_id` and `severity` (current severity);
`/api/alerts` additionally accepts `status=ACTIVE|RESOLVED`. An unknown station
filter returns an empty page. Resolved episodes have current severity NORMAL and
retain their highest severity separately. Transition pages include previous/new
severity, depth, telemetry ID/sequence, and UTC timestamp. Episode details include
trigger/latest telemetry IDs/sequences and depths, trigger/last-transition times,
and optional resolution time. Use the existing `/docs` OpenAPI schemas for fields.

The existing startup `Base.metadata.create_all()` creates the two new tables in
existing development databases. No old telemetry is backfilled/replayed: persistent
history starts with newly accepted samples after this version is deployed. Restarting
the service preserves episodes; it does not reclassify them without new valid data.
Manual/demo web alerts are not imported. Production migrations, calibrated hysteresis,
notifications, WebSockets, and resident mobile alert integration remain separate work.
**No push notification delivery or production-readiness claim is included.**

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
range 1–100), and `offset` (default 0, minimum 0). The general list additionally
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
range 1–100) and `transition_offset` (default 0, minimum 0) to page the timeline.
Transitions follow chronological ingestion order, with the internal transition
ID breaking timestamp ties. Their public fields are only `previous_severity`,
`new_severity`, `water_depth_cm`, and `transitioned_at`. A direct
NORMAL → EVACUATE transition is returned as recorded. Telemetry IDs, telemetry
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

Flutter currently has demo notification/history presentation and is unchanged
by this API addition. Its next integration can use the existing authenticated
request client, map this contract, and handle loading, unavailable, active, and
resolved states explicitly. **Push notifications, subscriptions, geofencing, and
delivery/read receipts are not implemented.**
