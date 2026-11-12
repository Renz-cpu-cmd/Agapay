# F36–F37 observed results

Verified locally on **2026-10-23 (Asia/Manila)**. No field model was trained/approved/deployed, no live database was migrated and no operational notification was sent. Changes remain uncommitted; the original 48 staged paths were preserved.

## Status

- **F36 software controls implemented; field acceptance pending.** Separate calibration/test events, event-based intervals and bootstrap estimates, threshold misses/false alarms/lead time, event peaks, subgroup/coverage reports, reviewed-policy gates, training-domain rejection, drift reporting, publisher input gates, operator faults and client interval/precision contracts are implemented. Tests use synthetic evidence only. Actual scientific claims require independent real-event validation and reviewed operational tradeoffs.
- **F37 implementation and local clean-source rehearsal complete; hosted execution pending.** CI has core/ML/hybrid dependency profiles, cross-client contract drift, web/unit/browser checks, Python/npm audits, a core container build and a disposable PostgreSQL restore job. Synthetic hybrid fixtures remove dependence on ignored datasets. A protected manifest-hash/licence-evidence export/build path is available for genuinely approved registry models. No qualified field artifact is supplied.

## Local verification

These runs overlap; do not add their totals together.

| Check | Observed result | Evidence |
|---|---|---|
| Broad backend regression | **107 passed**, 2 deprecation warnings | [backend-final.log](backend-final.log); predictions, registry, intervals/OOD, history, health, shared read models, preparation and synthetic hybrid integration |
| Final storm-intensity policy/registry/preparation checks | **37 passed**, 2 warnings | [backend-policy-final.log](backend-policy-final.log); after the final intensity gate and Python security updates |
| Final worker tick and clean-source allowlist regression | **18 passed**, 2 warnings | [backend-integration-final.log](backend-integration-final.log) |
| Initial clean core suite | **594 passed, 2 failed, 1 skipped** | [clean-core.log](clean-core.log); the two failures exposed missing copied firmware tool/ACL files, subsequently fixed |
| Corrected clean core tests | **70 passed**, 2 warnings | [clean-core-corrections.log](clean-core-corrections.log); includes both failed cases and final forecast/health/contract tests in the fresh environment |
| Core dependency separation | **Neither pandas nor scikit-learn installed** | [clean-core-dependencies.log](clean-core-dependencies.log), recorded before adding ML dependencies |
| Clean offline ML profile | **32 passed**, 2 warnings | [clean-ml-tests.log](clean-ml-tests.log) |
| Clean hybrid profile | **29 passed**, 2 warnings | [clean-hybrid-tests.log](clean-hybrid-tests.log); generated synthetic JSON estimator/rain series, no ignored data |
| Contract export in clean source copy | **Passed** | [clean-contracts.log](clean-contracts.log) |
| Final web unit/component/contract tests | **92 passed** | [web-unit-final.log](web-unit-final.log); includes dynamic first-hour persistence disclosure |
| Clean web lockfile install and tests | **Install succeeded; 92 checks passed** | [clean-web-install.log](clean-web-install.log), [clean-web-tests-final.log](clean-web-tests-final.log); includes the final disclosure regression |
| Clean web production build | **Passed**, Next.js 16.4.2 | [clean-web-build.log](clean-web-build.log); no copied `.env.local`, private model data or developer `node_modules` |
| Clean production-browser workflow | **Passed** using installed Chrome through pinned Playwright | [clean-web-browser.log](clean-web-browser.log); zero/interval, withdrawn history, outage, anonymous/resident staff-access guards |
| Flutter complete suite | **184 passed** | [flutter-tests.log](flutter-tests.log) |
| Final compact-card/forecast contracts | **26 passed** | [flutter-forecast-final.log](flutter-forecast-final.log) |
| Flutter analysis | **No issues found** | [flutter-analyze-final.log](flutter-analyze-final.log); after the final compact-card change |
| Python dependency audit | **No known vulnerabilities found** in resolved Windows profiles at audit time | [python-audit-final.log](python-audit-final.log), [python-audit.json](python-audit.json) |
| npm dependency audit | **0 reported vulnerabilities** at audit time | [npm-audit-final.json](npm-audit-final.json) |
| Workflow/configuration checks | YAML parsed; OpenAPI export check and `git diff --check` passed | [diff-check.log](diff-check.log); routine Windows line-ending warnings only |

The clean-source rehearsal created a new Python 3.12 environment and installed declared requirements under constraints. Core was checked before optional ML packages were added. The same freshly created environment was then extended sequentially for ML and hybrid; hosted CI installs each profile in a separate matrix job. A new lockfile-only npm install/build/browser run used the allowlisted source copy. No operational DB, journal, real credential file, ignored model dataset or existing environment was copied. New source was included because substantial earlier audit work is still untracked. This is not a claim that the current branch has been committed or that hosted CI ran.

The entire ten-minute core suite was not rerun after the two allowlist repairs. Both failed cases and the affected forecast paths passed in the corrected fresh copy; other initial core results are retained as observed. The PostgreSQL skip remains a local limitation. Hosted CI now supplies an explicit disposable loopback database for its restore job.

## Issues found and corrected during verification

- Calibration-fixture origin changes initially left inconsistent availability timestamps; the fixture now preserves causal timing.
- A newly imported account fixture needed its account-reset dependency in the new test module; test isolation was corrected.
- The new publisher/readiness integration test found that the forecast worker was absent from the heartbeat role allowlist. The role is now accepted, and an actual bounded publisher tick is exercised by the regression test.
- The first clean-source allowlist omitted `agapay-firmware/tools/render_station_config.py` and the broker `.acl` file. Both are now copied, both failed checks pass and a snapshot regression verifies required cross-project files while excluding machine state.
- The initial Playwright launch found no downloaded Chromium on this Windows machine. The local run used installed Chrome; CI explicitly installs its pinned Chromium. Neither result is a physical phone test.
- npm found advisories in Next.js, sharp and source-map-js. Compatible lockfile updates moved the build to Next.js 16.4.2 and cleared the npm audit. Python audit found certificate-bundle/OpenTelemetry issues; constraints now select `certifi==2026.10.19` and `opentelemetry-api==1.45.1`, and the final audit cleared both. Initial audit outputs are retained. No advisories were ignored or hidden.

## Remaining acceptance

**Field/domain:** real station/datum/calibration and source evidence, representative independently grouped training/calibration/test storms and negative events, reviewed season/intensity definitions, gap/target-label coverage, annotated physical onsets, accepted miss/false-alarm/lead-time tradeoffs and interval coverage under deployment conditions. Range-based OOD checks and offline feature-window reports do not establish concept-drift detection or calibrated coverage under changing conditions. The provisional policy cannot authorize release. Local-depth evaluation is not flood accuracy or an official evacuation decision.

**Infrastructure:** hosted Ubuntu CI, Linux-only uvloop resolution/audit, Docker image construction and the PostgreSQL service job have not executed locally. No container engine is installed here. The workflow supplies those checks, but a green hosted run still requires the complete intended source scope in a commit and then actual CI execution. Database-held model approval, current station binding and protected release-artifact provenance remain separate activation decisions.

**Device/product:** no field acquisition, physical notification receipt, phone background test or assistive-technology/user drill is claimed. The browser workflow and Flutter widgets validate software behavior only.
