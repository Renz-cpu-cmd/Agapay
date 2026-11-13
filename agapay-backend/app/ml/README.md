# AGAPAY historical data collection

The collection utilities run offline from FastAPI, SQLAlchemy, MQTT and notification workers.
They never load `.env`, connect to the application database, train a model or
publish predictions. The separately authorized [hybrid demonstration](hybrid_demo/README.md)
trains rainfall regression and models a controlled basin, while keeping operational
forecasts and safety functions separate. Existing `model.h5`, `scaler.pkl` and `train_model.py` are
empty placeholders and remain untouched. The existing forecast contract uses
local `water_depth_cm` at 30/60/90 minutes and currently has no trained predictor.

The requested `AGAPAY_Complete_Semester_Execution_Plan_FINAL_REVISED.docx` and
`AGAPAY_ML_Data_Collection_Starter` were not found in this checkout. Phase 6 could
not be checked against those references; implementation follows the supplied task.

## Setup (Python 3.11+)

Run from `agapay-backend` in PowerShell:

```powershell
py -3.11 -m venv .venv-ml
& .venv-ml/Scripts/python.exe -m pip install -r requirements-ml.txt
& .venv-ml/Scripts/python.exe -m pytest app/ml/tests -q --basetemp .pytest_cache/ml-tests
```

Use a fresh `--basetemp` for each concurrent run; pytest clears that directory.
ML dependencies are intentionally separate from the existing API requirements.
For ordinary environments with writable system temp, `--basetemp` is optional.

## Rainfall collection

```powershell
& .venv-ml/Scripts/python.exe -m app.ml.data_collection.collect_rainfall --location-id urdaneta_example --latitude 15.97430 --longitude 120.56906 --start 2020-01-01 --end 2025-12-31
# Small verification download, configurable date batching and output location:
& .venv-ml/Scripts/python.exe -m app.ml.data_collection.collect_rainfall --start 2025-01-01 --end 2025-01-02 --batch-days 1 --timeout 60 --attempts 3 --data-root ../data
```

