# Evaluation and clean-build runbook

Run backend commands from `agapay-backend`, web commands from `agapay-web`, and Flutter commands from `agapay-mobile`. These commands do not migrate a live database, contact a notification provider, flash hardware or approve a model automatically.

## Prepare and evaluate a candidate

Extend the F34 CSV with whole-event `partition` values `train`, `calibration`, `test`. Include an hour of pre-roll for each event. Each evaluated origin needs exact +30/+60/+90-minute observed truth; missing target labels are omitted and must be reviewed in the collection/coverage audit. After pre-roll, failed test input windows with known targets are retained as unavailable cases. The CSV may include a reviewed `storm_intensity` label. Do not infer an extreme storm from depth or reuse training events as calibration events.

Start with [provisional-decision-policy.json](provisional-decision-policy.json). Review event definitions, all three threshold tradeoffs, required storm-intensity labels, local season grouping, uncertainty, width/gain/coverage requirements and allowed seasons/use with the responsible domain reviewers. The provisional file intentionally cannot pass operational approval. Preserve the genuine policy evidence outside the bundle and reference its digest when a reviewed version is prepared. The existing station-config and independent model review remain mandatory.

```powershell
.venv-auth/Scripts/python.exe -m app.ml.water_depth --csv ../data/reviewed/site-events.csv --card ../data/reviewed/site-card.json --decision-policy ../data/reviewed/site-policy.json --output ../data/candidates/site-depth-v2.json
.venv-auth/Scripts/python.exe -m app.ml.decision_evaluation --bundle ../data/candidates/site-depth-v2.json --output ../data/reports/site-decision-v2.json
.venv-auth/Scripts/python.exe -m app.ml.decision_evaluation --bundle ../data/candidates/site-depth-v2.json --drift-input ../data/reviewed/recent-features.json --output ../data/reports/site-drift-v2.json
```

The training domain is derived only from training features. Constant/range-degenerate inputs require revised collection/model design, not a fabricated range. Drift input is a strictly increasing array of `{ "measured_at": "aware timestamp", "features": [depth_cm, rate_cm_per_minute] }`, using exactly the causal feature implementation. Reports are create-only and bounded. They do not mutate registration, approval, station binding or alerts. Retain raw sources, missing-target coverage, event rationale, all reports and their hashes for review.

## Dependency profiles and contracts

Create a new Python 3.12 environment for each CI profile; do not rely on an existing development environment:

```powershell
python -m venv .ci-venv
.ci-venv/Scripts/python.exe -m pip install -c requirements-lock.txt -r requirements-ci-core.txt
.ci-venv/Scripts/python.exe scripts/run_test_profile.py core
.ci-venv/Scripts/python.exe -m app.export_prediction_contracts --check
```

Use `requirements-ci-ml.txt` / `ml` for offline preparation tests and `requirements-ci-hybrid.txt` / `hybrid` for estimator/physics/API integration. The latter generates a tiny synthetic JSON forest and rain series under the test temporary directory. No training dataset download or ignored artifact is required. Linux uses `.ci-venv/bin/python`. The common constraints pin resolved versions, including platform-specific uvloop for Linux; changing them requires resolver, security and profile revalidation. Windows execution is not proof of Linux wheel/container compatibility.

`python scripts/validate_clean.py --profile core` creates an allowlisted source copy under ignored `.ci-check/`, creates a fresh venv and installs/runs that profile plus contract drift checks. Other profiles are selectable. It includes new source files and excludes `.env`, existing environments, databases, operational journals, credentials and ignored training data. Keep the printed path/log for inspection. It never deletes or resets the original repository. This source snapshot supplements hosted clean-checkout CI; it is not a claim that untracked work has been committed.

From web, run `npm ci`, `npm test`, `npm run typecheck`, `npm run build -- --webpack`, `npx playwright install chromium`, then `npm run test:browser`. On a Windows machine with installed Chrome, set `AGAPAY_BROWSER_CHANNEL=chrome` for the browser command. CI uses `npx playwright install --with-deps chromium`. The workflow allocates its own loopback ports, fake users and synthetic product; no production API/account/Maps service is used. Flutter runs `flutter pub get`, `flutter analyze`, `flutter test`. Updating contracts requires exporting and reviewing all schema/generated/corpus files together.

Security checks use an isolated tooling environment with `pip-audit==2.10.1`, then `python -m pip_audit -r requirements-audit.txt --strict`; that requirements file includes the profile constraints. Web uses `npm audit --audit-level=high`. Investigate findings; do not ignore advisories or use a forced major upgrade without assessing behavior.

## Container and approved artifact packaging

```powershell
docker build --target core -t agapay-core:review agapay-backend
docker build --target hybrid -t agapay-hybrid:review agapay-backend
```

Run those two commands from the repository root. Default builds end in the core production profile. Hybrid is an explicit research runtime and has no automatically copied dataset. These builds are not deployment approval and do not bypass production startup validation.

For a genuinely approved model, export from the registry using a real active administrator and retained redistribution/licence evidence. Choose a new output directory; do not overwrite an earlier release. No qualified field model is supplied by this change.

```powershell
python -m app.forecast_release --model-id ACTUAL_MODEL_SHA256 --admin-id ACTUAL_ADMIN_ID --license-evidence-sha256 ACTUAL_LICENSE_REVIEW_SHA256 --output forecast-release
python -m app.forecast_release --verify forecast-release --expected-manifest-sha256 TRUSTED_MANIFEST_SHA256
docker build --target forecast-artifact --build-arg FORECAST_MANIFEST_SHA256=TRUSTED_MANIFEST_SHA256 -t agapay-forecast:review .
```

The exporter requires independent registry approval and all current decision gates. Preserve the printed manifest hash in a protected release record or integrity-checked artifact registry; a checksum transported alongside attacker-editable files is not an authenticity boundary. The Docker target checks this external hash, bundle hash, model/site/licence identity and review references. It does not import, approve or bind the artifact automatically. Revalidate current approval and field configuration in the target deployment; revoked approval in the source registry does not magically revoke an offline copy.

## Monitor and roll back

Inspect `FORECAST_INPUT_OUT_OF_DOMAIN`, `FORECAST_INPUT_UNAVAILABLE`, worker heartbeat and product-expiry diagnostics. A failed publisher input gate withholds an older forecast; measurements/hazard observations remain independent. Retain a labeled drift/evaluation report and assess the cause. For confirmed regression, use web ML Evaluation to disable the station binding or revoke the model with current version, reason and evidence. A stale write requires manual refresh. No automatic rollback to a different unreviewed model, replay, retraining or uncertainty widening is enabled.

Before field activation, independently validate event grouping, physical datum/uncertainty, severe/negative events, seasonal/site/missingness coverage, interval assumptions, actual warning lead-time annotation, fallback and chosen miss/false-alarm tradeoffs. Source declarations, synthetic tests, package hashes and this runbook are not substitutes for those observations.
