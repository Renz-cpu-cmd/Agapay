# F22–F23 SOS concurrency and response drills

Implemented October 22, 2026. The user selected **configurable drill defaults**. No real LGU roster, operating agreement, emergency contact or operational response target was invented. [Verification results](RESULTS.md) record software evidence separately from operational acceptance.

## F22: ordered location writes and lifecycle protection

SOS records now expose an integer `version`. Both location PATCH and staff status PATCH require `expected_version`.

A location write uses one conditional database UPDATE covering request ID, owner, expected version, unresolved status and capture time (the stored capture must be absent or strictly older). A successful write increments the same version used by status transitions and drill actions. Resolution and location writes therefore cannot silently overwrite one another.

Exact duplicate GPS fixes remain idempotent, including two concurrent copies and a retry carrying the original version. A duplicate matches capture time, latitude, longitude and accuracy, and uses a conditional no-op UPDATE to serialize its acknowledgement with resolution/newer fixes. It does not increment version. A resolved request rejects even an exact duplicate. An equal-time different fix is a conflict, not a duplicate. New fixes retain the two-minute age / one-minute future-skew budgets; exact already-recorded retries do not become new measurements.

Conflicts return HTTP 409 with `detail.code=refresh_required`, a message and a sanitized `detail.current` request. A newer candidate with a stale version can also lose a race: the client must refresh and manually review rather than automatically merge it. The guarantee is monotonic accepted capture time and explicit conflict handling, not that every competing candidate is accepted.

Web status editors keep the version from opening the editor even when polling sees a later GPS fix. A conflict discards the resolution note and disables writes until explicit refresh. Mobile sends the known request version, pauses sharing on 409, blocks further fixes, and stops its foreground GPS stream. Periodic polling cannot remove that conflict latch. The resident must explicitly refresh, review and resume; the rejected fix is never automatically replayed.

## F23: a recorded drill workflow

The existing practice SOS record is retained, with its original resident, request reference, creation payload and individual lifecycle. Starting a response drill is a separate explicit staff action; it records staff review/acknowledgement if needed and assigns coordinator ownership. Legacy practice requests without a response drill can still use the original review lifecycle. Requests with a response drill must close through a reasoned, evidence-bearing drill action.

Drill response stages are:

| Stage/action | Required evidence and actor |
| --- | --- |
| UNASSIGNED | A staff member deliberately starts a drill using the reviewed policy version; a configured active coordinator is within recorded duty hours |
| ASSIGNED | Coordinator assigns an active staff responder within that responder's duty hours; assignment does not claim dispatch acceptance |
| Contact attempt | Coordinator/assigned responder records channel, actual outcome, reason and action reference; no call or message is sent by AGAPAY |
| ACCEPTED | Only the assigned on-duty responder records acceptance with a drill dispatch/action reference |
| EN_ROUTE | Only the assigned responder records departure after acceptance, with an action reference |
| ARRIVED | Only the assigned responder records arrival after departure, with an action reference |
| Handoff | Coordinator/current responder explicitly transfers ownership; the new on-duty responder must accept again |
| Unavailable | Assigned responder/coordinator records unavailability before acceptance; the next eligible roster participant is selected and acceptance remains pending |
| CLOSED | A recorded closure reason and evidence reference; assistance-completed closure requires recorded arrival; exceptional/exercise closure needs coordinator/admin review |

The coordinator remains responsible for review throughout. Every displayed drill stage comes from a recorded action. Acknowledgement means **review**, not that a responder was sent. Arrival is never inferred from elapsed time, GPS proximity or acknowledgement. The mobile app remains resident-only and reads recorded activity; staff controls exist on web.

Available closure reasons are assistance completed, resident cancellation, duplicate correlation, unable to contact and exercise completion. These are recorded drill outcomes, not proof of real-world assistance. A duplicate closure requires an incident link. Correlation adds a shared drill-incident reference without merging or deleting resident requests, changing their references, or exposing other residents' identities to a resident. Each request retains its own owner, response and history.

## Policy, duty hours and escalation

An administrator must explicitly configure the drill policy before starting a response drill. The policy requires real participating staff IDs, a coordinator with duty hours, timezone-aware shift intervals and at least one deliberately entered exercise fallback contact. The UI identifies duty timestamps as UTC; resident/staff SOS event times retain their existing PHT/local display labels.

Default planning targets are 120 seconds to assignment, 180 seconds to acceptance, 300 seconds to departure, 900 seconds to arrival and 300 seconds to coordinator review. They are configurable exercise targets, not an operational SLA or an LGU-approved standard. No roster or contact is prefilled. Roster order determines fallback order. Disabled/nonstaff accounts and staff outside recorded duty hours cannot receive a new assignment. Active drills retain their reviewed policy snapshot; changing the latest policy does not silently change an ongoing drill.

A bounded deadline worker records overdue review and escalation. For an unassigned/unaccepted drill it can assign the next active on-duty roster participant who has not already been attempted. This is an assignment record only; the alternate still must explicitly accept. After acceptance/departure/arrival it flags coordinator review rather than inventing a new dispatch or arrival. When no eligible alternate remains, it stops the timer and flags manual fallback review. A coordinator can record fallback review with a reference and establish another review deadline.

