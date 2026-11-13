# F28/F29 — recoverable depth history and explicit schema lifecycle

Implemented in this checkout. No firmware upload, filesystem formatting, live
database migration, broker reload, deployment or external delivery was performed.
See [RESULTS.md](RESULTS.md) for observed verification and remaining acceptance.

## Depth history contract

The live stream still targets one report every two seconds. Separately, the
firmware journals one observation every **10 seconds**, keeping **360 unacknowledged
observations** (about one hour at that cadence). These are configurable development
defaults, not an approved power/endurance budget. Records hold original observation
JSON, measured UTC or explicit null, 64-bit uptime, boot/sequence identity,
configuration hash, quality and local profile. Credentials are excluded from flash.

Storage uses dedicated `/agapay-depth/` files in an **already provisioned LittleFS
partition**. It never formats or changes the partition table/NVS. An unmounted,
missing or incompatible filesystem reports history unavailable and leaves sensing
running. Provisioning a new filesystem requires a separately reviewed device backup
and partition procedure; no upload/format command is automatically executed here.

Flash and journal scanning run in a separate task from acquisition and networking.
The journal task has a 12 KiB stack and a 360-entry index. Each fixed record is
roughly 1.2 KiB; reserve at least 0.5 MiB plus filesystem headroom. Writes use a
temporary file and rename; slot CRCs reject corrupt/truncated records at restore.
Actual brownout endurance and worst-case flash latency remain device tests.

At capacity, a successful new commit replaces the oldest pending slot. Per-boot
diagnostics report pending/capacity, cadence, evictions, corruption, write failures
and acquisition-to-journal handoff gaps. These counters are explicitly per boot;
they are not a lifetime completeness claim. Failed commits retain the old indexed
slot. A partially written temporary file is never replayed. Synchronized records
retain real timestamps; without synchronized UTC, uptime/boot remain available but
the server labels the observation `journal_unsynchronized`. It never dates the
measurement using reconnect time.

Replay publishes at most one observation per second, in addition to up to 30 live
reports/minute, under the shared default 120/minute ingress budget. The MQTT envelope
adds `delivery_mode: "backfill"`; HTTP callers use
`POST /api/telemetry?delivery_mode=backfill`. Historical ingestion cannot update the
current measurement cursor, heartbeat, firmware status, alert episode or outbox.
Configuration disagreement and exercise local outputs retain separate historical
review dispositions. The bounded measured-time report includes synchronized history
and keeps missing buckets empty; it does not infer uninterrupted coverage.

The backend publishes a non-retained QoS 1 ACK to
`agapay/stations/<station>/telemetry-ack` **after database commit**. The receipt names
station, config version, boot ID, sequence and the complete original telemetry object. The device compares both the key and observation before removing a slot. Exact immutable retries receive the
same ACK; conflicting content, revoked credentials, retained ingress, persistence
failure and rejected identities receive none. A delayed ACK cannot erase a newer
occupant of a wrapped slot. QoS 0 socket writes alone never remove a journal record.
Update both the backend and reviewed broker ACL before coordinated firmware rollout.
The production ACL grants devices read access only to their own ACK topic; devices
cannot publish ACKs. Broker credentials remain independently provisioned.

Recommissioned identities/configurations can leave old records rejected at the head
of the backlog. Diagnose and review/export those records deliberately; the firmware
does not rewrite their identity or silently delete them to get an ACK.

## Ordered migrations and startup

`python -m app.migrations` checks readiness without creating schema or seeding.
`--apply --writers-stopped --backup-confirmed` explicitly applies the ordered,
preserving legacy steps and the frozen baseline. The migration ledger records
revision, checksum and UTC completion time. A process lock serializes SQLite
migrators; a PostgreSQL advisory lock serializes PostgreSQL migrators. All writers
must still be stopped. Failed steps are never stamped; existing scripts are
idempotent where supported. Inspect failures before retrying; do not delete a lock
until its owner is known to have stopped.

The baseline contains reviewed SQLite and PostgreSQL DDL, independent of serving
model `create_all`. Existing legacy SQLite upgrades preserve IDs and foreign keys.
Unrecognized/partial layouts stop for review. An unreviewed legacy PostgreSQL layout
is not automatically converted by SQLite-specific preservation scripts.
New deployments and already compatible PostgreSQL schemas use frozen PostgreSQL DDL.
Do not edit applied snapshots or preservation scripts: add a new numbered revision
and upgrade/restore tests for future schema changes.

