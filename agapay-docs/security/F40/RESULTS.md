# F40 verification — 2026-10-23

The application controls and review package are implemented. Organizational/privacy/legal approval, managed PostgreSQL recovery and full service recovery acceptance remain pending. All exercises below used synthetic accounts, disposable databases and loopback fixtures. No live database was migrated or purged, no real backup was created, and no external message was sent.

## Observed local verification

| Check | Observed result | Scope and limitations |
| --- | --- | --- |
| Backend core regression | 612 passed, 1 skipped | Includes earlier privacy/recovery implementation. PostgreSQL integration was skipped because no test target was configured. Subsequent localized changes were covered by focused tests below. |
| Final privacy, recovery, SOS, identity and operations regressions | 76 passed | After account-lock/limiter ordering, access-review and privacy redaction corrections. Overlaps the core suite; counts must not be added as unique tests. |
| Final retention/recovery regression | 17 passed | Covers ambiguous-mail cleanup batching without deleting UNKNOWN/SENDING evidence; synthetic encrypted restore and quarantine. |
| Final privacy/recovery/identity regression | 53 passed | After the final mail-worker change. Covers stale account/contact/version suppression and serialization of an in-flight synthetic send with application erasure. Overlaps earlier suites. |
| Flutter full suite | 192 passed | Includes resident privacy request/export behavior and existing resident workflows. |
| Final Flutter focused suite | 14 passed | Privacy, SOS and accessibility regressions after final screen freshness changes. |
| Final Flutter privacy widget test | 1 passed | Explicit request, password clearing, receipt versus erasure and clearing the ephemeral record copy. |
| Flutter analysis | No issues found | After final test formatting/lint corrections. |
| Web checks | 93 passed | Includes authenticated privacy proxy, CSRF, bounded owner query forwarding and conflict passthrough. |
| Next production build and TypeScript | Passed | Local installed dependencies; no hosted CI or container execution claim. |
| Production browser workflow | Passed | Explicit privacy request receipt/password clearing; forecast unavailable/withdrawn states; anonymous/resident staff restrictions; keyboard skip/dialog/focus return; reduced motion and narrow large text. Loopback synthetic backend only. |
| Automated accessibility scans | 12 scans, zero violations | Six inspected routes in both themes, WCAG A/AA tags through 2.2. This is bounded automated evidence, not a blanket accessibility certification or resident comprehension test. |

The command logs are kept locally alongside this report; `*.log` is ignored by Git. The retained [axe results](web-axe-results.json), [narrow-screen image](web-narrow.png) and [synthetic drill report](synthetic-drill-report.json) contain synthetic evidence only.

## Recovery and retention drill

The tiny SQLite drill completed authenticated decryption, checksum/schema/row verification and quarantine in **0.437 seconds**. The original database was unchanged; rain ACK values were preserved. Two pending/retryable deliveries were suppressed and one processing delivery became UNKNOWN. Both notification and mail workers refused the quarantine fence, with **zero external send calls**. Separate tests preserve existing SENT/UNKNOWN history and reject a wrong key, altered ciphertext, truncated package and an existing restore target.

The exercise applied development retention to a synthetic old, closed SOS and recorded controlled audit evidence. Holds and active incidents remained protected in regression tests. Bounded batch tests verify that held incidents and ambiguous email records cannot starve eligible cleanup records. Case/access review tests reject stale versions and require explicit manual refresh. A controlled two-thread SQLite test verifies erasure waits for an account-bound identity send already holding the account lock; after erasure no queued identity message is sent. Real-engine PostgreSQL interleavings and actual provider behavior still need deployment validation.

**This does not measure production RPO/RTO.** Package capture age is not source-data freshness. Actual source cutoff/data loss remain explicitly unknown. The libpq PostgreSQL backup/restore path, real rain-journal deployment, encrypted storage ACLs, key escrow, capacity, restore duration and full API/broker/worker/provider recovery need an environment-specific exercise. Temporary synthetic fixtures and their encryption key were removed after the retained drill.

## Remaining acceptance gates

- The responsible organization must approve actual purposes, lawful handling, recipients, retention, residual pseudonymous histories, privacy audit-redaction exceptions, contact details and data-subject procedures. An evidence hash/attestation does not itself establish legal approval or deletion.
- Establish accountable incident/backup/database/push/Maps owners, real operator hours, fallback contacts, budgets and quotas. The example ownership record intentionally remains unapproved; production checks reject it.
- Measure managed backup/PITR and full service recovery against the provisional 15-minute RPO / four-hour RTO. Reconcile current privacy withdrawals and provider evidence before releasing a restored database. Never automatically replay historical notifications.
- Exercise external-copy/backup erasure and privacy request completion with real owners. Application erasure stays AWAITING_EXTERNAL until a reviewed completion decision; no automatic blanket backup deletion is claimed.
- Verify native device permissions, map disclosure and resident comprehension on physical phones. No new physical-device, provider receipt or emergency-response readiness claim is made.

No changes were staged, committed or pushed by this implementation. The pre-existing 48 staged paths were preserved.
