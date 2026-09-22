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
- Notifications with today/yesterday groups, details, and in-memory read state.
- Persistent practice SOS: confirmed submission, optional device/manual location, Google Maps GPS preview, safe retry, foreground location updates, status polling and history.
- Saved profile and barangay editing, password changes, and revocable logout;
  notification/location switches and language selection remain in-memory prototype settings.
- Custom five-tab navigation with the central red SOS button.

## Prototype boundaries

Home readings, alert details, station markers, and recent telemetry history now use
the authenticated monitoring API. They explicitly label simulator readings as a
virtual station and preserve the last valid severity when the latest sensor sample is
invalid. Static alert-notification history remains sample content. The map shows only
monitoring stations whose coordinates exist in the backend and labels missing data
honestly. UCU Gym is listed as an evacuation-use facility in the city's 2017
profile, but activation, capacity and safe entrance are not supplied live. Accounts and
practice SOS records come from the backend. Device location is captured only after the
resident taps a location action in SOS or the map; push notifications, turn-by-turn
navigation, ML inference and emergency dispatch are not connected. Evacuation routing
uses the online Google Maps Compute Routes service and must not replace instructions
from local responders.

Home and Alert Details forecasts use the authenticated [prediction API](../agapay-docs/PREDICTION_INTERFACE.md)
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
- `lib/controllers/`: accounts, practice SOS, forecast availability, and polling monitoring state.
- `lib/services/auth_api.dart`: authenticated HTTP API and secure token persistence.
- `lib/models/`: account, forecast, alert-level, and monitoring contracts.
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
alert tiers, station/shelter selection, notification read state, SOS cancellation
and simulated completion, settings, logout, and 320-pixel phone/keyboard layouts.

To regenerate optional development screenshots:

```powershell
flutter test --update-goldens --dart-define=CAPTURE_PREVIEWS=true
```

Screenshots go to ignored `build/previews/`. Widget-test screenshots may lack
platform emoji fonts; the live app uses platform fallback glyphs.
