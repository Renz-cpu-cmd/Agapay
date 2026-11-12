# F07/F08 verification — October 21, 2026

| Check | Observed result | Evidence |
|---|---|---|
| Complete web regression suite | 25 passed | [web-tests.log](web-tests.log) |
| Next.js production build, including TypeScript and route generation | Passed | [web-build.log](web-build.log) |
| Complete Flutter suite | 102 passed | [mobile-tests.log](mobile-tests.log) |
| Flutter static analysis | No issues found | [mobile-analyze.log](mobile-analyze.log) |
| Targeted mobile acceptance tests | 11 passed, overlapping the full suite | [mobile-targeted.log](mobile-targeted.log) |
| Scoped whitespace check | Passed | `git diff --check` on changed implementation, tests and documentation |

Web acceptance tests exercise missing data, valid zero, stale nonzero, invalid first samples, invalid historical points and retained valid values following invalid heartbeats. They verify independent rain quality, true timestamps, exclusion from current extrema/mean, historical coverage, empty-window UNKNOWN tiers, and shared report/export rows. Actual React components are rendered for dashboard, station cards, station detail, analytics, map footer, system health and forecast measured depth. Charts/maps/network hooks are stubbed in these component tests; production compilation covers their real imports. One existing Node module-type warning remains in the rainfall test.

Mobile acceptance tests sign in using mocked APIs and cover a new account with no stations, an empty station, an invalid station, delayed monitoring response, failed API, valid zero depth/rainfall, and deliberately entering/changing/leaving exercise mode. They assert no operational example warning/depth/rainfall/rate, unavailable gauge semantics, account/station context, and unchanged operational alert/snapshot state during exercises. Existing tests also verify one-hour retained depth with online invalid heartbeats and unresolved hazard, navigation, narrow layouts, themes, auth, notifications and practice SOS.

Commands from `agapay-web`:

```powershell
node --test test/*.cjs test/*.mjs
npm run build -- --webpack
```

Commands from `agapay-mobile`:

```powershell
C:/flutter/bin/flutter.bat analyze
C:/flutter/bin/flutter.bat test --reporter expanded
```

The backend was unchanged for this pair, so its prior suite was not rerun. Existing staged, unstaged and untracked work was preserved. No live migration/reset/reseed, broker restart, credential/source changes, external notification, firmware upload, mobile installation, deployment, commit or push was performed.
