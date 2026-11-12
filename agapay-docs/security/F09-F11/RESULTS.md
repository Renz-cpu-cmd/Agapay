# F09–F11 verification — October 21, 2026

Local implementation on `feature/day1-foundation`, based at HEAD `67f85e0`. Existing staged, unstaged and untracked changes were preserved. F07/F08 regression coverage remains included in the final client suites.

| Check | Observed final result | Authoritative evidence |
|---|---|---|
| Complete backend and ML suites | **407 passed**, 23 dependency deprecation warnings, 285.88 seconds | [backend-tests-final.log](backend-tests-final.log) |
| Complete web Node suite | **30 passed** | [web-tests-final.log](web-tests-final.log) |
| Next.js production build, TypeScript and route generation | Passed | [web-build-final.log](web-build-final.log) |
| Complete Flutter suite | **105 passed** | [mobile-tests-final.log](mobile-tests-final.log) |
| Flutter analysis | No issues found | [mobile-analyze-final.log](mobile-analyze-final.log) |
| Scoped whitespace check | Passed | `git diff --check` on implementation, tests and documentation; Git emitted only existing LF/CRLF normalization notices |

Backend acceptance coverage includes:

- Borderline 59.9/60.1 cm noise produces one advisory episode, followed by sustained recovery below the exit band.
- A genuine/suspicious rapid critical rise escalates immediately; suspicious downward spikes cannot clear it.
- Invalid samples reset recovery, excessive gaps restart persistence, and every crossed hysteresis band is checked.
- Station-specific rules require administrator authorization, validation evidence and expected version; stale writes do not overwrite current policy.
- Manual reviews require explicit issuer jurisdiction and the current telemetry ID and cannot rewrite sensor history.
- Unsubscribed devices receive no ordinary station delivery; station and registered-area subscriptions receive only intended escalations.
- Profile locality does not enroll a device or change delivery targeting. Subscription revision checks suppress stale queued deliveries.
- Removing and re-adding an area binding cannot replay a prior captured delivery; stale mapping writes return 409.
- Citywide dispatch requires explicit authority permission, reason and bounded expiry, is audited, and is not replayed.
- App operators cannot issue Actual public-authority action notices. Issuer jurisdiction, corrections, cancellation references and superseded-write rejection are enforced separately from sensor episodes.
- The additive migration preserves existing records, and prototype issuer bootstrap makes no automatic subscriptions or geographic-exposure claims and grants no citywide permission by default.

Web coverage renders measurement states and official notice cards, verifies issuer/area/date/Test/cancellation metadata, rejects malformed issuer/lifecycle responses, checks local expiry progression, and confirms threshold guidance does not claim mandatory evacuation or community safety. Existing freshness, chart-gap, statistics/export coverage, model setup, map markers and rainfall tests remain green. One existing Node module-type warning remains in the rainfall test.

Mobile coverage verifies parsed issuer types, local expiry/cancellation, resident notice metadata, explicit station follow/unfollow without profile mutation, UNKNOWN startup/outage behavior, isolated exercises, retained measurements, account lifecycle, navigation, narrow layouts, themes, notifications and practice SOS.

Commands:

```powershell
# agapay-backend
.\.venv-auth\Scripts\python.exe -u -m pytest tests app/ml/tests -q --basetemp .pytest_cache/f09-f11-final --tb=short

# agapay-web
node --test test/*.cjs test/*.mjs
npm run build -- --webpack

# agapay-mobile
C:/flutter/bin/flutter.bat analyze
C:/flutter/bin/flutter.bat test --reporter expanded
```

Earlier logs are retained for traceability and overlap these final counts. Initial runs exposed a pending ORM recovery-row deletion, a synthetic firmware string that did not match the contract, an intentionally changed screen-title assertion, an off-screen profile tap after layout changes, and missing Dart braces. Those were corrected before the final runs. Do not add overlapping suite totals.

The prototype policy choices were authorized by the app owner for current application development. Test fixtures that exercise transactions/provider behavior use an explicitly instantaneous synthetic policy so those tests remain independent of the new stability acceptance tests. None of these tests validates the provisional 2 cm / three samples / ten seconds rules against a physical flood sensor or constitutes operator/government approval.

No live migration/reset/reseed, issuer/grant creation, resident enrollment, external push/message, broker/service restart, firmware operation, mobile installation, deployment, commit or push was performed. The [setup guide](README.md) provides the additive migration and internal app-issuer bootstrap commands. Provider acceptance, physical receipt, real-device connectivity, calibration, public authority and emergency readiness are separate verification levels.
