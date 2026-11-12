# Privacy, incident and recovery runbook

Status: development procedure to rehearse; real owners, coverage, privacy/legal review and deployment evidence are pending. Do not announce operational coverage or send real incident messages from a software drill.

## Deployment and maintenance

Use a reviewed copy first. Keep accounts, incidents, subscriptions, outbox and rain ACK state; never reset/reseed a deployment to satisfy a migration test. Back up before the existing offline migration command. The new additive revision is `0005_privacy_recovery`; serving only verifies it.

From `agapay-backend`:

```powershell
python -m app.privacy_retention --limit 100
```

This inspects a bounded batch without deleting/redacting anything. Review its counts, holds, uncertain mail and actual policy hash. In an approved maintenance window with all writers stopped and a verified backup:

```powershell
python -m app.privacy_retention --apply-with-writers-stopped --limit 100
```

Repeat bounded passes and verify representative protected records until no eligible records remain. Do not write personal samples into reports. Production apply requires the current external governance record. The command does not install a scheduler: the organization must own maintenance frequency/monitoring and configure its supervised job/maintenance window. Holds or uncertain identity mail are reviewed exceptions, not a reason to silently discard evidence or reset mail for replay.

Admin API/UI case review uses expected versions and reason/evidence codes. Never retry a stale review automatically. The hold endpoint uses `PATCH /api/privacy/admin/holds/{user_id}` with expected version, active flag, aware expiry, reason code and protected evidence SHA-256. Review access with `GET` then `POST /api/privacy/admin/access-review`; current password and unchanged inventory hash are required. Owner exports are bounded pages, not a promise that all retained organizational evidence has been delivered.

## Encrypted backup

Use an existing private destination directory and reviewed private temporary directory on encrypted storage. Temporary snapshot/archive staging contains plaintext while the command runs; OS directory permissions and underlying disk encryption must be verified, particularly on Windows where POSIX mode bits are not a complete ACL policy. Cleanup is not a guarantee of physical SSD erasure. Backups/PITR need real storage encryption, retention enforcement and separate protected key escrow.

Inject `AGAPAY_BACKUP_KEY` as a base64-encoded random 32-byte secret through the organization's secret manager. Do not put it in a command argument, repository, screenshot, log or backup bundle. Retain key/version lookup and rotation/escrow evidence separately; never retire a key while a retained backup still depends on it. Identity/MFA encryption keys and provider credentials are separate recovery dependencies and are not included in the archive. Set `AGAPAY_RECOVERY_TEMP_DIRECTORY` to the reviewed private staging directory.

For offline reviewed SQLite copies:

```powershell
python -m app.recovery backup --source-copy C:/protected/copies/application.db --rain-copy C:/protected/copies/rain.db --writers-stopped --output C:/protected/backups/unique-id.agapaybak
python -m app.recovery restore --backup C:/protected/backups/unique-id.agapaybak --new-directory C:/protected/drills/unique-new-restore
```

Use actual existing protected paths. Output names must be new; no deployment is overwritten. The SQLite backup API captures WAL-consistent files; cross-store consistency still requires stopped/quiesced writers. If rain ingestion is enabled, include its actual independent journal and archives in the recovery inventory. Model artifacts, model/config approvals, broker ACLs/certificates, service environment, key escrow and vendor settings also require separately protected, integrity-checked recovery records.

For managed PostgreSQL copies/drills, configure external libpq service/password files with reviewed permissions and validated TLS. Never put connection secrets in CLI arguments. Choose services explicitly:

```powershell
python -m app.recovery backup --pg-service agapay_reviewed_copy --rain-copy C:/protected/copies/rain.db --writers-stopped --output C:/protected/backups/unique-pg.agapaybak
python -m app.recovery restore --backup C:/protected/backups/unique-pg.agapaybak --pg-service agapay_empty_drill --new-directory C:/protected/drills/unique-pg-restore
```

Install reviewed `pg_dump`/`pg_restore` versions compatible with the server. Backup holds application tables against writes during its offline dump. Restore requires a completely empty target, imports transactionally and verifies schema/row fingerprints before quarantine. Roles/ownership/grants are not copied blindly; review least-privilege deployment roles separately. A failed target is diagnostic material and must not be served. Real-engine PostgreSQL recovery, TLS, volume permissions, capacity and provider boundaries require execution on the intended platform; local SQLite tests do not establish them.

