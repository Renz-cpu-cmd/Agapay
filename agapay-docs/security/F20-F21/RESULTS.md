# F20–F21 verification — October 22, 2026

Local implementation on `feature/day1-foundation`, HEAD `67f85e0`. The 48 previously staged paths and unrelated work were preserved. [Contracts and deployment](README.md) describe the additive rollout and remaining acceptance.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Final complete backend/ML regression | **486 passed**, 23 dependency warnings, 432.85 seconds | [backend-final-full.log](backend-final-full.log) |
| Web Node suite | **46 passed** | [web-tests.log](web-tests.log) |
| Web TypeScript | Passed | [web-typecheck.log](web-typecheck.log) |
| Next.js production webpack build | **Passed**, including `/recover` and TypeScript | [web-build.log](web-build.log) |
| Final complete Flutter unit/widget suite | **122 passed** | [mobile-tests-final.log](mobile-tests-final.log) |
| Isolated mobile identity acceptance | **3 passed**, including cached-session removal after expiry | [mobile-identity-final.log](mobile-identity-final.log) |
| Final Flutter analysis | **No issues found** | [mobile-analyze-final.log](mobile-analyze-final.log) |
| Flutter web build | **Passed**, including Wasm dry run; built before the final cached-session visibility guard, which is covered by the final widget/analyzer checks | [mobile-build.log](mobile-build.log) |
| Backlog regeneration | **40 unique findings**; F20/F21 now record implementation and pending deployment acceptance | [Backlog](../../audits/2026-10-21/prioritized-backlog.csv) |

Backend acceptance covers unavailable-provider behavior, generic recovery responses, encrypted mail, expiry/resend/account-version binding, one-use and concurrent recovery, invitation authority/expiry, required staff MFA, RFC TOTP vectors, replay rejection, durable failed-attempt limits, single-use backup codes, MFA retention through password recovery, session ownership/privacy and deliberate push revocation. Mutation tests cover required versions/reasons, sanitized refreshed values, two concurrent editors and immutable ORM audit records. Deployment tests cover explicit production configuration, secret-safe errors, audit redaction inside nested collections and evidence-bearing offline recovery. The additive migration preserves synthetic account IDs, bearer hashes and data while backfilling public session IDs; repeated application is tested.

Shared-budget tests use separate limiter instances over one disposable SQLite database. A synthetic office scenario completes 301 distinct account logins behind the same peer; only that quota-accounting test stubs the password verifier. Real password verification remains exercised by the account/MFA suites. This is evidence against the former broad office quota, not a throughput benchmark or PostgreSQL multi-host acceptance.

Web tests exercise the MFA challenge before navigation, HTTP-only cookie issuance only after factor verification, no bearer returned to browser JavaScript, origin checks on public recovery mutations, hidden unconfigured Google/recovery controls, the original profile version despite background changes and conflict handling without replay. Mobile tests exercise public recovery without installing a session, password/form clearing on conflict, explicit refresh and cached security information hidden after session expiry. Resident-only mobile access and English-only behavior remain intact.

The earlier full backend run had 478 passes and two fixture failures: the notification-device lexical-order fixture mocked all model UUIDs and exhausted its two values when sessions gained public IDs. It now mocks only the notification-device column default. Subsequent sandboxed runs stalled before tests inside Python's loopback socket-pair initialization; they were stopped, diagnosed with a timed thread dump and rerun with local runtime access. No product workaround was added for the sandbox. The first mobile cached-session test stalled in asynchronous logout cleanup; the final test exercises the actual expiry callback and passes. One new brace lint and an off-screen disabled-button test tap were corrected. Diagnostic runs overlap final verification and are not extra passes.

The final backend log includes a diagnostic 60-second thread snapshot during the existing rain-gauge continuous-coverage test; that test completed successfully and the complete run exited with 486 passes. The dependency set now explicitly pins the already installed `cryptography==50.0.1`; no unrelated package upgrade was performed. Existing backend dependency deprecations and Node module-type warnings remain in logs. Git whitespace checking passed, with existing Windows line-ending notices.

No live migration/reset/reseed, SMTP/push message, station activation, broker/service restart, firmware upload, native app installation, deployment, staging, commit or push was performed. SMTP credentials/sender and real mailbox receipt, deployed reverse-proxy identity, multiple real workers/hosts, database audit privileges, authenticator usability and installed-device persistence remain acceptance work. SMTP acceptance is separate from inbox receipt. F16 physical mounting/range/calibration acceptance remains pending.
