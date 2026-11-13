# Installation and maintenance

Use a maintenance window for upgrades. Stop all API, ingestion and background writers, preserve their configuration privately and take verified database/journal backups. Never reset or seed existing data. Restart processes after a restore because journal initialization is cached per inode/process. Apply the main database migration through `python -m app.migrations --apply --writers-stopped --backup-confirmed` only after a restore rehearsal. The new HEAD is `0003_delivery_evidence`.

For a main SQLite database, the existing copy verifier opens the original read-only, upgrades a new destination and compares all original rows/columns without printing them:

```powershell
# From agapay-backend. Each destination must be new.
.venv-auth/Scripts/python.exe -m app.verify_upgrade --source agapay_dev.db --copy ../data/acceptance/main-upgrade-copy.db
```

## Rain journal upgrade and recovery

Version 0 is the legacy raw journal; version 3 adds indexes and transactional rollups. New ordinary ingestion may create an empty v3 journal but never upgrades an existing legacy journal implicitly. `RAIN_SCHEMA_MIGRATION_REQUIRED` prevents rain readiness until the reviewed journal is upgraded. Readers do not initialize missing files.

The following is a copy-first PowerShell rehearsal. Replace the first path with the actual configured rain journal. The source connection is read-only; destination creation is exclusive. The temporary copy can contain device identity metadata, so protect its directory and exclude database artifacts from Git.

```powershell
$rainSource = (Resolve-Path ../data/live_rain/rain-events.sqlite3).Path
$rainCopy = [IO.Path]::GetFullPath('../data/rain-upgrade-review.sqlite3')
.venv-auth/Scripts/python.exe -c 'import pathlib,sqlite3,sys; from contextlib import closing; source=pathlib.Path(sys.argv[1]).resolve(); target=pathlib.Path(sys.argv[2]).resolve(); target.open("xb").close(); original=sqlite3.connect(source.as_uri()+"?mode=ro",uri=True); copy=sqlite3.connect(target); original.backup(copy); copy.close(); original.close()' $rainSource $rainCopy
.venv-auth/Scripts/python.exe -m app.rain_journal upgrade --path $rainCopy
.venv-auth/Scripts/python.exe -m app.rain_journal verify --path $rainCopy
.venv-auth/Scripts/python.exe -m app.rain_journal backup --path $rainCopy --destination ../data/rain-backup-review
.venv-auth/Scripts/python.exe -m app.rain_journal verify-backup --path ../data/rain-backup-review
.venv-auth/Scripts/python.exe -m app.rain_journal restore --path ../data/rain-backup-review --destination ../data/rain-restored-review
```

Check `$LASTEXITCODE` after every command and stop on failure. A raw legacy backup must include a consistent SQLite backup, not an unsynchronized copy of the database while its WAL is active. After the rehearsal and restoration checks succeed, explicitly upgrade the stopped operational journal using its configured path. Do not substitute the rehearsal copy for the operational file without reviewing the resulting paths and archive ownership.

For ongoing v3 backups, `backup` uses SQLite's online backup API and copies every cataloged immutable archive into a portable bundle. It rewrites archive paths only in the backup copy, fsyncs files and publishes the completion manifest last. `verify-backup` checks the manifest, path containment, all archive checksums, SQLite integrity/foreign keys, archive event/gap counts and raw-plus-archive lifetime totals. `restore` is create-only and verifies again after copying. Keep the source and archives until restore checks pass. Storage/backup encryption, ACLs and off-host redundancy are deployment responsibilities.

## Retention operation

Defaults are `AGAPAY_RAIN_RAW_RETENTION_DAYS=30`, `AGAPAY_RAIN_ARCHIVE_BATCH=5000` and a protected `AGAPAY_RAIN_ARCHIVE_DIRECTORY`. Archival is an explicit command; no task was scheduled against existing data. Configure a deployment maintenance timer only after its volume, I/O latency, free-space reserve and backup destination have been measured. At a five-second cadence, one station adds about 17,280 heartbeat rows/day. The synthetic 30-day single-station database was about 492 MB including indexes and five years of generated hourly rows; this is not a fleet sizing guarantee. Reserve capacity for WAL, archives and verification copies as well as the main database.

```powershell
# Run on the configured journal only after the copy rehearsal.
python -m app.rain_journal archive --path /var/lib/agapay/rain.db --destination /var/lib/agapay/rain-archives --retention-days 30 --limit 5000
python -m app.rain_journal verify --path /var/lib/agapay/rain.db
```

