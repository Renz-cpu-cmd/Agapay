# AGAPAY hybrid projection v0.1 — October 13 demonstration

**EXPERIMENTAL — NOT VALIDATED FOR REAL-WORLD FLOOD WARNING**

The October 12 live-integration extension is documented in the
[live rain-gauge runbook](../../../../agapay-firmware/docs/live-rain-gauge-runbook.md).
It adds automatic authenticated rain-feed polling with a separate durable journal,
operator-confirmed 0.70 mm/tip, genuine completed-hour/history-context ML modes,
and an explicitly simulated testing fallback. The historical model remains unchanged.
Physical hardware success still requires the runbook's bench verification.

This prototype trains rainfall regression, then allocates its future hourly
rainfall into a simplified controlled-basin volume balance. It does not train a
river-level/depth model, fit a catchment, change sensor values, modify thresholds,
trigger notifications/evacuation, or replace `/api/predictions`. No migrations or
deployment were performed. Historical references are the downloaded ERA5 dataset;
there are no acquired river-level labels.

## Open the saved demo

The ready-to-use **single HTML file** is:

`data/demo/hybrid_rain_v01_20261012T003510Z_fdaff56583ad/index.html`

Double-click it in Explorer to open it in a normal browser. The complete held-out
rainfall series, saved random forest, calculations, charts and evaluation are
embedded. No CDN, internet, Python, backend, map API, installation or build is
needed for historical replay or archived ML backtesting. Device retrieval is the
one optional network action and requires the authenticated AGAPAY web origin;
it is unavailable in the standalone file. Keep the offline file backed up for
the demonstration. Dataset/model payloads and generated bundles are ignored by Git.

The Next.js dashboard adds **Hybrid projection lab** in the sidebar and the route
`/hybrid-demo`. The generated copy is `agapay-web/public/hybrid-demo/index.html`.
Existing UI edits were preserved. Start the web project normally and open that
route; public demo data need no account, but device monitoring still enforces
the existing staff/session authorization.

An optional loopback-only FastAPI demo server is also available. From backend:

```powershell
$HybridModelPath = '../data/models/hybrid_rain_v01_20261012T003510Z_fdaff56583ad'
$HybridBundlePath = '../data/demo/hybrid_rain_v01_20261012T003510Z_fdaff56583ad/index.html'
& .venv-ml/Scripts/python.exe -m app.ml.hybrid_demo.server $HybridModelPath --bundle $HybridBundlePath --port 8011
# Open http://127.0.0.1:8011; Ctrl+C stops only this local demo.
```

The demo server has `/api/evaluation` and `POST /api/project`, with manual initial
depth, mode, hourly origin, basin parameters and optional current rainfall
history. It imports no operational database/worker modules. It refuses posted
sensor claims; the browser uses existing authenticated monitoring for device
initialization. This endpoint is local demonstration infrastructure, not a
production service.

## Modes and input provenance

1. **Historical replay** uses actual archived future ERA5 rainfall for a chosen
   held-out-year timestamp and a manual configured starting depth. Every run is
   labeled historical simulation. The wet-example shortcut selects an event
   retrospectively using archived rainfall; it is explicitly not predictive
   event selection. No archived water depth is invented.
2. **ML-assisted projection** has two rainfall input choices:
   - **2025 held-out historical backtest** uses only the preceding 24 completed
     hours to predict the next three hours. Archived future values never enter
     this model's input or hydrological forcing. It remains a historical test,
     not a live 2026 forecast.
   - **Current supplied hourly observations** requires exactly 24 nonnegative
     finite hourly rainfall amounts, oldest to newest, and the most recent
     completed UTC-hour boundary. No automatic archived-data substitution exists.
     Amounts are user supplied; the interface cannot certify measurement origin.
     Input transfer from ERA5 reanalysis to a physical gauge is unvalidated.

Rainfall values are **mm per completed hour**, not rates of unknown duration,
not cumulative gauge totals and not the current incomplete hour. The ESP32
prediction contract currently has an unknown rainfall accumulation interval;
therefore that telemetry rainfall is not automatically fed to this hourly model.
Prepare valid hourly gauge totals and timestamp semantics before a live run.

Manual starting depth is labeled configured. To use a real device depth, choose
current rainfall mode, select ESP32 depth, enter the official station ID, confirm
the sensor measures this **controlled demonstration basin**, and read the latest
valid observation. The existing `/api/account/monitoring/stations` proxy supplies
the backend observation. The UI rejects non-device/simulator sources, invalid or
missing depth, offline/stale snapshots, missing/future/old observation timestamps,
and rechecks freshness when generating. Changing station invalidates the cached
reading. If the source fails, it reports the failure; select manual depth
explicitly instead. No fresh physical ESP32 reading was verified during this task.

