# Data, review and deployment workflow

No real water-depth candidate, administrator approval, station binding or worker was created in the operational database during this change. Do not activate a model using synthetic fixtures, the ERA5 rainfall demo, placeholder H5/scaler files or bench output demonstrations as field evidence.

## Establish the site and collection protocol

Identify the exact station, coordinates/catchment, local depth target, gauge zero/datum, reliable measurement range, uncertainty and calibration/installation history. Confirm the target is local sensor depth in cm, rather than river stage above an unrelated datum. Obtain permission/licence for every source and retain the original files and checksums. Record event IDs under a reviewed incident-grouping rule, including severe rises and recovery; do not label neighbouring windows from one event as separate test events. Preserve the timeline of what observations and weather products were actually available to the deployment at each issue time.

The current software has no reviewed paired field event set that establishes operational depth accuracy. The existing ERA5 archive is gridded rainfall reanalysis, not paired physical depth truth or evidence that its product was available online at a historical forecast origin. Physical commissioning, field collection, quality review, licences and independent withheld-event evaluation remain required. No agency was contacted or field history invented here.

Prepare a UTF-8 CSV with these columns:

| Column | Meaning |
|---|---|
| `station_id`, `event_id`, `partition` | Exact site, whole incident ID, `train` or `test` |
| `measured_at`, `available_at` | Aware timestamps for observation and first deployment availability |
| `depth_cm`, `quality` | Finite cm value for `valid`; empty/ignored depth for `invalid` |
| `source_class` | `physical_field` after source verification; fixtures use `synthetic_fixture` |
| `datum`, `units`, `configuration_hash` | One reviewed datum, literal `cm`, exact installation hash |
| `rainfall_mm` | Optional observed amount; missing stays missing and is not an input to v1 |
| `rain_interval_start`, `rain_interval_end`, `rain_available_at` | Required aware interval/availability when an amount is present; preserve native intervals and do not sum overlapping snapshots |

Training observations and labels must be available by the declared training cutoff. Withheld origins must be later than that cutoff plus 90 minutes; whole event time ranges cannot overlap. Unknown target times are omitted, not interpolated. Inputs must satisfy the runtime gates: at least 12 valid observations spanning 30 minutes, maximum five-minute gap, latest measured input no older than 120 seconds, and matching site/configuration. The provisional runtime history is the preceding hour with at most 3,600 rows. Review these engineering budgets against actual field cadence before selecting a deployed use.

Start from [model-card.template.json](model-card.template.json), replacing every placeholder with reviewed source information. Its source intentionally defaults to `synthetic_fixture`, which cannot pass operational approval. The invalid placeholder cutoff prevents mistaking the template for a trained artifact. The card records target/units/site/datum, data licence and provenance, calibration history, training cutoff, dataset SHA-256, actual inference features/availability, allowed use, limits and an unavailable fallback.

## Offline candidate preparation

Run from `agapay-backend` using the installed ML-capable environment. Outputs are create-only; choose a new path per candidate. These commands do not collect data, register a model, approve it or change operational forecasts.

```powershell
.venv-auth/Scripts/python.exe -m app.ml.water_depth --csv ../data/reviewed/site-events.csv --card ../data/reviewed/site-card.json --output ../data/candidates/site-depth-v1.json
.venv-auth/Scripts/python.exe -m app.export_prediction_contracts --check
```

The candidate is a transparent JSON depth-delta regression with fixed regularization. No pickle or client-supplied executable is loaded. Preparation bounds input to 100 MiB/one million rows and the bundle to 10,000 withheld origins; review cadence/event selection when those budgets are exceeded. Keep raw observations, event rationale, data exclusions, checksum manifest and the printed reference metrics alongside the candidate. Check severe-event residuals and all horizons; a pooled average gain is not a safety validation. If the candidate does not beat the references under permitted deployment-time inputs, retain unavailable operational forecasts and improve collection/model design rather than weakening the approval gate.

## Register, independently review and bind

