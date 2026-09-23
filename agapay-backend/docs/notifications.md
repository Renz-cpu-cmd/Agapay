# Notification delivery foundation

Status: **real push delivery is disabled**. No Firebase credentials, Firebase SDK,
FCM network adapter, device receipt, or end-to-end push verification is included.
The app and CI require no Firebase configuration.

```text
VALID telemetry -> AlertTransition -> NotificationEvent + NotificationDelivery
                                            (one database transaction)
                                   -> explicit bounded worker
                                   -> NotificationProvider
                                   -> future FCM adapter
```

The alert classifier remains provider-independent. Only severity increases create
events: NORMAL to ADVISORY/WARNING/EVACUATE, ADVISORY to WARNING/EVACUATE, and
WARNING to EVACUATE. Re-escalation within an episode is another meaningful
transition. Same-tier readings, invalid readings, downshifts, and NORMAL recovery
do not create push events in this first policy. Recovery and downshifts remain
in persistent Community Alert history; invalid telemetry never creates all-clear.

An event is persisted even with zero recipients. Eligible recipients are captured
at transition time: all enabled devices belonging to active residents, with a
valid registration-bound session, across AGAPAY stations. There is no geographic
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
return 409 and can safely be retried. A disabled/expired/revoked registration can
release its token to a new registration; an eligible other owner cannot be taken
over. The push token is not an authentication credential.

Registration stores only the session hash already used by authentication, not a
bearer token. Eligibility requires the matching unexpired session and active
resident at enqueue and send time. Logout/password revocation therefore blocks
future worker sends even if mobile device deletion failed. Tokens on such
ineligible rows remain until explicit deletion, replacement, or future retention
cleanup; database access must remain restricted. No new retention scheduler is
included. Logout cannot recall a send already in flight.

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
worker rechecks account/session/device eligibility, registration revision, and
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
The future adapter must bound network timeouts and return RETRYABLE_REJECTION only
when it knows acceptance did not occur.

An invalid-token result disables and erases the unchanged device registration.
Failures cannot roll back previously committed telemetry or alert history.
Logging uses delivery/alert IDs, severity, mode, a short SHA-256 token fingerprint,
state and fixed result category; never raw tokens, credentials or exception dumps.

## Payload and safety

The structured data contains only type=SENSOR_ESCALATION, alert_id (persistent
community episode ID for a future deep link), severity, station_id, and status.
Title/body use known severity text. No telemetry IDs, sequence numbers, account
data, auth tokens or provider token go into notification content.

EVACUATE wording is an **AGAPAY EVACUATE-level sensor alert**, with preparation and
official local-authority guidance. It is not an official LGU evacuation order
and does not activate a prototype shelter. Thresholds remain provisional pending
physical/site calibration. Notification delivery is independent of local ESP32
buzzer/alert operation; no firmware or thresholds change here.

## External setup still required (separate reviewed task)

1. Create/select a Firebase project and enable FCM HTTP v1. Implement the future
   backend adapter using least-privileged IAM and Application Default Credentials
   or a secret-managed service-account file **outside Git**. Reserved settings are
   `AGAPAY_FIREBASE_PROJECT_ID` and `AGAPAY_FIREBASE_CREDENTIALS_PATH`.
   Setting provider to fcm currently fails closed: no adapter is implemented.
2. Register Android application `com.agapay.agapay_mobile` and the confirmed iOS
   Xcode bundle ID with Firebase. Supply local google-services.json /
   GoogleService-Info.plist, add the Firebase Flutter adapter and platform build
   configuration; none is included here.
3. Configure Apple APNs credentials in Firebase, iOS push capability/entitlements
   and permissions, Android runtime notification permission/channel, and production
   signing as needed. Implement permission-aware token retrieval/refresh and
   persist a random installation UUID in secure local storage.
4. Add foreground/background receipt handling and structured alert_id navigation,
   with authenticated Community Alert detail retrieval. Design server-enforced
   preferences before presenting the Profile switch as operational.
5. Run a real credentialed backend send to a physical device with a genuine token
   and verify device receipt, safe text, logout/rotation, and deep linking.

Ignore rules protect common Firebase/service-account filenames and credentials
directories. Arbitrarily named secret files still require review; never commit
private keys, service credentials, tokens, or production account details.

## Validation

`python -m pytest -q` uses isolated SQLite, no-op/fake providers, and mocked
outcomes. Tests cover authorization, token privacy/rotation, intent atomicity,
duplicates, concurrent workers, bounded retry, disabled and ambiguous outcomes,
session eligibility, and safe payloads. CI does not establish real FCM delivery.