The trajectory includes the measured/manual initial point and modeled future
points. A manual point is not an observed water measurement. All modeled outputs
are advisory, separately displayed/exported, and never written into telemetry.

## Physical model and time alignment

For each step:

```text
inflow_m3 = rainfall_mm / 1000 * contributing_area_m2 * runoff_coefficient
requested_outflow_m3 = outflow_m3_per_hour * step_minutes / 60
actual_outflow_m3 = min(requested_outflow_m3, stored_volume_m3 + inflow_m3)
depth_next_m = depth_current_m + (inflow_m3 - actual_outflow_m3) / basin_surface_area_m2
```

Depth is capped at basin capacity; excess volume is returned as overflow.
Drainage is capped by available water; unmet outflow is reported separately.
Negative or nonfinite rainfall, invalid initial depth, invalid areas/runoff or
outflow are rejected. A final depth clamp prevents floating-point rounding above
capacity during repeated overflow. All five parameters have explicit
`measured`, `estimated` or `assumed` provenance selectors. Defaults (2 m² collection,
0.1 m² basin, runoff 0.8, zero outflow, 100 cm capacity) are **assumptions**, not
hardware measurements or river parameters.

The model directly predicts three future hourly totals. In a historical run,
+30/+60 use half/all of the first hour and +90 adds half of the second.
In a current run starting partway through an hour, steps split at the actual
hour boundary; up to the third predicted hour can be needed. Uniform rainfall
within each hour is an explicit approximation, not a separately validated
30-minute rainfall forecast. Storage/outflow behavior within each substep is
likewise simplified; no basin calibration or hydraulic routing is claimed.

Run JSON records created/projection/rainfall-origin timestamps, target times,
initial source and observation time, model version, source dataset hash,
parameter provenance, rainfall inputs, depth projections, inflow/outflow,
overflow/unmet outflow and assumptions. Historical projection times differ from
the actual generation timestamp, and are labeled accordingly.

## Model, reproducibility and genuine evaluation

