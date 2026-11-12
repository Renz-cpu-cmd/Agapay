# ML workspace and mobile preview

Prepared October 21, 2026.

## What changed

- Web ML Configuration uses a full-width workspace with a forecast preview, current setup summary, and grouped advanced controls.
- Web ML Evaluation includes accuracy cards, baseline comparisons, data provenance, and the rainfall-versus-depth validation boundary.
- Mobile home stacks measured water-depth history, the hybrid forecast, and rainfall activity. Map station selection updates these views together.
- Mobile is residents-only. Staff sign-in, mobile technical pages, and their links have been removed. Residents receive read-only water-depth, forecast, and rainfall summaries. ML Configuration and Evaluation stay on the staff website.
- Unknown rainfall stays unknown. Stale depth does not make a separately fresh gauge appear offline. Stale/expired projections hide their numeric values.
- Mobile does not expose model configuration or run controls. The server supplies its experimental summary using the documented assumed basin.

## Local web preview

- Command center: http://127.0.0.1:3011/ml-configuration
- Evaluation: http://127.0.0.1:3011/ml-evaluation
- API: http://127.0.0.1:8000

The restored API uses the existing `data/live_rain/demo-api.sqlite3` database and rain journal. Startup schema initialization, MQTT ingestion, and notification delivery are disabled for this UI preview. Old device readings therefore remain stale until a separately configured live session receives fresh telemetry. Historical context is demonstration data.

## Android build and USB connection

### Browser preview of the mobile UI

When no Android device is connected, run this from `agapay-mobile` while the API is running:

```powershell
& C:\flutter\bin\cache\dart-sdk\bin\dart.exe --packages=C:\flutter\packages\flutter_tools\.dart_tool\package_config.json C:\flutter\bin\cache\flutter_tools.snapshot run -d web-server --web-hostname 127.0.0.1 --web-port 8080 --no-pub --dart-define=AGAPAY_API_URL=http://127.0.0.1:8000
```

Open http://127.0.0.1:8080 after compilation finishes. The API already permits this local origin. The explicit SDK package map is required for this direct snapshot invocation. Native phone features, including its Google Maps WebView, require the Android app.

### Android APK

The debug build uses `AGAPAY_API_URL=http://127.0.0.1:8000`. On Android, that address reaches this laptop only after USB port forwarding is configured. It is not a Wi-Fi/LAN build.

Build command, from `agapay-mobile`:

```powershell
& C:\flutter\bin\cache\dart-sdk\bin\dart.exe C:\flutter\bin\cache\flutter_tools.snapshot build apk --debug --no-pub --dart-define=AGAPAY_API_URL=http://127.0.0.1:8000
```

The output is `agapay-mobile/build/app/outputs/flutter-apk/app-debug.apk`. The residents-only rebuild completed on October 21 in 65.1 seconds. The updated dated copy is `agapay-mobile/build/app/outputs/flutter-apk/agapay-ml-ui-usb-debug-2026-10-21.apk` (219,982,769 bytes). Its compiled kernel excludes mobile staff sign-in and the mobile ML workspace, and includes the resident role guard and read-only projection summary client.

SHA-256 of the dated APK: `94E38DB3F4B9636A166C3074A74D39434282E399C3CA19DCD64B515DA9CFF614`.

To connect a phone yourself, enable USB debugging, connect it to this laptop, and accept its normal USB authorization prompt. With the local API running, execute from the repository root:

```powershell
$agapayAdb = 'C:\Users\Asus\AppData\Local\Android\Sdk\platform-tools\adb.exe'
& $agapayAdb devices
& $agapayAdb reverse tcp:8000 tcp:8000
& $agapayAdb install -r '.\agapay-mobile\build\app\outputs\flutter-apk\agapay-ml-ui-usb-debug-2026-10-21.apk'
```

These commands assume exactly one authorized Android device is connected. No installation, device authorization, firmware flash, or device port forwarding is performed automatically by preparing this handoff. Reapply port forwarding after reconnecting USB if needed.

Open AGAPAY and sign in with a resident account, or use Register to create one. Admin/officer accounts use the web command center. Cached staff sessions in mobile are rejected and cleared. No new credentials are included in this document.

## Verification evidence

The October 20 implementation checks passed: production Webpack build, TypeScript checking, 18 web checks, 17 focused backend checks, clean Flutter analysis, and 92 mobile tests. The final mobile styling also passed the seven focused hybrid tests and clean analysis. Light/dark previews under `agapay-mobile/build/previews/ml-*.png` use test fixtures.

Those checks are distinct from the October 21 APK build and local service checks. No physical rain-gauge accuracy, phone installation, or field flood-forecast accuracy is established by a successful software build.

October 21 service checks: API `/health` returned `status=ok` and `database=connected`; the web `/login` HEAD request returned HTTP 200 after restarting the preview server with host access. These are service-response checks, not an authenticated browser visual inspection.

Resident-only correction verification on October 21: Flutter analysis clean; all 91 mobile tests and 16 focused backend tests passed. Staff responses and cached staff sessions are rejected in mobile, including when server logout fails. The running API rejects the removed mobile_staff audience with HTTP 422. The refreshed browser preview was visually checked: resident login/registration remains, with no staff selector. Web ML pages remain available to staff.
