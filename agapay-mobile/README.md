# AGAPAY Mobile

Android now separates development/staging/production flavors and rejects unconfigured protected signing. Development configuration assets and exercise controls are excluded from protected builds. See [F38–F39 implementation and evidence](../agapay-docs/security/F38-F39/README.md), [protected release checklist](../agapay-docs/security/F38-F39/RELEASE-CHECKLIST.md), and [accessibility matrix](../agapay-docs/security/F38-F39/ACCESSIBILITY-MATRIX.md). iOS release schemes/signing/APNs remain a separate pending gate. The newest finding-specific contracts linked here supersede the older prototype descriptions below.

F15/F16 add explicit rainfall products and reviewed installation hashes. Firmware fallback geometry is an unvalidated 150 cm bench profile; it is not a drop-in update for a 120 cm mounting. See [contracts, preservation migration, header export and physical acceptance](../agapay-docs/security/F15-F16/README.md).

F13 displays the backend measured-time cm/min estimate, slope range and unknown-coverage reason. No example rate or implicit stable trend is substituted. See [F12â€“F14 contracts and verification](../agapay-docs/security/F12-F14/README.md).

F09â€“F11 add provisional hysteresis/recovery policy, distinct issuer notice lifecycles and explicit notification subscriptions. See [implementation, setup and verification](../agapay-docs/security/F09-F11/README.md).

Operational home starts UNKNOWN when measurements are unavailable. Practice readings are available only through **Open exercise workspace**, with persistent labeling and local state. See [F07/F08 implementation and verification](../agapay-docs/security/F07-F08/README.md).

The monitoring contract separates heartbeat connectivity from retained-depth
age/quality and uses registry source metadata. Deploy the matching backend and
review source identities using [F05/F06 rollout](../agapay-docs/security/F05-F06/README.md).

Flutter frontend converted from the supplied Figma Make export,
`Strict Instruction Compliance.zip`. The React screen source is the visual
reference. Outfit, Inter, and JetBrains Mono are bundled locally with OFL licenses.

Registration, login, and profiles now connect to FastAPI. See [Accounts setup](../agapay-docs/ACCOUNTS_SETUP.md) for the backend, staff bootstrap, session behavior, and API configuration.

## Run

From this directory:

```powershell
flutter pub get
flutter run --flavor development --dart-define=AGAPAY_API_URL=http://127.0.0.1:8000
```

For Android, connect a device or start an emulator and use `flutter run --flavor development`.
iOS builds require macOS and Xcode. The Android debug APK builds successfully;
native device execution and iOS builds are not yet verified. Phones use their actual safe areas and system status bar;
the export's decorative browser phone frame is not part of the app.
Wide browser windows show a centered 390-pixel app preview.

## Map setup

The phone app uses one reusable `AgapayGoogleMap` WebView for monitoring stations,
evacuation guidance, and practice SOS previews. It loads the same Google Maps
JavaScript dark vector style used by the staff website, including terrain, satellite,
tilt, and Street View controls. GPS fixes come from `geolocator`, while markers and
the evacuation guide are sent into the shared map component from Flutter.

For local prototyping, copy
`assets/config/google_maps_demo_key.example.txt` to
`assets/config/google_maps_demo_key.txt` and replace its contents with a Maps Demo
Key. The real file is ignored by Git. Demo Keys require no billing but have changing
daily quotas and are prohibited for production use. A production build needs a
reviewed hosted HTTPS map with application/API-restricted credentials, or a different production map
provider. Protected builds default to the usable station/shelter list fallback until that integration is verified; they never load the bundled demo key.

## Implemented

- Animated splash that restores a saved session or opens Login.
- Resident-only sign-in and registration with validation, API errors, masked passwords, and barangay picker.
- Home: live/virtual alert banner, animated water gauge, measured water-depth
  trend, hybrid forecast, rainfall activity, station freshness, and telemetry history.
- Alert details, with navigation to the evacuation map and SOS.
- Centralized Google JavaScript WebView map with a five-second monitoring
  snapshot refresh, device GPS location, UCU Gym evacuation guidance, a Google-computed
  walking route with distance and duration, Street View controls, and external
  Google walking directions.
- Notifications with authenticated persistent sensor episodes, Active/History pages, and sanitized transition details.
- Persistent practice SOS: confirmed submission, optional device/manual location, Google Maps GPS preview, safe retry, foreground location updates, status polling and history.
- Saved profile and barangay editing, password changes, and revocable logout;
  notification/location switches and language selection remain in-memory prototype settings.
