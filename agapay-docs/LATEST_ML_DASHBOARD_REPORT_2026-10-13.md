# AGAPAY latest ML and dashboard changes

Report date: October 13, 2026

This is a handoff report for ChatGPT. The changes described below are implemented locally. Software checks passed; physical rain-gauge testing remains pending. These changes have not been committed, pushed, or deployed.

## 1. Latest dashboard changes

- Water Depth Trend and ML Forecasting now stack vertically, with forecasting below water depth. Both charts use the full width of the main monitoring column.
- A Rainfall Activity panel fills the space below the alert thresholds in the right column. The two columns align at the bottom on the verified desktop layout and stack on smaller screens.
- The forecasting station dropdown was removed. Selecting a station on the map now controls the water-depth trend, forecast, and rainfall panel together through shared station state.
- The dashboard forecast presents the trend, projected depths at +30, +60, and +90 minutes, source information, and reading freshness. Technical model inputs and basin settings are available through the sidebar.
- New sidebar pages: ML Configuration and ML Evaluation.
- Light/dark styling remains supported. The checked dashboard layout has no horizontal overflow.

## 2. Forecast integration

The command-center dashboard now uses an authenticated FastAPI hybrid-projection endpoint through the Next.js account proxy. It combines a saved rainfall Random Forest model with a water-balance calculation to produce experimental water-depth projections.

ML Configuration contains the starting depth, basin assumptions, and projection controls. ML Evaluation presents model results and limitations. Shared projection state continues across sidebar navigation, with a fixed starting anchor and polling that avoids overlapping requests.

Configuration currently lives in browser memory. Reloading or closing the session requires configuring and starting the projection again.

The old /hybrid-demo page remains available as an offline experimental lab. It has separate state and has not been fully consolidated into the command-center workflow. The legacy generic prediction endpoint also remains separate; this change does not migrate every mobile or station-detail forecast view.

## 3. Rain-gauge behavior

The confirmed gauge calibration is 0.70 mm per tip. Firmware and backend support cumulative tip events, duplicate handling, reboot identity, durable event storage, and acknowledgements after storage.

A valid fresh tip can change the water-balance projection after the event is received and the display refreshes. The Random Forest rainfall prediction uses completed hourly history; it does not necessarily change its output for every tip in the current incomplete hour. Therefore, the projected water depth can move while the rainfall-model output stays unchanged.

The integration uses a fixed anchor and avoids feeding projected depths back into the next calculation. A newer fresh measured water depth resets the anchor so rainfall already reflected in that measurement is not added again.

Stale, future-dated, wrong-station, or simulated events cannot claim fresh physical rainfall. Missing hourly rainfall stays unknown rather than being silently converted to zero.

## 4. Rainfall Activity and current preview

The backend now returns a 24-hour rainfall history for the rainfall chart. The panel distinguishes completed hourly rainfall from current-hour activity and explicitly labels archived demonstration data.

At the last verified preview, the gauge was Offline and the current-hour amount displayed an em dash. The visible rainfall bars were historical ERA5 context, and the projection used a manual starting depth with that historical context. The station's stale measured water reading was labeled stale.

This preview demonstrates the integrated dashboard and calculation flow. It is not evidence of live physical rainfall or validated flood forecasting.

## 5. Model and alert boundaries

The saved model uses 2020–2025 ERA5 hourly rainfall, with chronological training, validation, and test splits. It forecasts rainfall; water depth is calculated using operator-configured basin assumptions.

Pooled held-out rainfall MAE is approximately 0.297 mm and RMSE approximately 0.775 mm. Performance varies by forecast horizon; the one-hour MAE was slightly worse than the persistence baseline. There is no validated water-depth accuracy claim because the model was not trained against measured river or basin depth data.

The projection endpoint does not create sensor telemetry, alerts, or notification deliveries. Existing measured-water alert thresholds remain the alert basis. The experimental projection adapter is restricted to development mode and authenticated staff.

## 6. Verification completed during implementation

- Latest frontend type check: passed.
- Latest production Webpack build: passed.
- Frontend freshness and rainfall checks: 9 passed.
- Focused backend dashboard integration checks: 6 passed.
- Browser checks confirmed shared map selection, zero forecast dropdowns, equal water/forecast widths, aligned column bottoms, and no horizontal overflow. Only one registered station was available, so switching between multiple real stations remains unverified.
- Earlier in this work, the full backend suite passed 237 tests. That full run preceded the latest rainfall-history and dashboard refinements; the final changes received the focused checks above.
- Firmware build and host tests passed earlier. Physical receipt-to-dashboard timing remains unverified.

No firmware flash, NVS erase, or physical end-to-end rain-gauge trial was performed in this session.

## 7. Remaining work

Verify the gauge pin labels and GPIO4 signal voltage, then perform a controlled physical tip test. Confirm that each tip increments the durable counter, produces 0.70 mm of rainfall, updates the correct station, and refreshes the projection. Test disconnect/reconnect and reboot recovery, then measure actual end-to-end latency.

After that, test multiple registered stations and decide whether to persist projection configuration and consolidate the remaining offline lab. Real water-depth forecasting validation requires measured rainfall and water-level observations with appropriate physical calibration.

Local preview: http://127.0.0.1:3011/dashboard

Relevant implementation files:

- agapay-web/src/components/Dashboard.tsx
- agapay-web/src/components/ForecastTrendPanel.tsx
- agapay-web/src/components/RainfallActivityPanel.tsx
- agapay-web/src/context/MonitoringContext.tsx
- agapay-web/src/context/HybridProjectionContext.tsx
- agapay-backend/app/services/hybrid_projection.py
- agapay-backend/app/services/rain_gauge_service.py
- agapay-firmware/docs/live-rain-gauge-runbook.md
