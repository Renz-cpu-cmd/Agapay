# Firebase Cloud Messaging setup and verification

Repository integration is implemented; Firebase project configuration and physical
delivery are **not verified**. CI uses mocks, with no credentials, APNs key, phone,
or real registration token. Push is disabled by default. Local ESP32 alerts and
authenticated in-app Community Alerts remain independent of push delivery.

## Backend (external setup)

1. Select the actual Firebase project and enable its **Firebase Cloud Messaging
   API (HTTP v1)**. Grant the sending identity the required FCM IAM permission,
   using least privilege. No legacy server keys or `/fcm/send` are used.
2. Prefer workload identity/Application Default Credentials (ADC) in deployment.
   For local development, configure an authorized ADC identity, or intentionally
   provide a service-account credential file outside Git with restricted access.
   `AGAPAY_FIREBASE_CREDENTIALS_PATH` overrides ADC when explicitly set; an invalid
   explicit path never falls back. No access token is stored in application code.
3. Configure these environment values using the real project (no values supplied
   by this repository): `AGAPAY_NOTIFICATION_PROVIDER=fcm`,
   `AGAPAY_FIREBASE_PROJECT_ID`, and optionally
   `AGAPAY_FIREBASE_CREDENTIALS_PATH`. Leave provider `disabled` in ordinary CI.
4. Start the API normally so development tables exist. From `agapay-backend`,
   invoke `python -m app.notification_worker --limit 50`. No automatic scheduler
   is installed. Invalid project/credentials produce a sanitized configuration
   error before claiming deliveries. Disabled-mode processing suppresses pending
   deliveries terminally; it is not a way to test real sending.

The provider initializes one named Admin app per provider instance. It sends the
existing safe title/body and string data keys `type`, `alert_id`, `severity`,
`station_id`, `status`. Only valid severity escalation intents are sent.

FCM acceptance maps to ACCEPTED (worker SENT), unregistered tokens to INVALID_TOKEN
(revision-guarded disable), explicit quota/unavailable HTTP 429/503 rejection to
RETRYABLE_REJECTION, credential/permission/payload rejection to PERMANENT_REJECTION,
and timeout/transport/internal/ambiguous outcomes to UNKNOWN. No exception text is
logged. SENT is acceptance, not phone receipt. Existing bounded retries, revision
checks, supersession, outbox uniqueness and UNKNOWN/manual reconciliation remain.

Admin SDK 7.6.0 is pinned because its automatic POST retries are disabled through
one isolated private transport seam in `firebase_provider.py`. Tests verify zero
transport replays and bounded 15-second request and credential-refresh timeouts.
Review this seam on upgrades. Token-target messaging is retained for the existing
FCM registration-token contract; this SDK emits a token-field deprecation warning.
Do not substitute a Firebase installation ID for a registration token.

## Flutter Android (external setup)

1. Install the official Firebase CLI (`npm install -g firebase-tools`), authenticate
   with `firebase login`, then install FlutterFire CLI:
   `dart pub global activate flutterfire_cli`.
2. From `agapay-mobile`, run `flutterfire configure --platforms=android,ios` on a
   suitable setup machine, selecting the real project. For Android alone use
   `--platforms=android`. Register/select the existing application ID
   **com.agapay.agapay_mobile**; do not invent a different Firebase package.
3. Ensure the generated `android/app/google-services.json` matches that app.
   Gradle applies Google Services only when this file exists. This runtime uses
   native default-app configuration (`Firebase.initializeApp()`), so it does not
   import a missing generated `firebase_options.dart` in CI. Retain generated
   options privately for FlutterFire tooling; no fake identifiers are included.
   Review CLI Gradle edits and preserve conditional configuration for CI.
4. Build/run with `flutter run --dart-define=AGAPAY_FIREBASE_ENABLED=true` plus
   the existing backend URL configuration. Sign into a resident account. The
   Android 13+ notification permission is declared and requested once; subsequent
   changes are made through OS settings, then checked on resume. Permission
   refusal leaves registration waiting and does not disable in-app Community Alerts.
5. Use a physical Android phone with Google Play services for delivery verification.
   Android uses Firebase's default notification channel; channel/OS settings can
   suppress display. Foreground messages refresh the in-app feed instead of
   creating a second local notification or claiming physical receipt.