Each archive invocation publishes at most one bounded batch and reports counts. Drain older backlog in controlled batches with room for live ingestion; stop on any failure or resource pressure. This requires a writable protected persistent volume. Archive-first then catalog/delete commit means a crash may leave an unreferenced `.partial` or completed archive, while original raw rows remain committed. Never automatically delete orphan files: stop maintenance, compare the hot catalog and backups, verify the file, and quarantine it for review. A committed catalog always points to a published verified file. Missing/corrupt referenced files block old duplicate ACKs; restore the verified file before retrying. No UNKNOWN/outbox replay operation belongs in this repair.

Hourly summaries retain source and calibration versions, exact tip counts and receive-coverage gaps. Floating-point millimeter sums are compared with numeric tolerance (tests normalize to eight decimals; integrity uses relative `1e-9`/absolute `1e-6`). Do not reinterpret recovery totals as known occurrence times or use an anchor outside retained raw coverage. A managed-store migration is deferred until equivalent commit/ACK, duplicate, fsync, transaction and backup guarantees are tested.

## Delivery operations and privacy

Use `app.worker_service notifications` under the existing `deploy/compose.production.yaml` delivery profile for continuous supervision. `app.notification_worker --limit 50` remains a one-batch operator tool. Configure provider credentials privately and deliberately enable the profile; these changes leave the default provider disabled. Add notifications to `AGAPAY_OPERATIONS_REQUIRED` only when the deployment promises that service. Install a real receiver/duty route for the existing private metrics and workflow alert rules. A restart of a supervised worker does not reclaim PROCESSING.

The default intent lifetime is 300 seconds (`AGAPAY_NOTIFICATION_TTL_SECONDS`, 60–3600). Captured deadlines are persisted; a shorter citywide expiry also applies. The SDK transport receives Android TTL/APNS expiry. Stale intent is suppressed before a provider call. Receipt capabilities expire after `AGAPAY_NOTIFICATION_RECEIPT_DAYS` (default 7, range 1–30); the mobile encrypted queue independently retains at most seven days/200 callbacks. Increasing the server window does not extend client retention.

In **System Health → Notification delivery evidence**, filter UNKNOWN/PROCESSING and inspect queue time, expiry, recorded attempts, provider references and independently recorded callback stages. Operators see only authorized jurisdiction; only administrators may reconcile. Queue age over 60 seconds, stopped worker or ambiguous delivery has a specific workflow fault. A fresh PROCESSING attempt cannot be reconciled during that 60-second window; a very slow provider call can still finish later, so review external evidence before closing a stale attempt.

Record a decision only after inspecting actual evidence:

- Provider accepted/rejected requires a provider record. Paste an external record reference; the browser submits its SHA-256 digest, never the raw reference. Retain the source record in the approved evidence system.
- Close without resend records an explicit reviewed decision without claiming acceptance or receipt.
- Completed fallback/contact action records something an operator has actually done under the agreed response procedure. It stops automatic attempts but remains flagged for follow-up; it does not send SMS, call anyone, dispatch responders or prove phone receipt.
- A 409 or newer version locks the form. Refresh manually, inspect changed evidence and enter a new decision. Never silently replay a stale mutation.

Do not put tokens, passwords, phone numbers or private message contents in review reasons. UNKNOWN/PROCESSING transport history remains intact; reviews and callback rows are append-only application evidence. A recorded Opened or explicit Acknowledged does not invent a missing Received callback. Neither resident acknowledgement nor a provider response establishes evacuation, rescue, comprehension or authority-issued action.

Delivery audience is captured from existing station/verified-area subscriptions, with explicit audited citywide authority overrides. Optional receipt consent does not subscribe someone or override delivery preference/OS permission. Consent changes revoke old capabilities; natural API expiry does not withdraw enabled push registration. Explicit device/account revocation does. Fallback contacts, channels, consent and duty ownership must come from verified deployment procedures; none is invented by this console.

## Remaining acceptance on the intended deployment

Use a new isolated drill event and an expressly authorized phone. Leave historical ambiguous deliveries untouched. Record queued, actual provider acceptance/reference, foreground callback, background/terminated behavior, opened callback and explicit resident acknowledgement separately. Repeat with consent off/withdrawn, revoked device, offline cold restart and expired queued intent. Confirm no missing callback is labeled delivered. Firebase [delivery reporting](https://firebase.google.com/docs/cloud-messaging/understand-delivery) and [Flutter callbacks](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages) describe the limits of those observations.

Repeat interrupted-send and concurrent review/callback/withdrawal tests on the deployed PostgreSQL engine; verify supervision, alert receiver, archive volume durability and off-host restore. Local SQLite/synthetic tests do not substitute for these checks. No deployment, production migration, provider call, physical phone test or firmware flash was performed here.
