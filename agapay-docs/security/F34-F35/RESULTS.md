# F34–F35 verification and remaining acceptance

Closeout reviewed on **2026-10-23 (Asia/Manila)**. These are local software results, not a field-model approval or a production deployment. Logs in this folder preserve the individual runs; overlapping test totals must not be added together.

## Finding status

| Finding | Delivered | Still required |
|---|---|---|
| F34 | Causal offline data preparation, persistence/rate references, transparent JSON candidate, model cards, integrity checks, independent review and station-specific deployment gates | Reviewed paired field observations, target/datum agreement, acquisition and calibration evidence, licences, training and independently withheld real-event results demonstrating useful skill |
| F35 | One immutable published product shared by staff web and resident mobile; ID/history views; model/config/source/time metadata; expiry/revocation/configuration guards; isolated private experiments; evaluation from backend configuration; generated OpenAPI contracts | Apply the migration through the deployment procedure, approve a genuinely qualified model, bind its commissioned station, and validate the supervised publisher in the intended environment |

No real model was registered, approved or bound, and no operational forecast worker was enabled. The default operational result remains unavailable/untrained with null predictions. Software fixtures explicitly simulate evidence and cannot establish field accuracy. The safeguards do not constitute independent scientific validation.

## Observed checks

| Check | Observed result | Evidence and scope |
|---|---|---|
| Complete backend and offline ML suite | **637 passed, 1 skipped**, 24 deprecation warnings | [backend-full-final.log](backend-full-final.log); run before the final two read-path optimizations |
| Final backend regression after both read-path optimizations | **70 passed**, 2 deprecation warnings | [backend-read-final.log](backend-read-final.log); forecast registry, shared contracts, prediction adapter, offline depth preparation and operational health |
| Web unit/component/proxy checks | **88 passed** | [web-unit-final.log](web-unit-final.log); includes publication parsing, historical records, registry permissions and stale-write handling |
| Web production build and TypeScript | **Passed** | [web-build-final.log](web-build-final.log); includes forecast history and evaluation routes |
| Flutter suite | **181 passed** | [flutter-full-final.log](flutter-full-final.log); includes cross-client publication fixtures, forecast/controller flows and a narrow-screen historical-record interaction |
| Flutter analysis | **No issues found** | [flutter-analyze-final.log](flutter-analyze-final.log) |
| Generated OpenAPI/TypeScript/Dart/shared-case drift check | **Passed** | [contracts-check.log](contracts-check.log); the final 70-test run also verifies generated outputs against actual OpenAPI |
| Database upgrade rehearsal | **Copy preserved existing rows; integrity and foreign-key checks passed** | [copy-upgrade.log](copy-upgrade.log); source opened read-only; only the isolated copy was upgraded |
| Rehearsal registry inspection | **0 registered models, 0 bindings, 0 products** | [copy-registry-check.log](copy-registry-check.log); migration does not activate a forecast |

The copy rehearsal compared the original account, station, telemetry, alert, SOS, session and notification records, including 131 telemetry rows, seven SOS requests, three alerts and four delivery rows. It is not a backup/restore drill for a deployed PostgreSQL service. The skipped full-suite PostgreSQL test and SQLite concurrency tests do not prove PostgreSQL concurrency acceptance.

The final backend regressions additionally verify that unavailable product reads do not query raw telemetry and that valid viewer reads project the small model card rather than loading training/withheld cases. Publishers still validate the complete bundle. These query assertions are not a station/viewer capacity benchmark.

An earlier attempt to run the final backend regressions was not executed because automatic approval review had reached a usage limit. On continuation, review succeeded and the requested regression run completed with 70 passes. No validation remains blocked by that earlier failure.

## Acceptance exercised in software

- Staff and resident reads of the same published ID agree on forecast values, cutoff, generation, original expiry, model card, station binding and configuration. Historical reads preserve the original product and separately expose whether it is current.
- Concurrent publishers return one product ID for the same input/binding fingerprint. Repeated viewing does not perform inference or prolong expiry.
- Revocation, review-version/configuration/source changes, inactive lifecycle, stale inputs and expired products prevent current numeric availability. Invalid adapter outputs become unavailable rather than zero.
- Registration creates a draft only. The registrant cannot approve their own candidate. Administrative review/binding uses expected versions and records audit evidence; stale writes require manual refresh.
- Synthetic source declarations, insufficient event counts, overlapping train/test event identities, cutoff violations, mismatched calibration and nonfinite output cannot pass the approval gate. Passing that gate still requires independent examination of genuine evidence.
- Residents cannot use private hybrid configuration/inference. Operational rain cards use the observation-only endpoint; missing forecasts do not enter an experiment automatically.
- Backend, TypeScript and Dart share generated publication metadata and synthetic valid/invalid cases, including valid zero, absent identity, malformed hashes, mismatched cutoff/card and invalid timing.

## Deployment and field limits

The live database was not migrated, no real data was trained, no device was flashed, and no external alert was sent. Existing staged work was preserved; this work was not committed or pushed.

Use [RUNBOOK.md](RUNBOOK.md) for the explicit migration, evidence review, model registration, station binding, supervised worker activation and rollback sequence. Real-device collection/calibration, domain review, deployment/restore tests, clean CI/release reproducibility, assistive-technology testing and physical notification receipt are separate evidence levels and are not claimed by these logs. Field uncertainty and release criteria are tracked under F36; clean-build integration is tracked under F37.