The development targets are **RPO 15 minutes, RTO 4 hours**, pending agreement. An offline package command does not establish a production backup schedule. For a continuously operating managed PostgreSQL service, configure and test encrypted managed snapshots/PITR/WAL retention and monitoring rather than assuming repeated write-blocking offline dumps can meet availability needs. Measure data-loss boundaries and full workflow recovery, including broker/rain history, artifacts, credentials, privacy withdrawals and device registration. The report's package capture age and decrypt/verify/quarantine time measure only that procedure. A supplied SQLite copy may already be old; actual source cutoff/data loss remain unknown until independently reconciled with production checkpoint evidence. They are not complete service RPO/RTO.

## Restore quarantine and release

1. Restore into a new isolated environment with outbound providers blocked. Authentication/integrity failures must not create a target. Verify report/checksums, original incident/episode/outbox/rain-ACK history, schema and database integrity. Reconcile any failed/partial target privately; never point services at it.
2. Confirm old bearer sessions and push tokens are revoked. PENDING/FAILED notifications become SUPPRESSED, PROCESSING becomes UNKNOWN, and existing UNKNOWN/SENT records remain as history. Pending mail/action links are invalidated. The API and delivery workers refuse the quarantine fence. Never bulk reset these records to PENDING.
3. Apply the **current external privacy withdrawal/erasure/hold ledger** to the old snapshot before permitting reads. Reconcile changes made after its cutoff, including erased accounts, local/third-party copies and subscriptions. Keep this ledger protected and independently recoverable; storing it only inside an old backup cannot prevent resurrection.
4. Recover and verify the exact approved artifacts/configuration, identity encryption keys and least-privilege roles. Inspect restored active incidents as unresolved historical context, compare current physical observations and authority notices, and do not infer safety from a restored green panel.
5. Reconcile ambiguous provider acceptance with actual evidence; re-provision only deliberate current devices/sessions. Record restoration, privacy reconciliation, operator/issuer readiness and network/provider tests. Confirm the actual support/response roster and fallback contacts.
6. An authorized recovery owner performs a separately reviewed database change releasing the single `recovery_fences` record only after these steps and the current organizational attestation are recorded. There is intentionally no automatic fence-clear or resend command. Preserve the backup hash and a new append-only privacy event referencing the protected review evidence. Start services using the normal production preflight and inspect readiness before allowing residents back in.

## Incident response

- **Detect/triage:** capture UTC time, affected capability, correlation IDs and evidence location; assign the real incident commander and privacy reviewer. Keep public observations separate from confidential personal data. Preserve protected evidence without copying raw fixes/tokens/passwords into chat/logs.
- **Contain:** restrict affected credentials/accounts/service paths, isolate compromised infrastructure, suspend uncertain delivery and preserve outbox/incident history. Coordinate safe response fallbacks with actual operators; do not resolve SOS or replay notifications as a containment shortcut.
- **Assess:** identify affected people/data/recipients/time range, active holds and possible disclosure, vendor boundaries and backup integrity. The responsible privacy/legal organization determines applicable notifications, contents and deadlines using current requirements. The internal development case target is not a regulator reporting deadline.
- **Recover:** use the quarantined restore procedure, rotate/re-provision compromised secrets, verify current privacy withdrawals and explicit operator readiness, then record release evidence. Keep ambiguous outcomes ambiguous until reconciled.
- **Learn/close:** approve corrective actions and renewed PIA/access/retention review; update user-facing instructions from verified facts, and test the failed workflow again. Retain an accountable owner for each action.

## Required drill evidence

Record source cutoff, actual loss window, event/row integrity, rain ACK continuity, relevant artifact/config hashes, key availability, start/finish times, workflow readiness, provider-boundary results, privacy-withdrawal replay and participant/owner signatures. Local synthetic tests are listed separately in RESULTS.md. No real on-call roster, contractual SLA, external deletion or production disaster drill has been established by those tests.
