# F24–F25 verification results

Observed October 22, 2026 in the existing Windows workspace. These are software checks using synthetic resources, isolated databases and mocked platform/provider adapters. No real shelter, closure, emergency contact, route, dispatch or device encryption claim follows from them.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Backend complete regression suite | **515 passed**, 23 dependency deprecation warnings | [backend-full.log](backend-full.log) |
| Registry/receipt focused suite after no-store integration | **12 passed**, 2 dependency deprecation warnings | [backend-focused.log](backend-focused.log) |
| Web Node tests, CJS and MJS | **54 passed** | [web-tests.log](web-tests.log) |
| Web TypeScript check | Passed, no diagnostics | [web-typecheck.log](web-typecheck.log) |
| Next.js production webpack build | Passed; includes protected `/response-resources` | [web-build.log](web-build.log) |
| Flutter static analysis | **No issues found** | [flutter-analyze.log](flutter-analyze.log) |
| Flutter complete regression suite | **147 passed** | [mobile-full.log](mobile-full.log) |
| Embedded map JavaScript test | **1 passed**; themes, road and route overlays/cleanup, route failure, key failure, null duration and provider warnings | [map-asset-test.log](map-asset-test.log) |
| Flutter release web build | Passed; compiled `lib/main.dart` and produced `build/web` | [mobile-web-build.log](mobile-web-build.log) |
| Derived audit backlog | 40 original findings retained; F24/F25 marked implemented with live/native acceptance pending | [prioritized-backlog.csv](../../audits/2026-10-21/prioritized-backlog.csv) |

The 515-test run included all 12 new backend cases. The subsequent focused run verifies the last no-store middleware addition without resetting or touching the live database. Earlier development logs are retained for diagnosis and are superseded by the final suite logs above. The secure-storage interface is injected in existing unit/widget fixtures; automated adapter tests do not inspect real native ciphertext.

## Behaviors exercised

- Anonymous/resident/ungranted staff cannot maintain resources. Actual resources require scoped public-authority/geographic grants; app-operator exercises remain invisible to residents. No inventory defaults are seeded.
- Unpublished drafts are hidden; saving a published revision invalidates verification. Separate verification, expiry, withdrawal, capacity unknown/full behavior and original observation times are enforced. Full does not become available merely because the capacity report aged.
- Stale edits/verification return explicit refresh-required conflicts. Concurrent SQLite edits produce one winner and one conflict with exactly one accepted revision. Revision history is application append-only and records actor/reason/version without credentials. Additive migration is idempotent and seeds zero records. Exact area membership and bounded pagination are checked.
- The read-only SOS receipt lookup never creates a request, respects owner privacy, distinguishes a payload conflict and still matches the original submission after a newer GPS fix.
- Cold offline AuthApi/controller reconstruction restores a token-bound resident, original station timestamps and reader offsets; cached measurements stay unconfirmed and cannot become LIVE. Cache expiry/clock rollback, account/server isolation, size eviction, oversized responses, storage failure, late account results and JSON/non-JSON 401/403 denial behavior are tested.
- A failed monitoring feed retains its own last-known labels without revoking a verified session or blocking a deliberately submitted SOS to an available service. Cached-identity cold launch remains read-only until explicit verification.
- An offline SOS stays queued on device through restart. Reconnection/session verification never sends it automatically. Explicit send uses the original payload/reference without outbox metadata. Positive receipt remains durable through restart. History UUID alone cannot confirm receipt. Unknown and conflicting sends are not discarded/overwritten; rejection of a later retry cannot erase an earlier uncertain attempt. Discard and send cannot race through draft deletion.
- Widget rendering retains verified text/contacts when WebView is unsupported, GPS is denied or routing fails. Unverified instructions are withheld; expired reviewed instructions are explicitly historical. A 320-pixel layout preserves offline/outbox labels. Existing navigation/theme/account/push fixtures now assert the new registry and last-known behavior.
- Staff UI tests exercise version snapshots, dirty-form verification gating, conflict latching/manual refresh, UTC editing, decimal coordinates and locally elapsed expiry. BFF tests exercise namespaces, filters, pagination, origin/method/staff controls.

## Acceptance still requiring a deployed environment

- Real issuer/area authorization evidence; reviewed shelter activation, capacity, accessibility, contacts/hours, road sources and preparedness content. The live inventory intentionally remains empty until those records are maintained.
- PostgreSQL resource race verification, schema rollout and audit database privileges against the actual deployment configuration. No live migration was run.
- Android/iOS installed-device encrypted persistence and key-loss/backup/upgrade behavior, airplane-mode cold launch, interrupted send/restart/reconnect, GPS permission denial and real map quota/provider failure. The web build is compilation evidence only.
- Real contact reachability, road-passability evidence, authority-approved operating procedures and any operational dispatch activation. All SOS submissions remain practice; generic computed routes never certify flood safety.

No service was deployed, no external message was sent, and nothing was committed or pushed. The existing 48 staged paths, branch `feature/day1-foundation` and HEAD `67f85e0` were preserved.