1. Stop serving/writers, back up and rehearse restoration. Apply reviewed main schema HEAD `0004_forecast_registry` through `python -m app.migrations --apply --writers-stopped --backup-confirmed`. Do not reset or seed. A separate copy-only preservation rehearsal is available through `app.verify_upgrade`; it never migrates the original.
2. An active administrator may explicitly register the offline candidate with `python -m app.register_forecast --bundle ../data/candidates/site-depth-v1.json --admin-id <actual-administrator-id>`. This creates a **draft**, addressed by its canonical bundle SHA-256. Model weights, card and test evidence are immutable in the application; changing them requires a new ID. No HTTP upload/file-path evaluation endpoint exists.
3. In web **ML Evaluation**, a different active administrator reviews the candidate and original evidence. The registrant cannot approve their own bundle. Record the reason and SHA-256 of the externally retained independent-review evidence. Numeric gates require real source declaration, disjoint training/withheld events and value over persistence/rate references at every horizon. They do not replace domain approval, physical proof or licence review. Do not enter credentials or private contact information in reasons.
4. Select the station and approved candidate, enter a binding reason and save the displayed binding version. The server requires matching site, datum and exact current **field-reviewed** installation hash. A 409 locks editing until explicit refresh/manual review; nothing automatically retries a stale change. Approval alone does not publish, and binding alone does not fabricate a current forecast.
5. Rehearse the bounded publisher on an isolated environment using `python -m app.forecast_worker`. It processes approved bindings only; untrained/unapproved/invalid/stale sources produce no numeric publication. Never use the test suite's synthetic approval fixture as a deployable candidate.
6. Once actual field/independent evaluation and infrastructure acceptance pass, enable the `forecasting` profile's supervised `python -m app.worker_service forecasts` in `deploy/compose.production.yaml`. It ticks every ten seconds and has station budgets/heartbeat progress. It uses protected database-held JSON weights and does not depend on development hybrid mode. Add `forecasting` to `AGAPAY_OPERATIONS_REQUIRED` only when the deployment promises that capability. The template leaves that profile disabled.

Model-review and binding changes record actor, reason, version and evidence/reference IDs in the existing redacted mutation audit. Transport/official-alert authority and resident notification subscriptions are independent. This workflow grants no authority to issue an evacuation order.

## Product and incident response

| State | Behavior |
|---|---|
| No deployed adapter | Untrained/unavailable; no predictions, no demonstration fallback |
| Approved binding, worker/product absent | Forecast unavailable; inspect publisher/readiness |
| Valid published product | Same stored forecast ID/values/metadata for staff and resident |
| Product expired | Latest view returns `stale_data` with null predictions; original record remains historical |
| Model revoked or review version changed | Old binding invalid; manual review/rebinding required |
| Station inactive/maintenance, source identity changed, configuration/datum no longer matches | Old product unavailable; investigate commissioning before publishing again |
| Invalid inputs/output or scientific failure | No new publication; no numeric baseline or demo substitution |

The original cutoff and expiry remain unchanged across reads. Current check times belong to request freshness, not model generation. Latest data and historical record URLs are separate views of the same ID; a record's `current=false` never erases or revises its original values. Forecasts do not update sensor episodes, notifications or authority-issued notices. Measurements retain their own timestamps/quality when forecasting is unavailable.

Operator diagnostics distinguish `FORECAST_NOT_CONFIGURED`, `FORECASTS_WORKER_STALE`, `FORECAST_BINDING_INVALID`, `FORECAST_PRODUCT_UNAVAILABLE` and `FORECAST_STATION_BUDGET_EXCEEDED`. Treat these separately from experimental `MODEL_ARTIFACT_UNAVAILABLE`. Fix capacity/configuration/collection causes; do not prolong expiry or turn on the private experiment to clear an operational fault. Disabling the station binding or revoking approval stops availability without deleting previous products. Retain immutable records under the deployment's reviewed audit/storage policy; no automatic destructive purge is enabled.

## Private experiment and contract maintenance

`POST /api/hybrid-projections/{station_id}` and its legacy summary are staff-only, development-gated private experiments. They cannot write the operational registry, binding or publication tables. Ordinary rain panels use `GET /api/rain-activity/{station_id}`, which returns observations and an empty projection list in development or production. Changing browser basin/manual/history settings cannot affect that observation endpoint or a resident forecast ID.

ML Evaluation resolves the active experimental model directory/dataset through backend settings, matching inference, and shows their hashes and the separate evaluation hash. Its rainfall errors are never presented as water-depth accuracy. Replacing a configured artifact must update its manifest/dataset/evaluation coherently and pass integrity checks; invalid/missing files produce an unavailable experimental view. Production water-depth publication uses its approved database-held bundle and works with hybrid experiments disabled.

After a contract change, run `python -m app.export_prediction_contracts`, review the OpenAPI diff and regenerate TypeScript/Dart metadata manifests/shared cases together. Run `--check`, the cross-client corpus tests and role/expiry/configuration tests before deployment. Shared fixtures are explicitly synthetic and cannot authorize an operational adapter. Preserve all previous migration snapshots; never restamp/reset a live database.

Remaining acceptance requires actual field target/datum agreement, paired acquisition/quality/licence evidence, independently withheld real events, severe-event and fallback review, deployed PostgreSQL concurrency/restore and supervised publisher/receiver fault drills. No such real-world result is claimed by software tests.