The [official archive API](https://open-meteo.com/en/docs/historical-weather-api)
documents `models=era5`, `hourly=precipitation,rain,temperature_2m,relative_humidity_2m`,
`start_date`, `end_date`, `timezone=UTC`, Celsius and mm. Each batch spans at most
366 days by default and includes its two boundary dates; the next batch starts
the following day. Batches can cross calendar years; they never overlap.
Only idempotent GET failures with transport errors or 429/500/502/503/504 retry,
with bounded attempts, backoff, numeric Retry-After and a configurable timeout.
Authorization/parameter errors do not retry. Failed runs retain completed raw
responses and a failure report; reruns get new identities. There is no synthetic
fallback or automatic substitution with a different weather model.

Normalized CSV columns: `timestamp_utc`, `timestamp_original`, `precipitation_mm`,
`rainfall_mm`, `temperature_c`, `relative_humidity_pct`, `station_id`,
`dataset_source`, `rainfall_interval_seconds`.

`urdaneta_example` is a provisional geographic label, **not a verified station**.
ERA5 is gridded reanalysis, not direct rain-gauge observations. Requested and
returned grid coordinates both appear in the manifest; they can differ.
Hourly resolution is retained. Rain and precipitation are separate fields:
total precipitation includes rain and other precipitation; never add them together.
The documented rain and precipitation timestamps describe the **preceding hour's
sum**; temperature and humidity are instantaneous at the indicated hour.
Requests use UTC and normalized timestamps include `+00:00`. To display Philippine
time, use `pd.to_datetime(df.timestamp_utc, utc=True).dt.tz_convert('Asia/Manila')`.
The six-year UTC range displays locally from January 1, 2020 at 08:00 through
January 1, 2026 at 07:00. Local-date coverage is therefore different from UTC dates.

Attribute data to Open-Meteo and the ERA5/Copernicus providers. Consult the
[current terms](https://open-meteo.com/en/terms): data attribution under CC BY 4.0
does not remove the free service's non-commercial limits or rate limits.

## Water-level import

Supply the provider's original CSV, XLSX or XLS and JSON metadata. No macro
execution, PDF/OCR, dashboard scraping or station endpoint discovery is attempted.
Date/time columns must be ISO dates or actual Excel date cells; Excel serial
numbers stored as unformatted numeric values need explicit provider interpretation.
Ambiguous day/month strings should be resolved in a separate reviewed derivative;
the raw original must stay retained. The importer expects one station per file;
map the source station column if present so identity mismatches are detected.

Metadata template (replace all nulls and REPLACE values with provider facts):

```json
{
  "station_id": "REPLACE_WITH_OFFICIAL_ID",
  "source": "pagasa",
  "latitude": null,
  "longitude": null,
  "timezone": "Asia/Manila",
  "reference_datum": "REPLACE_WITH_PROVIDER_GAUGE_ZERO_OR_DATUM",
  "measurement_kind": "gauge_level",
  "units": {"water_level": "m"},
  "interval_seconds": 1800,
  "acquisition_reference": "REPLACE_WITH_OFFICIAL_REQUEST_OR_EXPORT_REFERENCE",
  "license": "REPLACE_WITH_PROVIDER_TERMS",
  "expected_start": "2020-01-01T00:00:00+00:00",
  "expected_end": "2025-12-31T23:30:00+00:00",
  "jump_thresholds": {"water_level": 1.0}
}
```

This is a structural template, not evidence of a station, cadence, datum or license.
Allowed sources are `philsensors`, `pagasa`, `agapay_esp32`. Measurement kinds are
`gauge_level`, `water_surface_elevation`, `local_depth`; allowed units are m/cm/mm.
Jump thresholds use original measurement units and need station-specific review.
If cadence or datum is genuinely unknown, record null/`unknown`; validation and
downstream human review must resolve it before training. No datum conversion is
performed, and negative gauge levels can be legitimate.

```powershell
& .venv-ml/Scripts/python.exe -m app.ml.data_collection.import_water_level C:/official-data/river.xlsx --metadata C:/official-data/station.json --sheet Observations --time-column DateTime --level-column Stage --quality-column QC --unit-column Unit --station-column StationID
# Columns default to timestamp and water_level; absent quality is 'unknown'.
& .venv-ml/Scripts/python.exe -m app.ml.data_collection.import_water_level C:/official-data/river.csv --metadata C:/official-data/station.json
```

Naive timestamps use the explicit metadata IANA timezone. Timestamps carrying
offsets retain their instant and convert to UTC. Original timestamp strings,
measurement strings, provider quality flags, units, datum and measurement kind
are retained. Missing/malformed values produce findings, not invented numbers.
Unresolvable local DST timestamps stay missing. Importer returns exit 1 if the
report contains errors, while preserving source and normalized rows for review.

## Storage, provenance and validation

Default output is repository-root `data/`, independent of current working directory:

```text
data/raw/{open_meteo,philsensors,pagasa,nasa_gpm,agapay_esp32}/<unique run>/
data/processed/<unique run>.csv
data/metadata/<unique run>.json
data/reports/<unique run>.json
```

The entire payload tree is ignored by Git except `.gitkeep` directory skeletons.
Unique run names and exclusive file creation prohibit overwrites by this pipeline;
raw files are not OS-locked against manual edits. SHA-256 hashes detect later
alterations. Preserve them in managed archival storage before sharing evidence.
Manifests retain source/acquisition terms, timestamps, units, requested coordinates,
grid coordinates, request parameters, retrieval instants, row counts, file sizes
and hashes. CSV, report and raw response have separate paths.

```powershell
& .venv-ml/Scripts/python.exe -m app.ml.data_collection.validate_dataset ../data/processed/RUN.csv --metadata ../data/metadata/RUN.json --output ../data/reports/RUN-recheck.json
& .venv-ml/Scripts/python.exe -m app.ml.data_collection.build_manifest --metadata C:/official-data/station.json --raw C:/official-data/river.csv --csv ../data/processed/RUN.csv --report ../data/reports/RUN.json --output ../data/metadata/manual-manifest.json
```

Validation checks missing timestamps/measurements, duplicate instants, finite
numeric values, units, ordering, cadence, coverage, geographic/identity metadata,
UTC serialization and configured jumps. Findings contain severity, count and
up to 25 CSV row numbers (header is line 1). Missing slots are reported separately.
`valid=true` means no structural errors, **not** approval of ground truth,
hydrological matching, quality flags, extreme values or model readiness. Warnings
require review. No observations are sorted, dropped, deduplicated or interpolated
by collection/import/validation. Preprocessing rejects ambiguous series first.

## Preparation without training

```python
import pandas as pd
from app.ml.data_collection.preprocess import (
    prepare_features, add_forecast_targets, chronological_split,
)

water = pd.read_csv("../data/processed/OFFICIAL_WATER_RUN.csv")
rain = pd.read_csv("../data/processed/RAINFALL_RUN.csv")
features = prepare_features(
    water, rain,
    pairing_confirmed=True,  # only after verifying watershed/grid relevance
    accepted_quality_flags=("good", "valid"),  # replace with provider's policy
    rainfall_available_delay_minutes=0,  # retrospective, not a real-time claim
)
labeled = add_forecast_targets(features, measurement_kind="gauge_level")
parts = chronological_split(labeled, embargo_minutes=90)
input_columns = ["water_level", "water_level_rise_per_minute", "water_level_mean_60m",
                 "water_level_missing", "rainfall_mm", "rainfall_accumulation_3h_mm",
                 "rainfall_missing", "rainfall_age_minutes"]
# Only input_columns may enter X; target_* fields belong in y/label bookkeeping.
# No estimator, scaler or model is fitted by these utilities.
```

Water targets require real quality-reviewed water records and exact timestamp
matches at +30/+60/+90 minutes. Irregular/missing matches remain null. Hourly
water records cannot supply independently observed 30/90-minute labels.
Unaccepted/missing quality flags mask values only in derived features/targets;
raw and imported datasets are untouched. Rainfall is joined backward with a
one-native-interval tolerance. Three-hour accumulation is computed **before**
joining, once per native rainfall interval; gaps invalidate the accumulation.
Rainfall is never subdivided into fabricated sub-hour measurements.
Rate of rise uses real elapsed minutes; rolling water means include only current
and past accepted samples and may be partial near gaps/start. Split purges
examples whose future label times cross the next partition (plus embargo).
Fit any future scaler/imputer on training inputs only; never interpolate labels,
mix station datums, use centered/future rolling windows or include target fields
in present-time inputs. Provider quality masks and retrospective reanalysis must
also be audited against the intended online information availability.

ERA5 and IMERG research products are delayed/revised. Historical timestamps are
not proof the value existed in real time. Use product-specific availability
delays and a deployable rainfall source for eventual operational evaluation.
Gauge-level targets remain gauge-level targets; they cannot be served as the
current API's local-depth forecasts without a separately justified datum mapping.

## Acquisition steps and training prerequisites

See [collection status](COLLECTION_STATUS.md) for verified download evidence and
source links. Request official Pangasinan/Agno station catalogs, exact identities,
coordinates, gauge datums and changes, native timestamps/timezones, water-level
and rainfall history, quality flag definitions, gaps and redistribution terms.
Confirm hydrological relevance instead of choosing solely by proximity.

Once matched records are acquired, review all findings, preserve a reviewed
derivative and split chronologically with the horizon purge. Evaluate persistence
and linear-trend baselines **before** LSTM/GRU. Report MAE/RMSE per horizon in the
correct level/depth units; precision/recall/F1 need independently defined flood
thresholds in that station's datum, and warning lead time needs documented event
onsets. No accuracy or flood-detection metrics exist for this delivery.
