# Exercise-evidence retention: PROPOSED engineering policy (not approved)

**Status: proposal for review.**
- **Not a legal determination.** The 30-day figure is an engineering default, not a legal or
  regulatory requirement.
- **No retention job exists.** No destructive retention job is implemented or scheduled. None may
  run against real data until an approved policy (owner, period, legal basis) is recorded.

## Records in scope

These come from migrations 0006 and 0007:

| Table | Content | Personal data |
|---|---|---|
| `exercise_sessions` | Administrator, reason (free text), limits, expiry, termination | Staff user ids; the free-text reason may contain names |
| `exercise_recipients` | Session ↔ device allowlist | Device id (linked to a resident) |
| `exercise_deliveries`, `exercise_sensor_deliveries` | Test sends, state, outcome | Device id; no message body beyond the fixed test text |
| `exercise_sensor_triggers` | Station, telemetry id, depth, tiers, ingress identity | No personal data |
| `exercise_station_arms` | Station arming by an administrator | Staff user id |
| `exercise_device_consents` | Resident opt-in per device revision | Resident user id and device |

Exercise actions are also recorded in governance and mutation audit tables, which have their own
audit retention. Recovery holds (migration 0008) reference exercise delivery ids without a
foreign key.

## Proposed rules

1. **Eligibility.** A session is eligible when it ended, by termination or expiry, more than
   30 days ago, **and** all of the following hold:
   - no delivery of the session is `PENDING` or `PROCESSING`;
   - no recovery hold, decided or not, references any of its deliveries (recovery evidence);
   - no device owner of its deliveries has an active privacy preservation hold;
   - no delivery-recovery generation is `RECOVERING`, which freezes all exercise retention.
2. **Deletion unit.** The whole session, deleted in this foreign-key order:
   1. `exercise_sensor_deliveries`
   2. `exercise_sensor_triggers`
   3. `exercise_station_arms`
   4. `exercise_deliveries`
   5. `exercise_recipients`
   6. `exercise_sessions`
3. **Always retained.** Governance and mutation audit rows, which keep their own retention.
   Recovery holds and `delivery_recovery_events`. Telemetry: deleting triggers and arms only
   releases their references; telemetry follows its own policy.
4. **Consents.** Active consents follow the device registration. Revoked consents are eligible 30
   days after revocation. Privacy erasure already deletes a resident's consents immediately.
5. **Expired sessions.** They are never resumed. Pending sends for an ended session are
   suppressed by the worker (`session_expired`) and stay as evidence until eligible.
6. **Execution.** A future, separately approved job would run offline in bounded batches with a
   dry-run report first, and record counts in `privacy_events`.

## Validation

The validation used synthetic data on disposable PostgreSQL 16, with a scratch script; no
application code was added. Five sessions were seeded:
- one ended 40 days ago;
- one ended 10 days ago;
- one ended 40 days ago with a decided recovery hold;
- one ended 40 days ago whose resident had an active privacy hold;
- one live.

Results:
- Only the first was eligible.
- Deleting the session first was refused by the foreign keys; the proposed order deleted exactly
  one row from each table.
- The other four sessions, both consents and the recovery hold remained.
- The released telemetry became deletable, while telemetry referenced by retained sessions
  stayed protected.
- With a `RECOVERING` generation open, nothing was eligible.

## Approvals outstanding

- **Owner and period.** A data owner, a retention period and a legal basis must be decided; 30 days
  is only a proposal.
- **Free-text reason.** Decide whether the session reason may contain personal data, or should be
  restricted at entry.
- **Audit retention.** Set the retention period for governance and mutation audit records and for
  recovery evidence.
