# Local verification — 2026-10-23

| Check | Observed result | Evidence |
|---|---|---|
| Flutter static analysis | No issues found | `flutter-analyze.log` |
| Complete Flutter unit/widget suite | 191 passed | `flutter-full-tests.log` |
| New mobile release/accessibility cases | Included in full suite: protected configuration rejection; elapsed-time coordinates; shared contrast ≥4.5:1; every resident tab at 320px/200% text/reduced motion in both themes; timestamp data including valid zero/unknown; representative effective Android tap-target guideline | `test/release_accessibility_test.dart` and full-suite log |
| Public release policy / synthetic archives | 2 tests passed; no real key used | `release-policy-tests.log` |
| Native production signing rejection | Expected Gradle failure: protected signing environment incomplete, no debug fallback | `android-release-negative.log` |
| Native production dependency graph | Dry run successful; protected validation task is included before packaging | `android-release-task-graph.log` |
| Development Android compilation | Final development APK compiled successfully (`assembleDevelopmentDebug`, 83.6 seconds); no installation | `android-development-build.log` |
| Web unit/contract suite | 92 passed | `web-tests.log` |
| Next production build | Compiled, TypeScript and static generation succeeded | `web-build.log` |
| Production Chromium workflow | Passed: forecast zero/interval, withdrawn history, outage, anonymous/resident access boundary, keyboard skip link, dialog focus containment/Escape/trigger return, narrow enlarged layout and reduced-motion preference | `web-browser.log` |
| Axe WCAG-tagged checks | 12 scans, zero violations in tested synthetic states: published forecast plus dashboard, alerts, SOS, System Health and settings, each in light/dark | `web-axe-results.json` |
| Responsive visual inspection | Narrow 390px browser page with enlarged root text reviewed; scrolling content and compact navigation remain visible | `web-narrow.png` |
| CI configuration | YAML parsed; mobile release policy tests, development APK and negative signing gate added; browser workflow invokes accessibility scans | `.github/workflows/ci.yml`; hosted run not performed |

Browser traffic uses an isolated loopback HTTP fixture and production Next server. Unconfigured optional fixture dependencies deliberately return 503 and the pages must render their degraded state, not a page error. These checks do not establish accessibility of every populated table, modal, map overlay or every actual provider response. The browser workflow asserts that no unexpected client exceptions occurred. No resident/staff account or live service was mutated.

The new enlarged-text tests initially exposed overflow in hazard/account rows, map metadata, bottom navigation, the SOS control and alert filtering/pagination. Those layouts were corrected and the complete suite subsequently passed. Earlier focused failure/debug logs are historical diagnostics, not the final result. A page-error button's contrast was corrected; its `retry` callback matches the installed Next.js documentation and existing contract test.

## Findings remain conditional

F38 software controls are implemented, but a protected staging/production artifact has **not** been built with an intended organizational upload key. No signer was invented. Store provenance, actual cloud key restrictions/hosted Maps integration, crash symbolization, physical startup/size/battery measurements, upgrade/background/permissions and controlled phone push remain pending. Development APK size is not a production size benchmark. iOS native schemes, signing, entitlements, APNs and physical behavior remain separately unverified.

F39 has scoped automated evidence. Full rendered contrast/focus coverage, 400% web zoom, all error/modal states, TalkBack/VoiceOver/switch access and representative resident/officer comprehension trials remain pending under [ACCESSIBILITY-MATRIX.md](ACCESSIBILITY-MATRIX.md). Zero axe violations is not a WCAG compliance certificate.

No code was staged, committed or pushed. Existing staged changes were preserved. No production database, firmware, broker credential or notification provider was changed by this task.