## Flutter iOS (external setup on macOS)

The project minimum is iOS 15 to match the installed FlutterFire podspecs. Use a
compatible Xcode/Swift toolchain; see [Firebase Apple SDK requirements](https://firebase.google.com/support/release-notes/ios).

1. Register/select the actual Xcode bundle ID **com.agapay.agapayMobile** and ensure
   `ios/Runner/GoogleService-Info.plist` is included in the Runner target through
   FlutterFire/Xcode. Do not commit local Firebase configuration.
2. Configure a real Apple developer team, signing/provisioning and the **Push
   Notifications** capability in Xcode. Remote-notification background mode is
   declared in Info.plist; verify capabilities/provisioning on the signed target.
   No APS entitlement or Apple signing completion is fabricated by this commit.
3. Upload/configure the actual APNs authentication key and associated IDs in
   Firebase. Keep method swizzling enabled as required by FlutterFire messaging.
   Never place the APNs private key in this repository.
4. Request permission through the app and verify on a signed physical iPhone.
   Token retrieval waits for an APNs token; resume retries if it is not ready.
   Build/run with the same explicit Firebase Dart define. Apple configuration and
   iOS builds cannot be verified by the Windows/Linux checks in this repository.

## Mobile behavior and security

`FirebasePushTokenProvider` wraps an injectable messaging gateway. Random UUID v4
installation identity and the permission-prompt marker are persisted in secure
local storage, never derived from hardware identifiers. iOS keychain may retain
identity across reinstall; resetting app data may create a new identity. Rotation
reuses the identity and existing authenticated registration API. Tokens are never
rendered or logged. Registration errors use the existing sanitized states.

Foreground validated SENSOR_ESCALATION messages refresh active/history API data.
The top-level background entry point performs no authenticated mutations; the OS
displays notification payloads while backgrounded. Initial and resumed taps parse
only a positive episode ID, wait for session restoration, and retrieve real detail
from `/api/community-alerts/{id}`. Logged-out taps are discarded, and API failure
shows the existing unavailable state. Push prose never supplies authoritative
episode content. No read receipts, offline replay, geofencing, topic subscriptions
or server-connected Profile preference is added.

API-session expiry does not revoke push authorization. Explicit logout, security
revocation, account ineligibility, withdrawal and invalid tokens retain their
existing protections. Production databases/backups need restricted access and
encryption at rest because provider tokens must be available for sending.

EVACUATE means **AGAPAY EVACUATE-level sensor alert**, not an official LGU evacuation
order or confirmation of an activated shelter. Follow official local instructions.
Thresholds still need physical/site calibration. Historical simulator/device origin
is not stored; notification receipt alone does not prove physical sensing.

## Verification checklist (perform only after external setup)

1. Sign into the configured physical app, allow permission, obtain an FCM token
   internally, and verify successful own-device registration without printing it.
2. Trigger a controlled **valid escalation** through the existing telemetry path.
   Confirm a new event/delivery targets that device; old history is not replayed.
3. Invoke the bounded FCM worker. Confirm provider mode `fcm` and SENT/accepted
   outcome using safe delivery identifiers, without exposing tokens.
4. Confirm the phone displays the safe notification while backgrounded. Separately
   verify foreground feed refresh, denied permission, logout and token rotation.
5. Tap the notification with a restored resident session and confirm the exact
   persistent Community Alert detail is fetched. Also test terminated launch,
   logged-out tap and unavailable API.

Record evidence separately: **A** code compiled/tests passed; **B** Firebase project
configured; **C** FCM accepted; **D** physical phone displayed; **E** tap opened the
correct persistent episode. A never implies B–E. No B–E claim is made here.

Local checks: backend `python -m pytest -q`; mobile `flutter pub get`,
`flutter analyze`, `flutter test`. These require no Firebase credentials.

Official references: [Admin sending](https://firebase.google.com/docs/cloud-messaging/send/admin-sdk),
[Flutter setup](https://firebase.google.com/docs/flutter/setup),
[Messaging setup](https://firebase.google.com/docs/cloud-messaging/flutter/get-started),
[Flutter receipt and taps](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages),
[FCM errors](https://firebase.google.com/docs/cloud-messaging/error-codes).
