# Restored-delivery recovery (R2 P0)

Restoring an older database backup must never re-send flood or exercise notifications whose
outcome became unknowable after the backup was taken.

## Failure mechanism (confirmed on PostgreSQL 16)

1. A backup captures delivery `D` as `PENDING`.
2. The live worker sends `D` (provider accepted) after the backup.
3. The database is restored from that backup, so `D` is `PENDING` again.
4. Before this change, an unmodified worker sent `D` a second time, with the same delivery key.
   Firebase Cloud Messaging has no idempotency key, so this is a real duplicate push.

The existing encrypted-restore tool rewrote states (`PENDING` → `SUPPRESSED`), but only when
that tool was used. A plain `pg_restore`, a point-in-time recovery or a VM snapshot rollback
bypassed it entirely.

## Policy

- **No blind replay.** Exactly-once external delivery is **not** claimed. Database uniqueness
  cannot prove it, and FCM gives no such guarantee.
- **Single gate.** A delivery reaches a provider only through a claim under the single `ACTIVE`
  delivery generation. The gate applies to operational, manual-exercise and sensor-exercise
  workers, at three points:
  - batch start;
  - the claim transaction;
  - immediately before the provider call. The exercise provider gate also re-checks.
- **Fail closed.** No claim is made when any of these is true:
  - the generation table is missing or empty;
  - more than one generation is open;
  - the generation is `RECOVERING`;
  - the database identity changed;
  - the external ledger is missing, unreadable or ahead;
  - production is running without `AGAPAY_DELIVERY_LEDGER_PATH`.
- **Holds.** Declaring recovery opens a new `RECOVERING` generation and supersedes the old
  one. The rows below get a hold that records their original state, attempts, result and
  timestamps:

  | Delivery kind | States held |
  |---|---|
  | Operational | `PENDING`, `PROCESSING`, `UNKNOWN`, and retry-scheduled `FAILED`, unless an operator already closed it |
  | Exercise (manual and sensor) | `PENDING`, `PROCESSING`, `UNKNOWN` |

  Delivery rows are **not rewritten**. `SENT`, `TESTED`, `SUPPRESSED`, `REJECTED` and
  permanently `FAILED` rows are terminal and are not held.
- **Holds are never released for resend.** An administrator decision (`provider_accepted`,
  `not_delivered`, `outcome_unknown`, `superseded`) records evidence (kind, SHA-256 of the
  retained evidence, reason, actor, time) and closes the hold. Decisions are final and
  version-checked. Every action is appended to `delivery_recovery_events`, which is
  append-only.
- **New work.** After activation, only deliveries without a hold are claimable. They pass every
  normal freshness check at claim time: superseded transition, TTL expiry, device revision,
  consent, session expiry, allowlist and station arming.
- **Ingestion and local alarms continue.** Readiness does not depend on the delivery fence. A
  `DELIVERY_RECOVERY_FENCED` or `DELIVERY_RECOVERY_UNDECIDED` warning is reported instead.

### State transitions

```
generation:  ACTIVE --declare--> SUPERSEDED     (in the same transaction, the new one is RECOVERING)
             RECOVERING --activate--> ACTIVE   (binds database identity, anchors the ledger)
hold:        undecided --decide--> provider_accepted | not_delivered | outcome_unknown | superseded   (final)
delivery:    unchanged by recovery; a claim in flight when recovery is declared ends SUPPRESSED/recovery_fenced
```

## Restore detection

Detection does not rely only on rows inside the restored database.

- **PostgreSQL database identity.** The cluster `system_identifier` and the database OID are
  bound at activation. A restore into another database, cluster or re-created database no
  longer matches.
- **External ledger.** `AGAPAY_DELIVERY_LEDGER_PATH` is a directory on the worker host, outside
  the database and its backups.
  - Each claim advances the generation's `claim_seq` while holding the generation row lock. It
    writes `{token, seq}` to that process's own ledger file (atomic replace plus fsync) before
    the claim commits and before any provider call.
  - A restored database is refused at its next claim, because it carries either an older
    generation token or a `claim_seq` at or below the ledger high-water mark. This also covers
    a restore into the same database and physical or point-in-time restores.
- **Unwitnessed environments.** If the ledger is missing in production, delivery is refused.
  Outside production the ledger is optional; without it, only the identity and generation
  checks apply.
- **Known false positive (fail closed).** If a commit fails after the ledger write, the ledger
  ends up ahead of the database and further claims are refused until an operator declares and
  activates a new generation.

### Ledger storage requirements (verify before production)

- **Location.** A local, durable, non-temporary filesystem on the worker host. It must not be
  tmpfs, a container's ephemeral layer, or a directory inside the database data directory.
- **Never restore it with the database.** It must not be part of the database backup set, and
  it must never be rolled back to an older copy: a restored ledger defeats detection. Protect
  it with redundant storage instead of point-in-time backups.
