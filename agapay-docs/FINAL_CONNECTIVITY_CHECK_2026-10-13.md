# AGAPAY final connectivity and consistency check

Verified against the running isolated demo on October 13, 2026, approximately
09:36–09:51 AM PHT. Dashboard: http://127.0.0.1:3011/dashboard.

## Result

The physical ESP32, authenticated MQTT broker, isolated FastAPI demo database,
water monitoring, physical rain journal and experimental projection are connected.
The user completed a dry-cardboard movement test. Actual database readings ranged
from 39.738 to 84.7739 cm; the station plot and projected starting depth followed
those readings. This is a cardboard-derived depth proxy, not calibrated river data.

Station details previously called the separate untrained prediction endpoint.
They now use the same shared projection as Dashboard and ML Configuration. The
trained component is the rainfall model
`hybrid_rain_v01_20261012T003510Z_fdaff56583ad`; future depth comes from the
controlled-basin volume calculation with explicitly assumed parameters. The
legacy `/api/predictions/STATION_001?mode=actual` correctly remains `not_trained`:
this work did not train a separate operational river-level model or falsify its status.

Live configuration uses fresh ESP32 starting depth, physical rain events, and the
archived 2025-07-01 12:00 UTC rainfall context while a complete valid live history
is unavailable. Historical rain is labeled as context, not current measured rain.

## Measured speed and consistency

- Previous telemetry median: 10.008834 seconds. New observed median:
  2.000844 seconds across 29 intervals, range 1.459745–2.482299 seconds under
  live physical movement and API load. Another stationary sample had a median
  1.996819 seconds, range 1.910251–2.098716 seconds.
- Water UI polls once per second, including background tabs, with no overlapping
  requests. Rain activity polls 1.5 seconds after each request; projection polls
  750 ms after each live request. Browser background throttling can still affect
  timing; focus causes an immediate monitoring refresh.
- Authenticated local API audit: 15 requests per endpoint. Median/max durations:
  monitoring 16.74/102.86 ms, rain 167.85/404.37 ms, projection 184.81/379.93 ms.
  These measure local API requests, not operator-to-screen reaction time.
- Every audited projection's initialization timestamp and depth matched its exact
  persisted ESP32 observation, including changing sensor values. Forecasts had
  three finite horizons: +30, +60 and +90 minutes.
- A separate read-only MQTT check received eight real telemetry messages in
  15 seconds. No synthetic measurements or rain events were published.
- COM9 capture showed Wi-Fi status3, MQTT connected1, MQTT state0, and the
  preserved BENCH DISTANCE local alert mode. COM9 was released afterward.
- Latest rain journal count:167 at09:51:28 PHT. Current-hour total13.300 mm;
  no new physical rain tip was requested or fabricated in this movement test.
- Station, header and forecast share freshness rules, keep stale values as history,
  and do not claim a feed is live after errors or expiry. Initial loading now shows
  CONNECTING rather than sample flood readings.

## Changes in this final check

Firmware:
- `agapay-firmware/src/main.cpp`: telemetry interval10,000→2,000 ms;
  boot cadence diagnostic. Acquisition interval1,000 ms and independent rain
  queue remain unchanged.
- `agapay-firmware/tests/firmware_host_test.cpp`: boundary regression verifies
  tips are retained before the publish window and reported once at its boundary.

Web:
- `agapay-web/src/lib/monitoring.ts`: common aged station display helper.
- `agapay-web/src/context/MonitoringContext.tsx`: bounded1-second polling,
  no overlap, focus refresh, common freshness, real timestamps, no mock readings
  or mock alert episodes during initial loading.
- `agapay-web/src/data/mockData.ts`: optional recorded timestamp on history points.
- `agapay-web/src/components/Header.tsx`: CONNECTING/UNAVAILABLE initial status.
- `agapay-web/src/components/Dashboard.tsx`: consistent1-decimal measured depths.
- `agapay-web/src/components/Stations.tsx`: shared forecast and Rainfall Activity,
  actual timestamp filters for1H/6H/24H using available samples, correct loading
  state, consistent depth display and immediate plot updates without animation.
- `agapay-web/src/components/ForecastTrendPanel.tsx`: common freshness,
  explicit measured/modeled starting values, generated time including seconds.
- `agapay-web/src/components/RainfallActivityPanel.tsx`: reused in station details;
  its existing current-hour calculation and source checks remain unchanged.
- `agapay-web/src/figma.css`: explicit fixed chart heights. Flex sizing had made
  the inner forecast/rain SVG containers zero height on station details.
- `agapay-web/src/lib/projection-settings.ts`: validated, account-specific setup
  persistence; no forecast values stored.
- `agapay-web/src/context/HybridProjectionContext.tsx`: restores setup after
  reload and synchronizes tabs of the same browser/account. Recomputes fresh
  API forecasts. Separate browsers do not share browser storage.
- `agapay-web/src/components/MLConfiguration.tsx`: explains shared setup/storage.
- `agapay-web/test/monitoring_freshness_test.cjs`: expiry/error/tick regressions.
- `agapay-web/test/projection_settings_test.cjs`: validated restoration/isolation.

Ignored local audit artifacts: `data/live_rain/final_connectivity_audit.py`,
`final-connectivity-audit-20261013.json`, COM9 capture logs and screenshot proofs.
No API, broker, model artifacts, credentials, thresholds or rainfall calibration
were changed during this final check. Existing unrelated Git work was preserved.