- Custom five-tab navigation with the central red SOS button.

## Prototype boundaries

Home readings, alert details, station markers, and recent telemetry history now use
the authenticated monitoring API. They explicitly label simulator readings as a
virtual station and preserve the last valid severity when the latest sensor sample is
invalid. The Alerts tab uses persistent community episodes, separately from live monitoring. The map shows only
monitoring stations whose coordinates exist in the backend and labels missing data
honestly. UCU Gym is listed as an evacuation-use facility in the city's 2017
profile, but activation, capacity and safe entrance are not supplied live. Accounts and
practice SOS records come from the backend. Device location is captured only after the
resident taps a location action in SOS or the map; push notifications, turn-by-turn
navigation, ML inference and emergency dispatch are not connected. Evacuation routing
uses the online Google Maps Compute Routes service and must not replace instructions
from local responders.

Home and monitoring-based Alert Details use the authenticated read-only
`GET /api/hybrid-projections/{station}/summary`. Station selection on the map
updates home history, forecast, and rainfall together. The summary uses fresh
ESP32 depth, physical gauge inputs, and the same assumed basin as the automatic
web demonstration. It remains development-only and does not inherit another
browser's configuration. Missing rainfall stays unknown; stale, failed, or
expired projections hide numeric values. Forecasts do not change alert tiers.

The mobile app is for residents only. Login always uses the `mobile` audience;
admin/officer logins and cached staff sessions are rejected. ML Configuration
and ML Evaluation belong to the staff web command center and have no mobile
screens or links. The mobile projection controller sends read-only summary
requests; it cannot configure or start a model run. The legacy prediction
contract and its controller remain for compatibility tests.

SOS saves a practice request only after explicit confirmation and shows success
only when the backend accepts it. Failed or interrupted attempts retain their
reference for duplicate-safe retry. History and staff status changes survive app
restarts. See [Practice SOS setup](../agapay-docs/SOS_SETUP.md).

Language selection changes the chosen setting only, as in the source export;
translated screen copy has not been supplied. Password recovery directs users
to an administrator. Privacy policy publishing remains unavailable.

## Structure

- `lib/app.dart`: app setup, routes, theme, and preview sizing.
- `lib/controllers/`: accounts, practice SOS, forecast availability, polling monitoring, and community alert state.
- `lib/services/auth_api.dart`: authenticated HTTP API and secure token persistence.
- `lib/models/`: account, forecast, alert-level, monitoring, and resident-safe community alert contracts.
- `lib/core/`: design tokens and shared UI primitives.
- `lib/screens/`: Flutter versions of the supplied screens.
- `lib/navigation/`: app routes and custom bottom navigation.
- `lib/widgets/common/`: form controls, animated gauge and shared forecast panel.
- `lib/widgets/maps/`: shared Google WebView map and Flutter-to-JavaScript marker bridge.
- `assets/maps/`: centralized Google Maps JavaScript renderer.
- `assets/fonts/`: bundled fonts and licenses.

## Verification

```powershell
flutter analyze
flutter test
flutter build web
```

Widget tests cover the main navigation, registration and dropdown, all four
alert tiers, station/shelter selection, persistent community alert details, SOS cancellation
and simulated completion, settings, logout, and 320-pixel phone/keyboard layouts.

To regenerate optional development screenshots:

```powershell
flutter test --update-goldens --dart-define=CAPTURE_PREVIEWS=true
```

Screenshots go to ignored `build/previews/`. Widget-test screenshots may lack
platform emoji fonts; the live app uses platform fallback glyphs.

## Community alert integration

The Alerts tab uses only the authenticated resident-safe `/api/community-alerts`
family through the existing `AuthApi.request()` and secure session storage. It
does not call the staff-only `/api/alerts` API. `CommunityAlertController` owns
typed episode/page/detail models and sanitized transitions; `MonitoringController`
continues to supply Home's current water level, rainfall, trend, and sensor quality.
Home's detail action remains monitoring-based. Tapping an Alerts card instead
loads that persistent episode's detail and timeline.

- Active loads `/community-alerts/active` every five seconds while signed in,
  skipping ticks during an outstanding request. History uses `/community-alerts`
  (active and resolved episodes), refreshed on entering Alerts/History or manually.
- Both feeds use Previous/Next pages of 50, replacing rather than accumulating
  records. Backend totals drive pagination. Offset pages can shift as new episodes
  arrive; refresh to restart a current view. Detail timelines use the same bound
  with `transition_limit` and `transition_offset` and refresh on open/page change.