API startup, offline administrator creation and production preflight require the
current ledger. `/ready` returns 503 for unavailable schema or version drift; `/health`
remains a basic database connectivity probe. Startup never calls `create_all`, runs
migrations, creates a demo station or rewrites old demo metadata. The legacy
`AGAPAY_SEED_DEMO_DATA` flag does not cause serving-time inserts.

From `agapay-backend`, first verify a private copy (destination must be NEW):

```powershell
python -m app.verify_upgrade --source agapay_dev.db --copy C:\private-backups\agapay-upgrade-check.db
```

This opens the source read-only, takes a consistent SQLite backup, upgrades only
the copy and verifies every original table/row/column, integrity and foreign keys.
The reviewed identity migration fills legacy null session public IDs; this specific
backfill is excluded from the original-value comparison. Copy files contain personal
account/SOS data: retain them privately and never commit them.

After a reviewed backup/restore check and stopped writers, the explicit local
application sequence is:

```powershell
python -m app.migrations --apply --writers-stopped --backup-confirmed
python -m app.migrations
python -m app.create_admin
# Optional DEVELOPMENT ONLY; review app/seed.py before explicitly updating demo metadata.
python -m app.bootstrap_demo --apply
python -m uvicorn app.main:app --reload
```

Existing installations skip administrator bootstrap when setup is complete. Nothing
in this implementation runs this checklist against the existing development DB.

## Managed PostgreSQL deployment and restore

`agapay-backend/deploy/compose.production.yaml` is a Linux-host deployment template
using an **external managed PostgreSQL**, a local HTTPS reverse proxy, two HTTP
workers and one dedicated MQTT owner. Production serving requires
`postgresql+psycopg`, `sslmode=verify-full` and an explicit root CA. It rejects
development SQLite and an HTTP service that starts its own MQTT subscriber. The HTTP service explicitly uses external-subscriber mode. A credential-free shared worker heartbeat expires after 15 seconds; accepted MQTT receipts remain independently dated in the database. Identity and general
delivery workers use bounded batches and an explicit `delivery` profile. The SOS
worker remains drill-only. No PostgreSQL container or auto-initializing demo database
is supplied. Review the existing identity/SMTP/origin template as well as
`deploy/production.env.example`; protect real secrets outside Git. The reverse proxy overwrites the HTTPS scheme assertion, clears forwarded client addresses, and Uvicorn accepts proxy headers only from the configured loopback peer. BFF client identity retains its separate signed contract. The image runs
without root and the service filesystem is read-only except the rain journal volume.

Migration is an explicit administration job before serving. The first administrator
is bootstrapped offline after migration and before production workers start. Set
up the volume's UID 10001 permissions, the explicit same-host HTTPS proxy peer, managed backup retention/PITR and restoration
credentials, trust anchors, unique broker identity/ACL and reverse proxy first.
Do not enable delivery services during restore verification.

To move SQLite data, migrate a private SQLite copy first. Set
`AGAPAY_RESTORE_DATABASE_URL` privately to a reviewed **empty** PostgreSQL target,
then use the explicit restore command:

```powershell
python -m app.transfer_database --source-copy C:\private-backups\agapay-upgrade-check.db --apply-to-reviewed-empty-target
```

The restore rejects populated/unknown targets and unreviewed source tables before migration, holds a consistent source snapshot and exclusive target table locks, inserts application
rows in one transaction, verifies bounded-memory per-table multiset fingerprints
and counts, and advances generated sequences. The target keeps its own migration
ledger. Credentials/row contents are never printed. A failed application import
rolls back; PostgreSQL sequence increments are not transactional and can leave harmless
gaps. Review a managed PostgreSQL backup restore into another isolated target, compare
accounts/SOS/alerts/outbox and rain journal, exercise CAS/concurrency and prove worker
delivery is disabled before any cutover. Keep the original deployment available for
a reviewed rollback; never restore over a live database as an automatic recovery.

`tests/test_postgres_restore.py` is opt-in: it only accepts an explicit loopback
`agapay_test_*` database and refuses any existing tables. It leaves restored test
data for inspection. No PostgreSQL runtime was available in this session, so real
PostgreSQL restore/concurrency and managed-provider acceptance remain pending.