Model directory: `data/models/hybrid_rain_v01_20261012T003510Z_fdaff56583ad/`.
Artifacts: `rainfall.joblib`, `forest.json`, `metadata.json`, `evaluation.json`.
Use joblib only with trusted locally trained files; pickle-style loading is not
safe for untrusted artifacts. Browser inference uses the exported tree arrays,
not pickle. [scikit-learn persistence guidance](https://scikit-learn.org/stable/model_persistence.html)
describes these trust/version constraints.

Dataset: 52,608 hourly records, 2020–2025, provisional `urdaneta_example`,
Open-Meteo ERA5 reanalysis. Source CSV SHA-256:
`14f574e1a4d063a4607ca841b7ed7fefc99a4dbe8aee5a5fd0b4fb46d47425fb`.
ERA5 is delayed/revised gridded rainfall, not a real-time rain gauge.
Preserve [Open-Meteo terms/attribution](https://open-meteo.com/en/terms) and
Copernicus/ERA5 attribution when distributing the demo and data.

Features: current completed-hour rainfall plus 23 lagged hours, preceding
3/6/12/24-hour accumulations, and UTC hour/weekday/month sine/cosine pairs.
No future weather values or water measurements are used as training features.
[RandomForestRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html)
uses 24 trees, leaf minimum 16 and seed 42. Max depths 6 and 10 were compared
using 2024 validation MAE; depth 10 was selected. Training uses only 2020–2023;
2025 is held-out testing. Training/validation rows whose +3-hour label crosses
the next split boundary are purged. No refit on validation/test occurred. Past
observations preceding a held-out origin are permissible causal input; future
test targets never become inputs or training labels.

Pooled held-out +1/+2/+3-hour scores (26,271 labels at 8,757 origins):

| Method | MAE mm | RMSE mm | Wet MAE mm | Wet RMSE mm |
| --- | ---: | ---: | ---: | ---: |
| Random forest | 0.2965 | 0.7752 | 0.6856 | 1.2682 |
| Persistence | 0.3236 | 0.9252 | 0.7999 | 1.4914 |
| Zero rainfall | 0.3823 | 1.1835 | 1.0679 | 1.9779 |

Wet means **observed target hourly rainfall ≥0.1 mm** (9,405 pooled labels).
Persistence repeats the last completed-hour amount at every future horizon.
The model's +1-hour MAE (0.2466) is slightly worse than persistence (0.2422);
the interface discloses this. Full validation/test/per-horizon values and counts
are in `evaluation.json`. These are rainfall metrics only; there are no
water-depth accuracy, flood-event precision/recall/F1 or warning lead-time scores.

## Rebuild and verify

From `agapay-backend`, Python 3.11+:

```powershell
& .venv-ml/Scripts/python.exe -m pip install -r requirements-hybrid.txt
& .venv-ml/Scripts/python.exe -m app.ml.hybrid_demo.rainfall
# Training prints a new model directory; substitute it below if retraining.
$HybridModelPath = '../data/models/hybrid_rain_v01_20261012T003510Z_fdaff56583ad'
& .venv-ml/Scripts/python.exe -m app.ml.hybrid_demo.build_demo $HybridModelPath
& .venv-ml/Scripts/python.exe -m app.ml.hybrid_demo.build_demo $HybridModelPath --output ../agapay-web/public/hybrid-demo
& .venv-ml/Scripts/python.exe -m app.ml.hybrid_demo.verify_artifacts $HybridModelPath
& .venv-ml/Scripts/python.exe -m pytest app/ml/tests -q --basetemp .pytest_cache/hybrid-tests
node --test app/ml/tests/hybrid_browser_test.cjs
& .venv-auth/Scripts/python.exe -m pytest tests -q --basetemp .pytest_cache/hybrid-backend-regression
```

From `agapay-web`: `npm run typecheck` and `npm run build -- --webpack`.
Model/data files stay local and are ignored by Git; new checkout setup must
restore them or retrain/rebuild. The HTML alone is the portable offline fallback.

## Observed verification and limitations (October 12, 2026)

- 45 Python ML tests passed (one FastAPI/httpx deprecation warning).
- Five JavaScript tests passed, including repeated-overflow rounding protection.
- All 223 existing backend tests passed (23 existing dependency/provider warnings).
- Web typecheck and production Webpack build passed; `/hybrid-demo` is generated.
- Artifact SHA-256 checks passed; browser predictions match saved scikit-learn
  predictions at 100 held-out origins, max difference `8.88e-16` mm. Python and
  browser hydrological calculations match.
- Live local browser verified integrated route, historical replay, ML backtest,
  current-mode missing-input rejection, and a wet replay capped at 40 cm with
  24.720 L modeled overflow. Desktop width 1280 had no horizontal overflow; the
  normal narrow browser viewport also displayed the responsive layout.
- In-app browser policy blocks `file://` URLs, so direct file opening was not
  automated. The same entirely embedded HTML was verified over local HTTP.
  Open the file in a regular browser yourself for the server-free rehearsal.
- Sandbox TestClient runs stalled and sandbox Webpack directory creation failed;
  authorized runs outside the sandbox completed. A strict floating-point test
  comparison was corrected to tolerance. Browser testing found a real repeated
  overflow rounding edge, fixed in Python and JavaScript and regression-tested.
- No fresh physical ESP32 reading or live hourly gauge history was verified.
  Manual starting depth plus archived replay/backtest is the verified demo path.
- Temporary verification servers are stopped at teardown; restart normally
  for the web route or use the standalone HTML.

Created this package (`rainfall.py`, `hydrology.py`, `engine.py`, `build_demo.py`,
`verify_artifacts.py`, `server.py`, `demo.html`, `demo.js`, `__init__.py`, this
README), `requirements-hybrid.txt`, Python/JS tests and the new Next page.
Modified only the sidebar (demo link) and root `.gitignore` (generated bundle).
Existing collection utilities, runtime prediction API, database and firmware
safety functions remain unchanged.

## Tomorrow's demonstration

1. Back up the standalone HTML. Open it, choose the wet historical replay,
   explain the manual initial depth and assumed controlled-basin parameters.
2. Switch to the same date in ML-assisted historical backtest. Explain that only
   past rainfall enters the saved model; the future forcing is predicted.
3. Show evaluation and its baselines, overflow handling, timestamps and run JSON.
4. Use ESP32 initialization only if a fresh valid controlled-basin measurement
   and complete current hourly rainfall history are available. Otherwise use the
   manual, explicitly historical demonstration.
5. Describe the next research steps: physical basin calibration, real gauge
   input/interval validation, source-transfer evaluation, official matched river
   levels and catchment/datum modeling, and depth/persistence/trend baselines
   before any operational river-warning claim.
