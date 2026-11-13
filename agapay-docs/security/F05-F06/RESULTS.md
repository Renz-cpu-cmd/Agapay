# F05/F06 verification — October 21, 2026

Local implementation on `feature/day1-foundation`, HEAD `67f85e0`. Existing staged, unstaged and untracked work was preserved. No commit or push was made.

| Check | Observed result | Authoritative evidence |
|---|---|---|
| Complete backend and ML suites, final source | **394 passed**, 23 dependency deprecation warnings, 275.25 seconds | [backend-tests-final.txt](backend-tests-final.txt) |
| Web regression suite | **21 passed** | [web-tests-final.txt](web-tests-final.txt) |
| Next.js production build with Webpack | SUCCESS, including TypeScript compilation and route generation | [web-build-final.txt](web-build-final.txt) |
| Complete mobile suite | **95 passed** | [mobile-tests-verified.txt](mobile-tests-verified.txt) |
| Flutter analysis | No issues found | [mobile-analyze-final.txt](mobile-analyze-final.txt) |
| Python compilation | PASS for changed backend modules | Local compileall run |
| Scoped `git diff --check` | PASS | No whitespace errors |

The backend command was run from `agapay-backend`:

```powershell
.\.venv-auth\Scripts\python.exe -m pytest tests app/ml/tests -q --basetemp .pytest_cache/f05-f06-final --tb=short
```

The web commands were run from `agapay-web`:

```powershell
node --test test/*.cjs test/*.mjs
npm run build -- --webpack
```

The mobile commands were run from `agapay-mobile`:

```powershell
C:/flutter/bin/flutter.bat analyze
C:/flutter/bin/flutter.bat test --reporter expanded
```

Backend acceptance tests cover firmware-string changes without source promotion, forbidden client provenance fields, persisted authenticated identity/credential/transport, registry-missing denial, legacy unverified rows, immutable commissioning versions and source review audit, cross-namespace MQTT rejection, exercise storage without operational side effects, duplicate/conflicting exercise payloads, and an additive migration that preserves existing samples without backfilling trust.

Freshness acceptance tests reproduce the one-hour retained EVACUATE depth followed by fresh invalid heartbeats. The value/date remain unchanged with both short and long chart windows; heartbeat remains online with age zero while depth age remains 3600, water is stale, rainfall interval freshness is independent, and the active hazard is unresolved. Hybrid initialization rejects stale, invalid, unverified, exercise and wrong-binding sources. The final test also verifies station metadata `last_ping` equals eligible receipt time, separately from measurement time.

Web tests verify re-aging retained values, source trust gates, model auto-setup rejection, and unknown measurement versus offline map markers. Mobile tests verify separate heartbeat/depth clocks, cached-age progression, firmware-independent source labels, and an actual home widget showing online heartbeat, a one-hour retained depth, and unresolved EVACUATE without a LIVE label. Existing mobile navigation, maps, narrow layouts, themes, auth, notifications and practice SOS tests pass.

Earlier logs are retained for traceability and overlap these totals. `backend-initial.txt` includes the old heartbeat-fixture expectation before its setup was updated. The first `mobile-tests.txt` includes an overly narrow new-test expectation: the correct age appeared twice, in both depth and trend panels. The corrected assertion checks both. Use the authoritative final logs above, and do not add overlapping suite totals.

## Activation boundary

The [rollout guide](README.md) describes the additive provenance migration, admin-reviewed source classification, credential/version replacement, isolated simulator namespaces and coordinated backend/web/mobile deployment. Existing identities are not automatically promoted to physical sources. Existing unprovenanced readings and historical episodes are retained.

No live database migration/reset/reseed, source reclassification, broker/service restart, credential installation, ESP32 upload/NVS erase, mobile installation, physical sensor/clock/calibration verification, external notification, commit or push was performed. Firmware code was unchanged for this pair; no new firmware build/physical delivery claim is made. Registry trust records authenticated administrative designation and does not constitute hardware attestation or calibrated flood validation.
