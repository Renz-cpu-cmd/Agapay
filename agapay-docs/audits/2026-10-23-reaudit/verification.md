# Re-audit verification — 23 October 2026

## Fresh results from this review

| Check | Observed result | Evidence / limit |
|---|---|---|
| Complete backend + offline ML suite | **698 passed, 1 failed, 1 skipped**, 24 warnings, 947.40 seconds | `backend-full.log`; the run is not green |
| Isolated staff-workspace module after that failure | **7 passed**, 2 warnings | `staff-isolated.log`; overlaps the complete suite and does not replace its failure |
| Web unit/component/contracts | **112 passed** | `web-tests.log` |
| Flutter analysis | **No issues found** | `mobile-analysis.log` |
| Complete mobile unit/widget suite | **225 passed** | `mobile-tests.log`; mocked APIs, storage and platform interfaces |
| Firmware real source against host fakes | **All four profiles pass**: default, cardboard bench, unprovisioned, release | `firmware-host-*.log`; no ESP32 flash or physical acquisition |
| Negative firmware release guards | **Pass**: rejects bench/unprovisioned release combinations | `firmware-release-guards.log` |
| Public mobile release policy | **2 tests passed** | `mobile-release-policy.log`; synthetic packages, no organizational signing key |
| OpenAPI / TypeScript / Dart forecast drift | **Matches** | `forecast-contract-drift.log` |
| Production web security-header/CSP runtime | **Pass**: 12 SSR scripts carry document nonce; new nonce per request; required headers/no-store | `csp-runtime.log`; isolated loopback listener, no session/form/provider calls |
| Missing-coordinate probe | **R1 reproduced** | `map-coordinate-probe.json`; real TypeScript transform, synthetic station input |
| Configuration review-status probe | **R4 reproduced** | `configuration-review-probe.json`; synthetic authenticated fixture and shared ingestion services, in-memory DB, one notification intent, zero deliveries/sends |
| Queue pagination probe | **R5 diagnosis supported**: target absent on first page, present on second | `queue-pagination-probe.json`; 21 synthetic in-memory episodes, actual queue query |
| Git whitespace / preservation | **Diff check passed; 48 pre-existing staged paths retained** | No staging, commits, push, reset or product-source edits |

Backend command:

```powershell
# From agapay-backend; tests/conftest.py selects and owns its disposable agapay_test.db.
./.venv-auth/Scripts/python.exe -u -m pytest tests app/ml/tests -q --tb=short --basetemp .pytest_cache/end-to-end-reaudit
```

The failure is `tests/test_staff_workspaces.py::test_provenance_cannot_be_relabelled`, line 40. Its unverified-scope membership assertion reads only the first default page. The fixture clears provenance across cases while retaining earlier alert rows. Those older rows become unverified and can precede the target advisory. The isolated module passes, and the controlled query probe preserves the target on page two. This is a test-isolation/pagination failure, not demonstrated unauthorized physical-source promotion. It still blocks claiming a green complete suite until corrected and rerun.

The skipped test is the opt-in PostgreSQL restore test: no `AGAPAY_TEST_POSTGRES_URL` target was configured. The inspected local Python environments also lacked the PostgreSQL driver. No package/engine was installed to manufacture a claimed result, and no deployment database was selected. Isolated Mosquitto cases were not skipped in the complete run; PostgreSQL results cannot be inferred from them or SQLite tests. Warnings were 2 dependency deprecations and 22 Firebase SDK token deprecations; warnings are retained in the full log.

## Existing same-source evidence reviewed

The immediately preceding implementation verification recorded a successful production web build and four production browser workflows, including **24 automated axe scans with zero violations**. See [the scoped validation record](../../design/shared-vocabulary/validation.md). Those browser workflows were not rerun in this review, because product source did not change; the CSP runtime check did execute again. The scans are synthetic fixtures and do not cover every populated page, provider error, assistive technology or scenario combination.

Earlier F37 evidence contains a sanitized clean-source/dependency-profile rehearsal, but not a hosted clean run of the complete current committed implementation. Earlier firmware records include actual target compilation; this review reran host logic/guards and did not produce a newly protected/flashed field image. Earlier encrypted-restore evidence uses a tiny disposable SQLite package and does not establish managed PostgreSQL or full-service RPO/RTO.

Native screen-reader sessions, resident/officer task comprehension, physical phone push/background/upgrade tests, actual sensor calibration and field-model qualification remain unmeasured here. No full physical-device → intended broker/network → deployed backend/worker → installed resident phone acceptance chain was exercised.

## Probe safety and scope

The two Python probes force `sqlite:///:memory:` before importing the application, disable MQTT/observability/shared-cache producers, and use synthetic accounts/stations/credentials. They do not run the application lifespan, contact SMTP/FCM, start a notification worker, migrate a real database or share pytest's disposable DB. The review-status probe tests shared services under development settings; the missing production review-status check is source-confirmed, not a claim of tested production exposure.

The initial review-status probe failed schema validation because its synthetic firmware version lacked semantic-version syntax. The retained script was corrected to `0.4.0-synthetic-audit`, then completed and produced the JSON evidence. That probe correction is not a product fix or an additional passing test-suite result.
