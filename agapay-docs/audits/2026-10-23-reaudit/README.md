# AGAPAY acceptance re-audit — 23 October 2026

**Verdict: substantial implementation and local verification; not perfectly complete and not accepted for production emergency use.** Passing local tests does not close the remaining physical, database-engine, deployment, scientific, organizational or human acceptance gates.

This review compared the 40 original backlog entries and their feature closeout evidence, inspected critical ingestion/ordering/alert/SOS/startup/release/client presentation paths, reproduced an additional map inconsistency and reran the combined local regressions. It is a bounded source and acceptance review, not proof that every possible defect has been excluded. The product source was not changed during this review.

## What remains in the source and test coverage

### R1 — Web supplies a demo coordinate when registry coordinates are unknown

Priority: P2. Evidence: reproduced through the actual presentation function. Related findings: F24, F26, F39.

`agapay-web/src/context/MonitoringContext.tsx:33` supplies a bundled station to `displayStation`. At `agapay-web/src/lib/station-display.ts:36`, missing API coordinates fall back to that bundled station's planned location. A synthetic API record for `STATION_001` with null latitude/longitude therefore produces latitude `15.98165`, longitude `120.560573`, status `planned`. Mobile uses only its API coordinates and leaves the station in the list, so the platforms disagree. The planned label limits the claim but does not make the point an actual registry location.

Evidence: [map-coordinate-probe.json](map-coordinate-probe.json). The probe called the real TypeScript transformation with synthetic data; it did not call Google Maps or any live service.

Required correction: retain null operational coordinates, keep planned demonstration locations inside an explicit exercise context, and expose coordinate verification/source from the registry rather than assigning every non-null API point `planned`. Add a cross-client case using an ID that also exists in bundled demonstration data; current synthetic IDs do not exercise this fallback.

### R2 — The PostgreSQL lane does not test the required concurrency behavior

Priority: P1 acceptance gap. Evidence: source-confirmed. Related findings: F03, F21, F22, F29, F37, F40.

`.github/workflows/ci.yml:64` configures a PostgreSQL service, but its test command at line 89 runs only `tests/test_postgres_restore.py`. That test inserts/restores one synthetic station and checks schema/current-version and repeat-restore rejection. It does not exercise concurrent water arrival, duplicate/reboot ordering, SOS location versus resolution, stale administrative writes, outbox claiming or privacy/identity races on PostgreSQL. The broad backend fixtures use a disposable SQLite database. The presence of a PostgreSQL job cannot close those real-engine criteria.

Required evidence: a disposable PostgreSQL matrix that forces the interleavings and checks winning values, explicit losing-write conflicts, preserved incidents/outbox/audits and no replay. Restore fixtures should include linked accounts/sessions, station/telemetry/provenance, alerts/transitions, SOS/response histories, ambiguous deliveries and migration metadata. Execute that lane on a complete release candidate and retain actual results; do not infer them from SQLite behavior.

### R3 — The complete implementation has not been delivered as a verified release revision

Priority: P1 integration/release gate. Related finding: F37.

The working tree contains essential untracked modules, including forecast/privacy routers, the migration implementation, the forecast workspace and the shared mobile vocabulary. Local sanitized-source rehearsals can include these files, but a Git checkout/hosted run only receives the eventual committed scope. No complete release revision or hosted run for this combined implementation was established by this review. This is consistent with preserving the user's existing staging and keeping commits/pushes pending; it must not be described as already integrated or deployed.

Required evidence: review the intended source scope, preserve it in an exact revision when authorized, and verify fresh Linux dependency profiles, contract checks, containers, firmware, PostgreSQL and client builds from that revision. The existing 48 staged paths were not altered by this review.

### R4 — Sensor operational eligibility does not enforce configuration review status

Priority: P1 before operational rollout. Evidence: reproduced in the shared authentication/ingestion services; production exposure was not tested. Related findings: F09, F16, F17, F27.

`app/device_config.py:44` permits `prototype`, `bench_reviewed` and `field_reviewed`; saving any status copies its thresholds into the station. `app/services/telemetry_service.py:63` checks applied-configuration hash agreement but does not use the review status when deciding current eligibility. In contrast, forecast binding/publication explicitly requires `field_reviewed`.

In an isolated in-memory database, a synthetic commissioned physical-source identity with valid synthetic credentials and a matching **prototype** configuration produced `eligible_for_current=true`, an EVACUATE episode and one durable notification event. There were zero delivery rows and zero external sends. Development behavior is expected to allow prototype testing; the gap is the absence of an equivalent per-station production review-status gate in the shared sensor decision/delivery path.

Evidence: [configuration-review-probe.json](configuration-review-probe.json), reproduced by [probe_configuration_review.py](probe_configuration_review.py). This is not a full production startup, exposed-network or phone-delivery test.

