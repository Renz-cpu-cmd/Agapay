# F17–F19 verification — October 22, 2026

Local changes on `feature/day1-foundation`, HEAD `67f85e0`. Existing staged, unstaged and untracked work was preserved. [Contracts and rollout](README.md) describe the implemented policy and additive migration.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Full backend/ML regression before fixture corrections | 440 passed; three older assertions failed because they expected inactive ingestion or maintenance recovery | [backend-full.log](backend-full.log) |
| Alert/history and operations rerun after those corrections | 79 passed; three new citywide fixtures failed due to missing synthetic coordinates and unscoped transition lookup | [backend-final-targeted.log](backend-final-targeted.log) |
| Final operations, preference, concurrency and citywide acceptance | **16 passed**, including the corrected citywide fixtures and blank geographic-ID rejection | [backend-acceptance.log](backend-acceptance.log) |
| Unique backend/ML cases covered by the full regression plus focused reruns | **448 cases have passing results**; overlapping runs are not added together; this is not a claim of one final 448-pass full-suite run | Above logs and [backend-collection.log](backend-collection.log) |
| Complete web Node suite | **40 passed** | [web-tests.log](web-tests.log) |
| Web TypeScript | Passed; also checked during production build | [web-typecheck.log](web-typecheck.log) |
| Next.js production build with webpack | **Passed**, including TypeScript and route generation | [web-build-webpack.log](web-build-webpack.log) |
| Complete Flutter unit/widget suite | **119 passed** | [mobile-tests.log](mobile-tests.log) |
| Flutter static analysis | **No issues found** | [mobile-analyze.log](mobile-analyze.log) |
| Flutter web compilation | **Passed**, including Wasm dry run | [mobile-build.log](mobile-build.log) |
| Generated mobile release metadata | `build/web/version.json` contains version **0.1.0**, matching `pubspec.yaml`; no invented profile release/build number | Local generated build artifact |

Backend checks exercise anonymous/resident/officer administration rejection, audited admin metadata, stale and concurrent metadata/lifecycle/account preference writes, real device HTTP and mocked MQTT authentication, water/rain lifecycle consistency, retained unresolved incidents, maintenance escalation without external recipients, recovery hold, decommission revocation, and notification epoch suppression across reactivation. Explicit citywide dispatch cannot bypass lifecycle or account delivery-off. Turning delivery off removes all account registration tokens; turning it on cannot replay earlier registration revisions. Verified geographic IDs remain independent of subscriptions, unsupported locale updates fail, community language requests persist without translation, and the additive migration preserves existing records and is idempotent. Existing session-expiry/provider no-replay tests remain in the regression run.

Web handler tests verify displayed revision/identity-version submission, reason propagation, conflict blocking without automatic retry, officer read-only controls and verified-area writes without subscription/locale mutation. Existing measurement, interval, history, map, health and official-notice cases still pass.

Mobile tests verify restart/account isolation for local preferences, failed-load unknown state, stale write blocking until manual refresh, account-generation fencing, independent OS permission/service readings, timeout cleanup on disposal, actual package metadata and English-only supported locales. The new 320-pixel settings test saves a community language request while operational English remains unchanged and checks unavailable push capability/denied location permission. Existing account, notification, practice SOS, home unknown/error, exercise isolation, theme and narrow-layout cases remain included.

Earlier diagnostic logs overlap final checks and are not extra passes. Initial analysis identified seven missing-brace lints; these were fixed. Flutter fixtures now inject OS and secure-storage doubles rather than waiting on real platform channels. The default sandboxed Turbopack build failed creating a CSS worker process; the webpack production build passed. One existing Node module-type warning and the existing backend dependency deprecation warnings remain. Flutter's SDK localization support pins `intl` 0.20.2; `package_info_plus` is now an explicit dependency. No unrelated dependency upgrade was requested or performed.

No live migration/reset/reseed, station activation, service/broker restart, firmware upload, NVS erase, external notification, native mobile installation, deployment, commit or push was performed. Native Android/iOS permission changes, secure-storage persistence in an installed app and explicitly authorized real-provider delivery-off/on checks remain rollout acceptance work. Geographic registry activation and operator review of lifecycle policy also remain deployment work. F16's physical mounting/range/calibration acceptance remains pending; this change does not replace it.
