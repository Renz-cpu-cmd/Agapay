# Notification delivery foundation

Status: **disabled by default**. The Firebase Admin HTTP v1 adapter is implemented,
but no Firebase project/credentials or physical delivery have been verified.
The app and CI require no Firebase configuration. See [FCM setup](firebase-fcm-setup.md).

```text
VALID telemetry -> AlertTransition -> NotificationEvent + NotificationDelivery
                                            (one database transaction)
                                   -> explicit bounded worker
                                   -> NotificationProvider
                                   -> Firebase Admin HTTP v1 adapter (explicit opt-in)
```

The alert classifier remains provider-independent. Only severity increases create
events: NORMAL to ADVISORY/WARNING/EVACUATE, ADVISORY to WARNING/EVACUATE, and
WARNING to EVACUATE. Re-escalation within an episode is another meaningful
transition. Same-tier readings, invalid readings, downshifts, and NORMAL recovery
do not create push events in this first policy. Recovery and downshifts remain
in persistent Community Alert history; invalid telemetry never creates all-clear.

An event is persisted even with zero recipients. Eligible recipients are captured
at transition time: all enabled devices with retained provider tokens/hashes
belonging to active residents, across AGAPAY stations. There is no geographic
personalization or barangay matching. Later registration does not replay history.
Device/simulator historical origin is not known.

## Device contract

Existing bearer authentication is required. Only residents register mobile push
devices; staff receive 403, anonymous/expired sessions 401. These routes do not
alter staff-only `/api/alerts` or resident-safe `/api/community-alerts`.

- `POST /api/notification-devices`: idempotent registration (200). Body:
  `provider: "fcm"`, `platform: "android" | "ios"`, `installation_id: UUID`,
  and `provider_token` (16â€“4096 characters, no whitespace).
- `DELETE /api/notification-devices/{device_id}`: disable own registration,
  erase its stored token/hash, retain the ID for audit (204). Repeated removal
  succeeds. Unknown or other residents' IDs receive the same 404.
- No enumeration API. Responses allowlist only ID, platform/provider, enabled,
  and UTC created/updated/last-seen times. Tokens, user IDs, installation IDs,
  session hashes, and diagnostics are never returned. Responses use no-store.

One device per resident/installation UUID and one retained token globally are
enforced by DB constraints. Rotation updates the existing row. A reinstall with
the same token reuses that resident's row. Conflicting existing installations or
another resident's eligible token produce a generic 409. Concurrent upserts may
return 409 and can safely be retried. A disabled/revoked registration can
release its token to a new registration; an eligible other owner cannot be taken
over. The push token is not an authentication credential.

### API session and push registration are separate lifecycles

API sessions authenticate API requests. An explicitly enabled device registration
authorizes a resident installation for community flood notifications. Natural
API-session expiry does **not** revoke that authorization: a phone registered on
day 1 remains eligible on day 8 even if API access now requires another login.
Pruning an expired AuthSession row during login also leaves push eligibility
intact. Another resident cannot claim its token just because its session expired.

`session_hash` is private authorization provenance and explicit-revocation linkage,
not a continuously renewed delivery lease. No bearer token is stored on the device.
Recipient capture and worker rechecks require an enabled device with nonempty
provider token/hash and an existing active resident owner. Processing additionally
checks the captured device revision and whether a newer alert transition superseded
the intent. Neither step joins AuthSession or checks its expiration timestamp.

Explicit events revoke registration:

- `/api/auth/logout` disables registrations still linked to the supplied bearer
  hash, clears provider tokens/hashes, advances revisions, and deletes that session
  in one transaction. This works even if it expired or its row was pruned, and
  provides fallback cleanup when mobile DELETE fails or is skipped. Phone A's
  logout does not disable phone B registered under a different session.
- Password changes and deliberate account-wide session revocation disable all
  currently authorized registrations for that account, including registrations
  whose expired session rows were pruned. Existing administrative deactivation,
  role changes and password resets use this same revocation path. Reactivating an
  account does not restore disabled devices; authenticated registration is required.
- Authenticated own-device DELETE/token withdrawal and invalid-provider-token
  results disable the affected registration. Invalid-token results retain the
  atomic revision guard so an old response cannot disable a rotated token.

Registration and explicit revocation serialize on an account row lock (SQLite's
write lock in development). Registration re-authenticates after acquiring that
lock: a request authenticated just before revocation cannot restore a device with
its now-revoked session. A fresh authenticated registration after revocation commits
is allowed. Replaying logout for the old session cannot disable a registration
rebound to a new session. Expiry cleanup never calls deliberate revocation.

Flutter still attempts device DELETE before explicit logout. If DELETE returns
401, it retains the bearer only within that logout operation to call the cleanup
endpoint; it does not restore the expired API session. Ordinary 401 handling clears
local API state without DELETE/logout and does not erase server push authorization.
A send already in flight cannot be recalled by logout or revocation.