Required correction/policy: define and enforce reviewed production eligibility for operational publication and external delivery, or a deliberate bounded/audited override. Keep raw observations, unresolved incidents and independent local fail-safe alarms available; do not implement this by silently discarding a critical measurement. Add production-profile cases for prototype, bench and field configurations with matching hashes.

### R5 — The complete backend suite is not green

Priority: P2 test reliability/integration blocker. Related findings: F05, F37 and the staff workspace.

The fresh combined backend/ML run ended with **698 passed, 1 failed, 1 skipped**. The failure is `tests/test_staff_workspaces.py:40`, `test_provenance_cannot_be_relabelled`. The same staff module passes all seven tests in isolation.

The failure is consistent with a fixture/pagination assumption, not evidence that physical-source authorization was bypassed: the assertion expects its newly unverified advisory to occur in the first default 20-row page, while previous tests leave older unverified episodes. The queue correctly orders severity/age before pagination. A separate synthetic 21-episode probe places the advisory on page two, not page one, while preserving it in the unverified scope.

Evidence: `backend-full.log`, `staff-isolated.log`, [queue-pagination-probe.json](queue-pagination-probe.json) and [probe_queue_pagination.py](probe_queue_pagination.py).

Required correction: isolate the test's episode population or follow the endpoint's pagination when asserting membership, preserving the operational/unverified authorization assertions. Rerun the complete suite afterward. The failing full-run result was not replaced by the passing focused count; no product or test-suite patch was made in this review.

## Major acceptance gates still open

| Gate | Current evidence | What closes it |
|---|---|---|
| F16 physical geometry — P0 | Host/bench acquisition crosses tiers under synthetic geometry; physical acceptance record remains empty; R4 review-status gate is absent | Measured installed geometry/datum/range margin, threshold crossings, blind-zone/fault/offline behavior, configuration identity, rain-volume calibration and operator review |
| F09/F10/F11/F17 domain policy | Configurable provisional policy, issuer and lifecycle safeguards | Actual station rules, verified geographic scope, legitimate issuer/authority and accepted lifecycle/notification behavior |
| F20/F27/F29/F30 production infrastructure | Local auth/proxy/TLS/ACL/migration/readiness controls; isolated broker and copy rehearsals | Intended network/proxy/CA/revocation, real SMTP/MFA recovery, supervised workers/receiver, managed PostgreSQL and full recovery/fault drill |
| F23/F24 operational response | Practice SOS workflow and managed resource schema; no real dispatch implied | Named duty ownership/hours/fallback, maintained verified shelter/road inventory and a witnessed handoff/escalation drill |
| F25/F28/F33/F38 installed-device delivery | Host journal tests, widget cache/outbox tests, provider mocks and release guards | Protected signed build; phone permissions/upgrade/offline/background/key-loss/push receipt stages; actual ESP32 outage/brownout/endurance/network evidence; separate iOS acceptance |
| F34/F36 scientific qualification | Candidate preparation, baselines, registry/evaluation/uncertainty/OOD gates with synthetic evidence | Reviewed paired field data, calibrated target/datum, independent withheld storms/negative events, baseline gains, interval coverage and accepted miss/false-alarm/lead-time tradeoffs |
| F35 published operational product | Same-ID web/mobile publication contracts and expiry/revocation guards | Genuinely qualified model and commissioned station binding, approved artifact and supervised publication in the target environment |
| F39 human usability | Bounded automated semantics/contrast/layout/browser evidence; participant count zero | Actual NVDA/TalkBack/VoiceOver sessions and measured resident/officer task comprehension, including outage/uncertain-send/concurrent-action cases |
| F40 ownership/privacy/recovery | Unapproved example governance record, application controls and tiny synthetic encrypted restore | Real responsible owners/policy decisions, approved handling and access/retention exercises, managed recovery against chosen RPO/RTO and safe reactivation |

These gates describe missing acceptance evidence, not a claim that the original code defects are all unchanged. Every original finding has implementation work recorded. Several software criteria have passing local tests; deployment and field closure remain separate. No arbitrary completion percentage is assigned.

## Finding-by-finding record

[acceptance-matrix.csv](acceptance-matrix.csv) retains all **40 unique findings**, their priority and recorded implementation state, a specific remaining condition and the corresponding feature evidence. The original backlog was not overwritten or marked closed.

## Verification

Fresh command results and the retained same-source browser evidence are recorded in [verification.md](verification.md). Test totals from earlier feature runs overlap and must not be added. A skipped PostgreSQL test is missing acceptance evidence, not a pass.

Recommended sequence: correct R4 eligibility policy and R1 map behavior; fix R5 isolation/pagination and obtain a green complete regression; implement/execute the PostgreSQL acceptance matrix; establish the complete clean release candidate and deployment; then collect the physical/device, scientific, operational and human evidence required for the enabled feature profile. Keep forecasts unavailable and response workflows in practice where their activation criteria remain unmet.
