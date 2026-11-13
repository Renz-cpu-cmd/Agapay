# Collection status — October 12, 2026 (Asia/Manila)

## Verified live acquisition

The official Open-Meteo downloader completed six HTTP 200 archive requests using
`models=era5`. Dataset ID: `urdaneta_example_20261011T231532Z_ed4c1003e2e4`
(identifier uses UTC; collection date in Manila is October 12).

| Property | Observed result |
| --- | --- |
| Requested coordinates | 15.97430 N, 120.56906 E; provisional `urdaneta_example` |
| Returned ERA5 cell | 16.0 N, 120.5 E in all six responses |
| UTC coverage | 2020-01-01 00:00 through 2025-12-31 23:00 |
| Temporal resolution | Hourly, 3,600 seconds |
| Record count | 52,608 |
| Variables | Total precipitation mm, rainfall mm, temperature °C, humidity % |
| Missing values / duplicate times / coverage gaps | None detected |
| Validation findings | None; original report and independent CLI recheck both passed |
| SHA-256 verification | All six raw responses, CSV and original report match manifest |
| Source classification | Gridded ERA5 reanalysis; not station-measured ground truth |

Local artifacts, relative to repository root:

- `data/raw/open_meteo/urdaneta_example_20261011T231532Z_ed4c1003e2e4/` — six exact JSON response byte payloads.
- `data/processed/urdaneta_example_20261011T231532Z_ed4c1003e2e4.csv` — hourly normalized data.
- `data/metadata/urdaneta_example_20261011T231532Z_ed4c1003e2e4.json` — request/batch metadata, grid coordinates, units, provenance and hashes.
- `data/reports/urdaneta_example_20261011T231532Z_ed4c1003e2e4.json` — original validation report.
- `data/reports/urdaneta_example_20261011T231532Z_ed4c1003e2e4-recheck.json` — independent CLI revalidation.

These data artifacts are intentionally ignored by Git. No commit, push,
deployment, application database modification or ML training was performed.

## External source access

