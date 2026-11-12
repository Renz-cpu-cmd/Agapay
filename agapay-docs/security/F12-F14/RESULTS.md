# F12–F14 verification — October 22, 2026

Local implementation on `feature/day1-foundation`, based at HEAD `67f85e0`. Existing staged, unstaged and untracked work was preserved. See [contracts and rollout](README.md).

| Check | Observed result | Evidence |
|---|---|---|
| Complete backend and ML suites | **424 passed**, 23 dependency deprecation warnings, 303.45 seconds | [backend-tests.log](backend-tests.log) |
| Complete web Node suite | **35 passed** | [web-tests.log](web-tests.log) |
| Next.js production build, TypeScript and route generation | Passed | [web-build.log](web-build.log) |
| Complete Flutter suite | **107 passed** | [mobile-tests.log](mobile-tests.log) |
| Flutter analysis after null-assertion cleanup | No issues found | [mobile-analyze.log](mobile-analyze.log) |
| Targeted Flutter contract/home/rate tests | **13 passed** | [mobile-targeted.log](mobile-targeted.log) |
| Scoped tracked and new-file whitespace checks | Passed | `git diff --check` plus explicit new-file checks; existing LF/CRLF normalization notice only |

Backend regression coverage includes independent rain staleness while water remains fresh, valid zero tips, maintenance administration, read-only missing-journal behavior, HTTP not proving MQTT health, local subscriber disconnection, provisional rate boundaries, equivalent rates at different cadences, outlier resistance, invalid observations, gaps, reboot boundaries, stale/short windows and review exclusion.

Report tests exercise asynchronous station times, explicit null buckets, raw extrema versus bucket means, synchronized late history, invalid/unverified exclusions, exact persisted event boundaries, staff authorization, timezone-aware inputs, date/station/point/sample budgets and failure without partial reports. An isolated database test verifies that the additive measured-time index preserves records and is idempotent.

Web tests cover independent channel aging, API failure, maintenance/outage distinctions, zero tips, broker evidence, timestamp series, CSV scope/event/timezone/units/source/quality/coverage, spreadsheet formula neutralization and no export from the short live monitoring window. One existing Node module-type warning remains in rainfall tests.

Mobile widget tests cover unknown trend when rate coverage is insufficient and presentation of the backend cm/min rate and slope range. The complete suite also includes earlier operational unknown-state, exercise isolation, governance and account regressions.

Commands used:

```powershell
# agapay-backend
.\.venv-auth\Scripts\python.exe -u -m pytest tests app/ml/tests -q --basetemp .pytest_cache/f12-f14 --tb=short

# agapay-web
node --test test/*.cjs test/*.mjs
npx tsc --noEmit
npm run build -- --webpack

# agapay-mobile
C:/flutter/bin/flutter.bat test
C:/flutter/bin/flutter.bat analyze
```

Earlier targeted logs overlap the complete suite and must not be added to its totals. The rate thresholds and channel timeouts are application defaults, not physically approved flood criteria. Software fixtures do not prove sensor mechanics, calibration, broker-wide operation, emergency readiness or native-device behavior.

Static analysis initially found a redundant Dart null assertion; it was removed and analysis passed. The complete mobile suite passed before this behavior-preserving cleanup. CSV quoting was additionally hardened against formula-like text, then the web suite and production build were rerun.

No live migration/reset/reseed, broker/service restart, authority grant, external notification, firmware operation, mobile installation, deployment, commit or push was performed.
