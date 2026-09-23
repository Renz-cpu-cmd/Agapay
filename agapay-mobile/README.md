# AGAPAY Mobile

Flutter frontend converted from the supplied Figma Make export,
`Strict Instruction Compliance.zip`. The React screen source is the visual
reference. Outfit, Inter, and JetBrains Mono are bundled locally with OFL licenses.

Registration, login, and profiles now connect to FastAPI. See [Accounts setup](../agapay-docs/ACCOUNTS_SETUP.md) for the backend, staff bootstrap, session behavior, and API configuration.

## Run

From this directory:

```powershell
flutter pub get
flutter run --dart-define=AGAPAY_API_URL=http://127.0.0.1:8000
```

For Android, connect a device or start an emulator and use `flutter run`.
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
standard billing-enabled Google Maps credential or a different production map
provider.

## Implemented

- Animated splash that restores a saved session or opens Login.
- Resident login and registration with validation, API errors, masked passwords, and barangay picker.
- Home: live/virtual alert banner, animated water gauge, interval rainfall,
  station freshness, telemetry history, forecast, and an offline demo fallback.
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

Home and monitoring-based Alert Details forecasts use the authenticated [prediction API](../agapay-docs/PREDICTION_INTERFACE.md)
for `STATION_001`. Actual mode shows Model not trained until an adapter is configured.
Development previews label sample values and let you exercise all availability states.
Failed or expired results hide numbers; forecast previews do not change alert tiers.

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
  notification dots were removed. There is no real notification delivery or read-receipt
  backend; the disabled delivery foundation is documented below. The Profile switch is explicitly a future preference only and does not
  disable this safety feed, register devices, or control push delivery.
- `source=sensor` means telemetry-generated. Device/simulator historical origin
  is not stored, and persistent episodes are not labelled physically verified.
  Physical/site calibration remains pending. An EVACUATE sensor tier is not an
  official LGU evacuation order; follow official local instructions and confirm
  shelter activation and safe access. The existing prototype UCU Gym map remains.

Firebase/FCM, APNs, SMS, push delivery, acknowledgments and background notification
handlers are not implemented. No firmware, thresholds, backend lifecycle or
authentication changes are part of this integration.

Run `flutter pub get`, `flutter analyze`, and `flutter test`. Community tests cover
typed parsing, unsafe values, authenticated owner lifecycle, pagination, errors,
polling overlap, late responses, expiry/logout/password changes, real episode UI,
peak/recovery semantics, direct transitions, and narrow-screen layout. Existing
authentication, SOS, prediction and navigation/monitoring checks remain in the suite.

## Push registration foundation (delivery disabled)

`PushTokenProvider` separates future Firebase token acquisition from authenticated
registration. The default `DisabledPushTokenProvider` has no token, makes no device
requests, and requires no Firebase dependencies/project files. No real FCM send or
device receipt has been performed by this integration.

`NotificationRegistrationController` uses only `AuthApi.request()`:
after login/restoration it reads the provider token, then serializes token-change
events into POST `/api/notification-devices`. The future provider must keep one
stable UUID per installation through token rotation. Repeated token events do not
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

The Profile switch remains explicitly **future preference only**. It is not
server-connected and does not control registrations or delivery. A future release
must implement a server-enforced preference before labelling it operational.
The Community Alert feed and live Home monitoring remain separate and unchanged;
no unread/read-receipt model or notification presentation/background handler exists.

Future notification metadata uses a structured persistent `alert_id` for opening
Community Alert detail, not navigation parsed from prose. Actual deep-link receipt
handling awaits the Firebase adapter. Source device/simulator history remains
unknown; sensor EVACUATE is not an official LGU evacuation order and physical/site
calibration remains pending. Local ESP32 alert operation is independent of push.

See [backend notification setup](../agapay-backend/docs/notifications.md) for the
exact external Firebase/APNs/platform setup still needed. Do not put service-account
JSON, private keys or local Firebase configuration in Git. Current CI uses fakes
and does not require an emulator or physical device.

Validate with `flutter pub get`, `flutter analyze`, and `flutter test`.
Registration tests cover login, disabled/no-token behavior, rotation, serialization,
logout races, failure/expiry, provider errors and disposal; existing Community Alert,
auth, SOS, monitoring, prediction and navigation tests remain in the full suite.