## Validation

- Standard and cardboard-demo firmware host suites passed, including actual
  firmware JSON/FastAPI contracts, NVS/rain retention, local alerts, retry logic
  and new2-second telemetry boundary checks.
- PlatformIO cardboard-demo build passed: RAM45,848 bytes, flash785,065 bytes.
  Normally uploaded to COM9 successfully with hash verification. No flash erase,
  partition change or NVS reset.
- Focused backend tests:42 passed,2 dependency deprecation warnings.
- Web tests:15 passed; TypeScript checking passed.
- Final isolated current-source Webpack production build passed. It used its own
  build output, preserving the running demo `.next` directory. Non-fatal Next
  workspace-root warning and existing Node module-type warning remain.
- Browser verification: real station details and dashboard both show the same
  sensor origin, physical hourly rain and shared projection; station charts render
  in dark mode; reload restores active setup and produces fresh forecasts.
- Focused `git diff --check` passed; Windows line-ending notices are informational.

Commands from project root:

```powershell
& .\agapay-backend\.venv-ml\Scripts\python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-backend/.venv-ml/Scripts/python.exe -m ziglang c++'
& .\agapay-backend\.venv-ml\Scripts\python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-backend/.venv-ml/Scripts/python.exe -m ziglang c++' --bench-profile
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -e esp32-cardboard-demo
# Close COM9 monitors before an intentional normal upload:
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -e esp32-cardboard-demo -t upload --upload-port COM9
```

Web checks from `agapay-web`: `npm run typecheck` and
`node --test test/monitoring_freshness_test.cjs test/projection_settings_test.cjs test/rainfall_activity_test.mjs`.
Backend focused suite from `agapay-backend`:
`.venv-auth/Scripts/python.exe -m pytest tests/test_hybrid_dashboard.py tests/test_monitoring.py tests/test_predictions.py tests/test_rain_gauge.py tests/test_mqtt_subscriber.py -q -x --tb=short`.

Physical calibration remains outstanding. BENCH red/buzzer at distance≤25 cm is
an explicitly separate local cardboard behavior; canonical measured-depth alert
thresholds remain60/85/100 cm. It is expected that a25 cm target can activate
local bench red while the unchanged backend95 cm proxy reads WARNING. Forecast
accuracy and real-world flood readiness are not established by connectivity tests.

## Follow-up: automatic demo startup, October 13

At the user's request, the local demo no longer requires parameter entry or a
manual Start for a new setup. Once fresh valid physical STATION_001 telemetry
arrives on localhost/127.0.0.1, the projection provider selects the previously
verified live sensor/physical gauge preset automatically. It retains the same
archived rainfall context and explicitly assumed2/.1/.8/0/100 basin parameters.
Saved custom choices and an explicit Stop are preserved. No unknown station,
simulator, stale input or remote deployment is automatically configured.
Backend development/demo access gates remain unchanged.

ML Configuration now displays the shared forecast first and places controls
inside collapsed “Advanced projection settings (optional).” Presentation labels
say “Demonstration projection”; the calibration limitation remains visible.
This finalizes the demonstration workflow, not an operational river predictor.
No firmware upload, calibration change, backend restart, database reset or model
retraining was performed for this follow-up.

Changed: `src/lib/projection-settings.ts`, `src/context/HybridProjectionContext.tsx`,
`src/components/MLConfiguration.tsx`, `src/components/ForecastTrendPanel.tsx`,
`src/components/HybridForecastPanel.tsx`, `test/projection_settings_test.cjs`
(all under `agapay-web`).

Web regression suite now17 passed. TypeScript and isolated production build
passed. Browser observation confirmed a running fresh forecast with advanced
controls collapsed and no main-view Start requirement. The default-start and
saved-Stop rules were tested directly; a separate localhost login check was
blocked by the existing origin check, which was left intact. Original authorized
127.0.0.1 session remained signed in and working.

## Power-bank verification and page retry

The user confirmed the ESP32 was moved to a power bank. At10:13 AM PHT,
30 consecutive database records arrived at a median2.00033 seconds, with
monotonically increasing device uptime and no restart in that sample. Backend
health, login page and account setup proxy all returnedHTTP200. The rain journal
reported cumulative184; extra tips were not independently physically observed
by the agent and are not a calibration result.

The signed-in station view remained LIVE at10:19:57 PHT, showing measured62.1 cm,
fresh sensor-based projection and connected physical rain activity6.300 mm for
the current hour. No COM9 access, firmware flash, backend restart or NVS reset
was used for this verification.

The generic command-page error screen incorrectly called every page failure an
account-service outage. Also, its Try again button used Next's `reset`, which
clears error state without refetching the server contents. Updated
`agapay-web/src/app/(command)/error.tsx` to use the installed Next16.3.4 `retry`
refetch callback and a neutral page-failure message. Added
`agapay-web/test/page_error_test.cjs`; regression, TypeScript and isolated
production build passed.

A separate live browser error reported that Google Maps' demo-key daily2D quota
was reached. That external quota was not changed, and paid billing was not
enabled. It does not stop ESP32/MQTT/API telemetry, rainfall or forecasts.
The station detail page avoids the map dependency and was left open for the demo.