| Source | Actually acquired in this task | Documented access / remaining work |
| --- | --- | --- |
| [Open-Meteo historical API](https://open-meteo.com/en/docs/historical-weather-api) | 52,608 hourly reanalysis records | Complete for the provisional point/range. Confirm river location and catchment representativeness. Respect [API terms and data attribution](https://open-meteo.com/en/terms). |
| [DOST-ASTI PhilSensors](https://philsensors.asti.dost.gov.ph/site/about) | No historical water-level records | Official About page describes historical datasets provided on request and institutional historical/realtime API access. The supplied `/site/data` page failed to load through the research tool. No anonymous bulk water-level API, endpoint or confirmed station ID was established; request approved access and a Pangasinan/Agno catalog. Public last-24-hour displays do not establish bulk-download permission. |
| [PAGASA climate data](https://www.pagasa.dost.gov.ph/climate/climate-data) | No historical water-level records | Official page offers raw climatological Excel requests and an academic researcher process; these are not automatically a river-level archive. For stage/telemetered water-level data contact Hydro-Meteorology / Agno River Basin Flood Forecasting and Warning Center via [official contact channels](https://www.pagasa.dost.gov.ph/contact-us). The [Citizen's Charter](https://pubfiles.pagasa.dost.gov.ph/pagasaweb/files/PAGASA%27s_CITIZENS_CHARTER_4th_EDITION_FINAL.pdf) lists provision of telemetered rainfall/water-level data; verify the current process with the office. |
| [NASA GPM IMERG directory](https://gpm.nasa.gov/data/directory) | No IMERG granules | Directory supplies actual downloadable gridded precipitation products, not river water levels. [IMERG Final Run GES DISC](https://gpm.nasa.gov/node/3328) provides documented subsetting/download links. [GES DISC archive](https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/) requires Earthdata Login and application authorization; PPS also documents registration. User must establish authorized access and choose product/version/catchment subset. Preserve quality/fill values and rate-versus-accumulation semantics when adding a dedicated IMERG adapter. |
| AGAPAY ESP32 | No historical export acquired | Existing telemetry has local depth and rainfall but unknown rainfall accumulation interval in the prediction contract. Establish measured timestamp/interval semantics and a reviewed export before combining with historical datasets. |

Pangasinan/Agno is a relevant acquisition lead, not a confirmed pairing with the
provisional Urdaneta point. No station identifiers were invented and no requests
were submitted to agencies. The importer is implemented and tested with synthetic
CSV/XLSX fixtures; those fixtures are not collected observations.

For each official request, specify research purpose, location/catchment, desired
2020–2025 coverage (or longest available), native cadence ideally 30 minutes or
finer, river stage and colocated rainfall, station catalog/coordinates, units,
gauge zero/datum history, quality definitions, missing data, timezone and allowed
research/redistribution use. Request official IDs rather than guessing them.
PAGASA's academic climate process lists school ID/registration, approved proposal,
terms of use and an adviser-noted formal letter; the hydrological office must
confirm its own current requirements.

## Implementation inventory

Created `requirements-ml.txt`, `app/ml/__init__.py`, this status report, `README.md`,
`data_collection/{__init__,config,collect_rainfall,import_water_level,validate_dataset,build_manifest,preprocess}.py`,
`tests/{test_collection,test_preprocess}.py`, and eight `data/` `.gitkeep` files.
Modified only root `.gitignore` (ignore data payloads) and backend `.gitignore`
(ignore isolated ML environment). Existing application and user changes remain.
Empty existing model/scaler/training placeholders are retained.

## Commands and verification

Commands ran from repository root or `agapay-backend` as shown:

```powershell
# Repo root: Python 3.12.14 was available in the existing backend environment.
& agapay-backend/.venv-auth/Scripts/python.exe -m venv agapay-backend/.venv-ml
& agapay-backend/.venv-auth/Scripts/python.exe -m pip --python agapay-backend/.venv-ml/Scripts/python.exe install -r agapay-backend/requirements-ml.txt
# Applied final pandas-compatible NumPy bound in the isolated environment:
& agapay-backend/.venv-auth/Scripts/python.exe -m pip --python agapay-backend/.venv-ml/Scripts/python.exe install 'numpy>=1.26,<2.3'

# agapay-backend: offline suite and actual live collection
& .venv-ml/Scripts/python.exe -m pytest app/ml/tests -q --basetemp .pytest_cache/ml-final --tb=short
& .venv-auth/Scripts/python.exe -m pytest tests -q --basetemp .pytest_cache/backend-ml-regression-3 --tb=short
& .venv-ml/Scripts/python.exe -m app.ml.data_collection.collect_rainfall --start 2020-01-01 --end 2025-12-31 --timeout 60 --attempts 3
& .venv-ml/Scripts/python.exe -m app.ml.data_collection.validate_dataset ../data/processed/urdaneta_example_20261011T231532Z_ed4c1003e2e4.csv --metadata ../data/metadata/urdaneta_example_20261011T231532Z_ed4c1003e2e4.json --output ../data/reports/urdaneta_example_20261011T231532Z_ed4c1003e2e4-recheck.json
```

Additional checks: exact record/coverage/missing-value counts, per-batch grid
coordinates, hashes for each manifest entry, ignored payloads versus trackable
directory markers, `compileall`, and `git diff --check`.

Final results: **24 ML tests passed in 2.16 seconds**, with no warnings or failures;
**223 existing backend tests passed in 45.71 seconds**, with 23 dependency/provider
deprecation warnings and no test failures. Compilation and whitespace checks
passed. Web/Flutter suites were not rerun because no application UI was changed.

Environment problems encountered and resolved: sandbox `ensurepip` failed;
installation using the existing environment's pip targeting `.venv-ml` worked
after authorized network execution. System-temp access caused six initial pytest
fixture errors; using workspace `--basetemp` resolved them. Latest NumPy produced
pandas 2.x timedelta warnings; the isolated compatibility bound removed them.
Sandboxed backend regression commands stalled without output and were interrupted;
the diagnostic run outside the sandbox encountered a Windows access violation
during TestClient teardown while the timed traceback hook was active. The final
run without that hook completed all 223 tests successfully. This does not imply
any provider failure or altered measurements.

## Next steps

1. Obtain official historical river records and confirm the actual monitoring
   site/catchment. Import with provider metadata and review all quality findings.
2. Preserve a reviewed derivative with explicit quality acceptance and datum
   semantics; use the existing causal feature and exact-label helpers. No real
   matched water-level/depth targets exist yet.
3. Resolve operational rainfall availability, delays and ESP32 accumulation
   periods; compare historical and deployable sources.
4. Evaluate chronological, purged persistence and linear-trend baselines, using
   MAE/RMSE by horizon. Define station-datum flood events before precision, recall,
   F1 and warning lead-time measurement. Develop LSTM/GRU only after that evidence.

No model accuracy, flood-event detection score or live local-depth forecast is
claimed by this pipeline.