The worker must actually be supervised and run for timed escalation to occur. A displayed due time does not prove a sweep ran; the UI says so. One bounded invocation is:

```powershell
# Reviewed drill environment only; no external messages are sent.
.venv-auth/Scripts/python.exe -m app.sos_escalation_worker --limit 50
```

Schedule bounded runs through the deployment supervisor at an interval below the configured drill targets and monitor execution failures. Concurrent sweeps use request versions and recheck the deadline under the write lock; they cannot append duplicate escalation actions for the same expired stage. No worker was run against the live database during implementation.

## API and audit

All endpoints require authentication. Policy, directory and incident administration are staff-only, with policy writes restricted to administrators. A resident can read only their own response activity. Writes recheck staff authorization under the account lock and serialize through the SOS version.

- `GET/PATCH /api/sos-response/policy`: current draft, planning targets, shifts and exercise contacts. PATCH requires `expected_version` and reason. Stale policy edits require manual review.
- `GET /api/sos-response/staff`: bounded active staff directory for roster selection, with no resident directory/contact disclosure.
- `POST /api/sos-response/{id}/start`: request `expected_version`, reviewed `policy_version`, reason.
- `GET /api/sos-response/{id}`: current drill stage and recorded events. Event history is bounded to 100 rows; `before_event_id` retrieves older pages. A resident receives public drill messages, not internal reasons, evidence references, fallback contacts or other residents' requests.
- `POST /api/sos-response/{id}/actions`: version, action, reason and the fields required for that action. A stale action cannot append an event or overwrite an assignment. Unknown transport outcomes require refresh, not blind replay.
- `GET/POST /api/sos-response/incidents`: staff correlation records, with bounded list pagination.

Response events are application append-only and carry actor, time, reason, request version and evidence details. General mutation audit entries identify the policy/incident/action actor and reason. Snapshot and event tables are separate from any future operational dispatch data. Existing F21 database ownership/append-only privilege requirements still apply; ORM guards alone do not protect against a database owner.

Web provides a dedicated drill workspace inside SOS details: structured policy/roster/contact configuration, action recording, correlation and the event timeline. Staff action conflicts discard inputs and require explicit refresh. Correctable validation errors retain input. Resident mobile shows only recorded drill stages and messages, clearly labels exercise mode, hides cached activity when account ownership ends and marks failed refreshes as unavailable/stale.

## Additive rollout

No live database was migrated, reset or reseeded. Deploy backend and clients together; old clients without expected versions will receive validation errors.

1. Confirm the actual target database, preserve backups and record existing SOS IDs/references, statuses and practice flags. Stop writers and workers; complete earlier F01–F21 migrations first.
2. For an existing installation, inspect from `agapay-backend`:

   ```powershell
   .venv-auth/Scripts/python.exe -m app.migrate_sos_response
   ```

   After reviewing the plan and backup, use the same command with `--apply`. It adds the version column with default 1 and separate drill policy, response, incident and event tables. It preserves SOS rows/references/flags and is idempotent. Schema gaps stop API/production/bootstrap startup with an explicit migration message. Fresh installations create the complete schema through the existing offline administrator bootstrap instead.
3. Deploy web and resident mobile with the updated version contract. Verify exact-duplicate retries, equal-time conflicts, location-versus-resolution races, manual refresh, and foreground sharing stop/resume.
4. Configure an exercise coordinator, explicit duty windows, actual participating staff and exercise-only fallback contacts in the web SOS drill workspace. Review the draft targets. Schedule and supervise the bounded deadline worker for the drill environment.
5. Run a witnessed drill: primary does not answer/is unavailable; alternate receives assignment and explicitly accepts; record departure, arrival, handoff if applicable, and evidence-bearing closure. Include no-coverage/fallback review, worker outage, account revocation, two editors and correlation of two independent resident requests. Preserve the resulting event IDs and drill report for operator review.

## Operational activation remains disabled

`operational_enabled` is always false; there is no activation endpoint or settings shortcut. Payloads cannot set `practice=False` or promote a drill to an emergency request. The resident's normal journey remains visibly practice-only.

F23 operational acceptance remains pending a real LGU workflow and jurisdiction, signed operating hours/coverage, accountable operators, verified fallback contacts, trained responders, agreed escalation/SLA rules, dispatch integration/provider acceptance, supervised worker monitoring and a witnessed unavailable-first-officer drill. A future reviewed operational release must define how it receives actual emergencies and keeps exercises segregated. The configurable software drill and its synthetic tests do not establish those external facts.

Concurrency tests ran on the real SQLite engine with independent HTTP request/database sessions. PostgreSQL concurrency acceptance and an installed-device/witnessed drill remain pending; neither a PostgreSQL runner nor an operational dispatch integration was available in this task. No physical response, external contact attempt, SMS, call, push message or emergency deployment is claimed.