- Requests are serialized per resource. Owner/query generations suppress old
  results and queued requests after account changes, logout, expiry, password
  changes, or disposal. Logout/disposal stops alert timers; no background service
  or delivery infrastructure was added.
- Active cards show current severity and latest valid depth. Resolved cards show
  peak incident severity, trigger depth, and explicitly labelled recovery depth.
  Trigger/recovery readings are not peak depths. UTC timestamps stay parsed as
  UTC and are formatted in Philippine time (UTC+08:00/PHT), independent of the
  phone's timezone. Unknown/malformed values produce an unavailable state, never
  a NORMAL fallback.
- Loading, unavailable, empty Active, and empty History states are distinct.
  A failed fetch clears that resource's previous data; no offline alert cache is
  shown. A successful response can still contain an old valid reading: invalid
  telemetry preserves the persistent episode and does not resolve it.
- The static notification feed, fake read/unread counts, and monitoring-derived
  notification dots were removed. Optional per-notification callback evidence and
  explicit acknowledgement now have a separate history (F33). Profile delivery
  preferences are server-connected; they do not hide the in-app sensor feed.
- `source=sensor` means telemetry-generated. Device/simulator historical origin
  is not stored, and persistent episodes are not labelled physically verified.
  Physical/site calibration remains pending. An EVACUATE sensor tier is not an
  official LGU evacuation order; follow official local instructions and confirm
  shelter activation and safe access. The existing prototype UCU Gym map remains.

Firebase transport code is implemented behind explicit setup; APNs credentials,
real phone delivery, SMS and acknowledgments are not completed. No firmware,
thresholds or alert-lifecycle changes are part of this integration.

Run `flutter pub get`, `flutter analyze`, and `flutter test`. Community tests cover
typed parsing, unsafe values, authenticated owner lifecycle, pagination, errors,
polling overlap, late responses, expiry/logout/password changes, real episode UI,
peak/recovery semantics, direct transitions, and narrow-screen layout. Existing
authentication, SOS, prediction and navigation/monitoring checks remain in the suite.

## Push registration and optional Firebase transport

`PushTokenProvider` separates Firebase token acquisition from authenticated
registration. `firebase_core` and `firebase_messaging` are installed, but runtime
initialization is opt-in via `--dart-define=AGAPAY_FIREBASE_ENABLED=true` and real
native configuration from FlutterFire. Default/unconfigured startup uses the
disabled provider; no real FCM acceptance or phone receipt is verified.

`NotificationRegistrationController` uses only `AuthApi.request()`:
after login/restoration it reads the provider token, then serializes token-change
events into POST `/api/notification-devices`. The Firebase provider persists one random UUID v4 in secure storage per
installation through token rotation. Repeated token events do not
repeat registrations; failures remain unavailable and can retry through
`refresh()`, a new token event, or a new session. No registration polling runs.
Provider/token error text is not exposed in UI state or logs.

Logout drains registration work, attempts DELETE for this device, then revokes
the session. If deletion fails, backend logout explicitly disables devices linked
to that session, even when it has expired or been pruned. If DELETE returns 401,
AuthApi keeps the bearer only within this explicit logout operation to complete
that server cleanup; it never restores the expired API session.

**API session != push registration.** Natural API expiry/401 clears local API state
without deleting the server push registration. An already enabled device remains
eligible while its resident owner is active, until explicit logout, withdrawal,
security revocation or an invalid-provider-token result disables it. Password and
administrative security revocation also cover registrations with pruned sessions;
reactivation requires fresh registration. A send already in flight cannot be
recalled. Expiry, password changes, owner removal and disposal
cancel subscriptions and ignore late results. A non-401 API failure does not
destroy the login session; 401 uses the existing AuthApi expiration callback.

This is authorization behavior only: the default provider remains disabled and
the app does not claim real notifications are active. Production provider-token
storage requires protected database/backups and encryption-at-rest controls.

The Profile delivery preference is server-connected (F17–F19). Optional app receipt
consent is a separate off-by-default choice (F33). The Community Alert feed and
live Home monitoring remain separate from per-notification evidence. Foreground
messages refresh community data; background notification display belongs to the OS.

Validated SENSOR_ESCALATION metadata selects a positive `alert_id`. Initial and
resumed notification taps wait for session restoration, then fetch Community Alert
detail from FastAPI. Logged-out taps are discarded; unavailable details show the
existing error state. The background entry point never mutates alert state. Source device/simulator history remains
unknown; sensor EVACUATE is not an official LGU evacuation order and physical/site
calibration remains pending. Local ESP32 alert operation is independent of push.