- **Access.** Writable only by the service account that runs send-capable workers.
- **Single host, enforced.** Every ledger file records the host that wrote it. A worker refuses
  to claim if any entry came from another host. Multi-host delivery is **unsupported** until its
  coordination guarantees are demonstrated, so run every send-capable worker on one host.
- **Permissions, enforced on POSIX.** Workers refuse to claim if the ledger directory is writable
  by group or others; use mode 0700, owned by the service account. On Windows, restrict the
  directory's ACL to the service account; this is not checked automatically.
- **Writes.** Each process writes only its own file: temp file, fsync, atomic replace, then on
  POSIX an fsync of the directory. No cross-process lock is needed because the high-water mark
  is the maximum over all files.
  - Verified with four concurrent OS processes.
  - On Windows, a transient sharing violation while a peer replaces a file is retried for up to
    about 0.5 s; anything persistent fails closed.
- **Size.** Retired anchors accumulate under `retired/`, one small directory per activation.

### Ledger failure and recovery

| Condition | Worker behaviour | Operator action |
|---|---|---|
| Directory missing (`AGAPAY_DELIVERY_LEDGER_PATH` unset in production, or disk lost) | Refuses every claim | Restore storage, then declare and activate a new generation. Activation re-anchors the ledger; all unsettled work is held first. |
| Entry unreadable or corrupt | Refuses every claim | Do not hand-edit. Investigate the storage, then declare and activate. |
| Token differs from the database generation | Refuses every claim | An older database backup was restored: declare, reconcile, activate. |
| Claim sequence at or behind the ledger | Refuses that claim and rolls it back | Same as a restored database. |
| Entry from another host | Refuses every claim | Consolidate send-capable workers on one host, then declare and activate. |
| Directory writable by others (POSIX) | Refuses every claim | Fix ownership and permissions. |
| Database commit failed after the ledger write | Next claim is refused (false positive) | Declare and activate; no delivery was sent. |

- **Evidence is kept.** Activation moves earlier ledger files into `retired/` and never deletes
  them. Holds and `delivery_recovery_events` are never deleted by recovery.
- **Nothing is replayed.** No path re-queues a held `PENDING`, `PROCESSING` or `UNKNOWN`
  delivery.

## Restoration procedure (operator)

1. **Quiesce.** Stop the notification worker, the exercise runner and other writers.
2. **Identify the source.** Record the backup file, its SHA-256, the source database and the
   intended recovery point.
3. **Restore into an isolated, empty target.** The preferred tool is
   `python -m app.recovery restore`. It verifies the backup, quarantines restored data
   (`RecoveryFence`) and declares a `restore` generation holding the uncertain work. After any
   other restore method, declare recovery manually:
   `python -m app.delivery_recovery declare --admin-id N --reason "..." --workers-stopped`.
4. **Verify the target.**
   - `python -m app.migrations` (schema current)
   - `python -m app.delivery_recovery status` (generation `RECOVERING`)
   - `python -m app.delivery_recovery holds`
5. **Reconcile.** For each hold, compare against provider exports, app receipts and audit
   records, then decide it via `POST /api/delivery-recovery/holds/{id}/decision` or
   `python -m app.delivery_recovery decide ...`. Nothing is resent.
6. **Recheck current state.** Review current device registrations, consent, station
   configuration and notification policy. Devices disabled by the restore tool must
   re-register.
7. **Release restored data** after privacy withdrawals are reconciled:
   `python -m app.delivery_recovery release-restored-data --admin-id N --reason "..."`. The API
   and ingestion can now serve, but delivery stays fenced.
8. **Authorize new-generation delivery** on the worker host:
   `python -m app.delivery_recovery activate --admin-id N --reason "..." --workers-stopped`.
   This refuses while holds are undecided unless `--defer-reconciliation` is given, and
   deferred holds stay blocked.
9. **Evidence.** `delivery_recovery_events`, `privacy_events` and the restore report record
   operator ids, timestamps, decisions and the backup hash.

An unplanned worker or database restart without a restore changes neither the identity nor the
ledger, so nothing is quarantined.

## Operational versus exercise

Both use the same generation gate and hold table, with separate `kind` values:

| Kind | Delivery table |
|---|---|
| `operational` | `notification_deliveries` |
| `exercise_manual` | `exercise_deliveries` |
| `exercise_sensor` | `exercise_sensor_deliveries` |

Exercise deliveries remain `EXERCISE_TEST`. No recovery path creates, converts or re-queues a
delivery of the other kind.

After a restore, these exercise deliveries stay ineligible, through the normal worker checks
plus the exercise provider gate:
- expired or terminated sessions;
- revoked recipients;
- withdrawn consent;
- disabled registrations;
- disarmed stations.

## Not covered

- Identity mail (SMTP) keeps its existing restore quarantine (`SENDING` → `UNKNOWN`,
  `PENDING` → `SUPPRESSED`); it is not part of this generation gate.
- A recovery declared while a provider call is already in progress cannot stop that call. This
  is why the procedure quiesces workers first.