Provider tokens must remain available for future delivery. Production deployment
requires restricted database/storage and backup access plus encryption-at-rest
controls. This task introduces no ad-hoc reversible encryption. Token/hash/session
provenance must never be exposed through APIs or credential logs. No real FCM
delivery or automatic worker scheduler is enabled.

## Outbox, processing and failures

`NotificationEvent.transition_id` is unique; deliveries are unique by
(event, device). These constraints complement ingestion's telemetry uniqueness
and station serialization. An intent cannot commit separately from its
transition. Each delivery stores its target user/device revision, attempts,
state, timestamps, provider mode, and a small fixed result category. No provider
response dumps or exception strings are persisted.

After API startup has created the development tables, process one batch from
`agapay-backend`:

```powershell
python -m app.notification_worker --limit 50
```

Limit is 1â€“100. This is an **explicit operator invocation**, not an automatically
running scheduler or a public HTTP endpoint. With default
`AGAPAY_NOTIFICATION_PROVIDER=disabled`, eligible rows become SUPPRESSED with
category disabled. Suppressed rows are terminal and are not replayed later.
Do not treat running the disabled worker as a real push test.

A conditional UPDATE claims each row as PROCESSING and commits before provider
invocation, allowing concurrent workers without duplicate claims. No database
transaction is held across the external call. Immediately before sending the
worker rechecks account/device eligibility, registration revision, and
whether a newer episode transition superseded the intent. Changed registrations
and superseded incidents are suppressed, preventing old recovery/incident context
from being sent as a current escalation. These checks cannot cancel changes
occurring after dispatch has begun.

- PENDING: durable intent awaiting processing.
- PROCESSING: committed exclusive claim; no automatic reclaim after a crash.
- SENT: a real provider reports acceptance, **not proof of device receipt**.
- TESTED: fake/test provider processed the payload, with no real send.
- FAILED: rejected. Only confirmed retryable rejections get another attempt:
  30 seconds then 60 seconds, at most three attempts total. The bounded worker
  must be invoked again after the due time. Permanent rejection is terminal.
- SUPPRESSED: provider disabled, ineligible device, or superseded intent.
- UNKNOWN: timeout/unexpected provider exception or ambiguous acceptance;
  terminal for automatic processing.

A process crash may leave PROCESSING. Operators must inspect/reconcile these and
UNKNOWN rows with provider evidence before any future replay tooling is used.
**Exactly-once network delivery is not promised.** FCM does not make the local
delivery key an exactly-once guarantee. This foundation avoids blind resend of
ambiguous outcomes, accepting possible nondelivery instead of duplicate pushes.
An accepted send followed by a DB failure is likewise not automatically replayed.
The adapter bounds transport and credential-refresh timeouts to 15 seconds each,
disables SDK automatic send retries, and retries only explicit 429/503 rejections.
Timeouts, transport errors and ambiguous SDK errors become UNKNOWN. The pinned SDK
transport seam is tested; review it before upgrading firebase-admin.

An invalid-token result disables and erases the unchanged device registration.
Failures cannot roll back previously committed telemetry or alert history.
Logging uses delivery/alert IDs, severity, mode, a short SHA-256 token fingerprint,
state and fixed result category; never raw tokens, credentials or exception dumps.

## Payload and safety

The structured data contains only type=SENSOR_ESCALATION, alert_id (persistent
community episode ID for authenticated deep-link retrieval), severity, station_id, and status.
Title/body use known severity text. No telemetry IDs, sequence numbers, account
data, auth tokens or provider token go into notification content.

EVACUATE wording is an **AGAPAY EVACUATE-level sensor alert**, with preparation and
official local-authority guidance. It is not an official LGU evacuation order
and does not activate a prototype shelter. Thresholds remain provisional pending
physical/site calibration. Notification delivery is independent of local ESP32
buzzer/alert operation; no firmware or thresholds change here.

## External setup still required

Follow [Firebase FCM setup](firebase-fcm-setup.md) for actual project, ADC or secret
file configuration, FlutterFire native configuration, Apple signing/APNs and
physical-device verification. No real credential or token belongs in Git.
Provider mode remains disabled unless explicitly configured. Enabling FCM without
valid configuration fails closed before the worker claims any delivery.

## Validation

`python -m pytest -q` uses isolated SQLite, no-op/fake providers, and mocked
outcomes. Tests cover authorization, token privacy/rotation, intent atomicity,
duplicates, concurrent workers, bounded retry, disabled and ambiguous outcomes,
natural expiry versus explicit revocation, concurrent registration/revocation,
multiple sessions/devices, and safe payloads. CI does not establish real FCM delivery.