Permission is requested once per installation after resident authentication.
Denial/null token leaves registration waiting without affecting in-app alerts or
login. Resume rechecks permission/token; token refresh registers rotations. The
Profile switch remains a non-operational preference, not an OS permission control.

See [Firebase setup](../agapay-backend/docs/firebase-fcm-setup.md) for the
exact external Firebase/APNs/platform setup still needed. Do not put service-account
JSON, private keys or local Firebase configuration in Git. Current CI uses fakes
and does not require an emulator or physical device.

Validate with `flutter pub get`, `flutter analyze`, and `flutter test`.
Registration tests cover login, disabled/no-token behavior, rotation, serialization,
logout races, failure/expiry, provider errors and disposal; existing Community Alert,
auth, SOS, monitoring, prediction and navigation tests remain in the full suite.

Station lifecycle administration, persistent preferences, English-only language and verified geographic context: [F17-F19 contracts and rollout](../agapay-docs/security/F17-F19/README.md).

Verified email recovery, account sessions/devices and stale profile protection: [F20-F21 contracts and deployment](../agapay-docs/security/F20-F21/README.md). Staff MFA and administrative tools remain on web.

SOS location conflict pause/manual resume and resident-visible recorded response drills: [F22-F23 contracts and rollout](../agapay-docs/security/F22-F23/README.md). Mobile remains resident-only; operational dispatch is disabled.


Registry shelter/text fallback, encrypted last-known offline reader and durable exact-payload practice SOS outbox: [F24-F25 contracts, rollout and remaining device acceptance](../agapay-docs/security/F24-F25/README.md). Live inventory starts empty; generic routes do not certify flood-safe access.


Unified observation freshness/selection across home, map, detail and forecasts; release-only HTTPS origin guards: [F26-F27 implementation, rollout and verification](../agapay-docs/security/F26-F27/README.md). Field deployment acceptance remains pending.

## Feed lifecycle and bounded reads (F30–F31)

Monitoring, hybrid, forecast and community-alert reads pause in the background and refresh on resume. Old account/station/mode generations cannot replace the current view. Monitoring requests 20 history points; encrypted legacy 120-point cache entries remain readable without renewing their timestamps or retention. Backend degradation appears separately from sensor freshness. See the [measured results](../agapay-docs/security/F30-F31/RESULTS.md); native battery/radio and physical receipt-to-render checks remain pending.

## Optional delivery evidence (F33)

Alerts → Push delivery evidence displays the resident's own queued/provider/callback/open/explicit-acknowledgement stages. Optional callback collection defaults off; a dedicated encrypted 200-record/seven-day journal submits original timestamps without reading API credentials from a background isolate. Manual refresh drains bounded queued callbacks. A stale acknowledgement requires manual refresh and is never automatically retried. Physical phone delivery and OS background behavior remain pending; see [contracts and phone acceptance](../agapay-docs/security/F32-F33/README.md).

Home/detail water forecasts use the shared published product and display its ID, datum, binding and original expiry. Tapping the ID opens a historical record. Ordinary rain reads use an observation-only endpoint and cannot run private basin inference. Staff experiments and model review remain web-only. The operational model remains unavailable until real-data evaluation and independent approval pass; see [F34–F35 contracts and rollout](../agapay-docs/security/F34-F35/README.md).

F40 adds resident privacy requests and an ephemeral owner-record copy, with current-password verification and explicit review receipts. SOS map disclosure requires a deliberate map action. Staff privacy administration remains web-only. See [privacy/recovery contracts](../agapay-docs/security/F40/README.md) and [observed verification](../agapay-docs/security/F40/RESULTS.md).

Resident home and alerts now follow area, next-action, advisory, help and observation decisions. Shared scoped notice reads preserve expiry/cancellation and exclude Test/Exercise records; technical details, measured trends and published forecasts have separate expandable regions. See [design, contracts, previews and verification](../agapay-docs/design/resident-decisions/README.md).

Resident SOS now leads with queued/unknown/server-received evidence and an immutable reference, followed by recorded drill ownership/actions and location consent. Maps start with shared station/resource lists, including coordinate-less stations, area-scoped inventory pages and optional map views. See [SOS/map contracts, previews and verification](../agapay-docs/design/resident-sos-map/README.md).
