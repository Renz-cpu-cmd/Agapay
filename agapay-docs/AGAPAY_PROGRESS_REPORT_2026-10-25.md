# AGAPAY progress and handoff report
## Continuation through 25 October 2026 — Asia/Manila

### 1. Where this report starts

This continues the AGAPAY material previously prepared for ChatGPT:

- **13 October 2026:** `agapay-docs/LATEST_ML_DASHBOARD_REPORT_2026-10-13.md`, the last standalone “latest changes” report found. The earlier “Build AGAPAY ML data pipeline” conversation explicitly links that file as the report created for ChatGPT.
- **21 October 2026:** the full end-to-end audit, `agapay-docs/audits/2026-10-21/AGAPAY-END-TO-END-AUDIT.md`. The ChatGPT conversation titled **“AGAPAY Reliability Priorities”** contains that audit attachment and the subsequent five-work-package plan: secure ingestion, trustworthy measurements, consistent clients, physical alarm validation, and reproducible release preparation.
- **23 October 2026:** the acceptance re-audit, `agapay-docs/audits/2026-10-23-reaudit/README.md`, which checks what the implementation actually proves and identifies remaining gaps.

The main period covered here is **21–25 October**, with a brief bridge from the October 13 report. This document is intended to stand alone when uploaded to ChatGPT. Repository paths are evidence pointers; ChatGPT will not automatically have those files unless they are also attached.

**Overall status:** substantial local engineering work has been implemented across all 40 original findings. AGAPAY remains a development prototype with unresolved field, scientific, operational, database-engine and release acceptance gates. It is not established as a production emergency-response or validated flood-warning service. No completion percentage or “perfectly finished” claim is justified.

### 2. Important changes to the previous report

Several statements in the October 13 report are now superseded:

| Earlier state | Current direction / implementation |
|---|---|
| Separate ML Configuration and ML Evaluation sidebar links | One ML Configuration sidebar entry; Configuration, Evaluation and Published forecasts are grouped inside the workspace. |
| Browser-configured hybrid projection presented alongside monitoring | Operational clients read a persisted, versioned forecast product. Private rainfall/basin experiments remain separate staff tools. |
| Mobile technical/staff access appeared during an intermediate iteration | Mobile is explicitly **resident-only**. Staff administration and ML configuration/evaluation remain on the web. |
| Arrival/receipt-based or ambiguous measurement presentation | Measured time, receipt time, heartbeat time, last-valid time, quality and channel freshness have separate contracts. |
| Open/development ingestion and implicit source trust | Provisioned station identities, per-station credentials, source registry, authenticated HTTP/MQTT and independent transport controls. |
| Dashboard screenshots could show historical experimental context | The current isolated preview reports unknown readings and unavailable forecasts honestly; it does not fabricate live measurements. |
| Visual redesign could replace the original application composition | The owner's original mobile and web Figma designs are the visual baseline. Preserve their layout, charts, dial and map while keeping the corrected contracts. |

On October 20–21, the ML workspaces and mobile trend composition were also improved. The final mobile scope correction removed staff sign-in and mobile technical pages.

### 3. Engineering work against the original findings

“Implemented” below means local source and documented software checks exist. It does **not** mean the corresponding end-to-end acceptance criteria are all closed. The detailed acceptance matrix retains all 40 unique findings.

| Findings | Work implemented locally | Remaining boundary |
|---|---|---|
| **F01–F02: ingestion and provisioning** | Station-bound credentials for HTTP/MQTT; expiry/revocation; shared payload/rate budgets; administrator-only audited provisioning/commissioning; version conflicts; rejected anonymous/cross-station traffic cannot create operational rows. Staff login tokens are not device credentials. | Real station commissioning, credential deployment, intended broker ACLs and installed-network acceptance. |
| **F03–F04: ordering and retained MQTT** | Boot/session/configuration identity, sequence and uptime high-water rules, measured/received timestamps, exact-retry versus conflicting-payload distinction, serialized current-state updates, and rejection of retained operational water/rain ingress. Late history cannot roll current measurements or alerts backward. | Actual PostgreSQL interleavings and physical reconnect, reboot and clock behavior. |
| **F05–F06: provenance and freshness** | Trusted source designation comes from the authenticated registry, not firmware text. Operational and exercise streams are separate. Heartbeat, latest sample and last valid depth have independent timestamps/quality/freshness; last-valid lookup does not depend on chart length. | Registry review is not hardware attestation or field calibration. Stolen valid credentials remain a provisioning/revocation risk. |
| **F07–F08: honest missing data** | Nullable web measurements, explicit unavailable reasons, valid zero retained as zero, coverage-aware aggregates and gaps. Resident home starts unknown; feed failure cannot invent warning values or auto-enter an exercise. | Installed-client outage/cold-start acceptance remains separate from widget evidence. |
| **F09–F11: alert policy, authority and targeting** | Configurable hysteresis/recovery and plausibility review; immediate upward escalation retained. Sensor episodes, forecasts, app advisories and public-authority notices have distinct models. Notice correction/cancellation and issuer/area/lifecycle metadata exist. Push uses explicit station/area subscriptions with audited citywide controls. | Provisional engineering policy needs physical/domain approval; actual public authority and verified affected areas have not been invented or activated. |
| **F12–F14: health, rate and reports** | Independent water/rain/heartbeat/broker/configuration health; measured-time robust rate in cm/min with coverage/dispersion; timestamp-aligned history; bounded database report ranges, filters, quality, coverage and CSV scope. Missing intervals remain gaps. | Deployed channel interruption tests, domain interpretation of rates, and representative history/load testing. |
| **F15–F16: rainfall and installation geometry** | Explicit rainfall intervals/configuration hashes; durable rain products are authoritative; per-station coefficients; reviewed installation record/export; device-applied hash and mismatch visibility; geometry validation and fault rules. | Physical mounting/datum/range margin, every approved tier, blind-zone policy and controlled-volume rain calibration remain open. |
| **F17–F19: lifecycle and resident settings** | Audited/versioned station lifecycle and maintenance policy; persistent real preferences; delivery choice separated from OS permission and service availability; selected-area context and build metadata. English operational resources are used; Filipino translation is visibly unavailable. | Actual operator lifecycle policy, permission/device acceptance and reviewed future translations. |
| **F20–F21: accounts and administrative concurrency** | Single-use expiring recovery/verification/invitation flows, configurable SMTP queue, staff MFA, session/device management, shared abuse controls/trusted-proxy boundaries, atomic expected versions, reasons and redacted audit trails. Conflicts require explicit refresh/manual review. | Real SMTP/sender/public origin, staff recovery/MFA operations, proxy deployment and multi-worker/real-engine acceptance. |
| **F22–F23: SOS ordering and response workflow** | Conditional location updates cover owner/version/lifecycle/capture time; exact duplicate fixes remain idempotent. Configurable response drills add coordinator/assignment/contact/acceptance/departure/arrival/closure evidence and timed escalation. Resident status comes from recorded actions. | No real LGU roster, duty coverage, dispatch service or response SLA is established. Acknowledgement means review, not that a responder was sent. |
| **F24–F25: resources and offline behavior** | Managed shelter/road/preparedness/contact registry with issuer, area, verification/expiry and capacity/access information; list fallback; hardcoded shelter removed. Explicit encrypted reader cache and durable SOS outbox preserve original times/references and queued/received/unknown distinctions. | Maintained verified inventory, installed-device encryption/offline/restart/upgrade tests, and real response procedures. Generic routes are not certified flood-safe. |
| **F26–F27: shared mobile state and transport** | Home/map/detail/forecast share monitoring state and generation/freshness guards. Production TLS/HTTPS, credential/ACL templates, release transport gates and web CSP/security headers exist. | Intended deployment certificates, broker/proxy configuration, actual ESP32 TLS/revocation behavior and production provider acceptance. |
| **F28–F29: depth recovery and schema lifecycle** | Bounded durable depth journal/backfill with original identity/time and post-commit application ACKs; explicit gap/eviction diagnostics; ordered preserving migrations and schema readiness. Serving no longer automatically runs create_all or seeds demo stations. | Physical flash/power/outage/brownout acceptance, reviewed filesystem provisioning, PostgreSQL migration/restore and production deployment. |
| **F30–F31: workflow health and bounded shared reads** | Separate liveness/readiness/diagnostics; worker/queue/broker/rain/model checks; correlation/metrics/operator faults/runbook; shared bounded read products and inference caching; visible/background lifecycle, coalescing and stale-generation rejection. | Intended station/viewer capacity, p95/p99 workflow latency, phone network/battery measurements, supervised services and live fault drills. SSE was not added merely as a checkbox. |
| **F32–F33: rain growth and delivery evidence** | Incremental hourly/lifetime/session rain products, indexes, one-time initialization, explicit archival/integrity checks; worker supervision support, queue-age/ambiguity diagnostics, audited reconciliation and app receive/open/acknowledge evidence stages. No blind replay of UNKNOWN/PROCESSING. | Actual sustained journal workload, archive/restore operations, supervised production workers and controlled physical phone receipt tests. |
| **F34–F35: model preparation and published forecast** | Causal site/datum-bound candidate preparation, baselines/model cards, approval/binding registry and immutable forecast IDs shared by web/mobile. Evaluation resolves the deployed registry/configured experimental artifact. Typed OpenAPI/TypeScript/Dart publication contracts and shared cases exist. | No real operational water-depth model has been trained/qualified. Real paired field targets and independent approval are required. |
| **F36–F37: decision uncertainty and reproducibility** | Event/horizon/subgroup/peak/threshold evaluation; separated calibration/test events, event-based intervals and bootstrap estimates; OOD/drift/fallback/rollback gates; appropriate display precision. Core/ML/hybrid CI profiles, synthetic integration fixtures, artifact integrity/licensing gates, contract/browser/security checks and clean-source rehearsals. | Field uncertainty/false-alarm/miss/lead-time qualification; complete committed release scope; hosted Linux/container/real-engine evidence. |
| **F38–F39: release and accessibility** | Android environment flavors/protected signing gates with no debug release fallback; metadata/symbol handling and release inspection. Shared readable state vocabulary, chart time/gap/text alternatives, focus/keyboard/reduced-motion/reflow/contrast checks. | Protected organizational signer, physical phone upgrade/background/push tests, separate iOS signing/APNs, actual screen-reader sessions and user task comprehension. |
| **F40: privacy, ownership and recovery** | Data inventory and review package; versioned access/correction/erasure cases, holds and redacted evidence; bounded retention dry runs; encrypted recovery packages and restore quarantine/no-replay guards; production governance preflight. | Responsible organization, privacy/legal review, real ownership/retention/service decisions, keys/backups/PITR and measured full-service RPO/RTO. |

### 4. Policies and hardware boundaries that must not be mistaken for approval

The owner authorized practical configurable defaults because there is no external client/operator policy yet. Those defaults are deliberately recorded as **provisional**, not government-approved policy:

- Recovery: 2 cm exit hysteresis at each tier; three recovery samples over at least 10 seconds; maximum 15-second sample gap; provisional plausibility limit 10 cm/second. Increasing severity remains immediate, including suspicious critical rises flagged for review.
- Internal issuer: **AGAPAY App Operations**, an application operator. Its application audience is not a geographic exposure map or an LGU evacuation authority.
- SOS: configurable drill defaults. No real on-call roster, emergency telephone number, responder dispatch or guaranteed response time was fabricated.
- Depth outage history: one durable record every 10 seconds, capacity 360 pending records, approximately one hour, with bounded replay and explicit eviction/gap reporting. The live stream remains separate. These are development resource defaults, not measured endurance/power acceptance.
- Rain raw retention: an engineering default of 30 days online, with explicit bounded archival; no automatic claim that archived raw data has been erased.
- Firmware fallback geometry: **unvalidated 150 cm bench height**, nominal 20–450 cm sensor range, 2 cm uncertainty, 5 cm margin and unchanged 60/85/100 cm depth tiers. This fixes software reachability under that geometry; it is not a drop-in configuration for an installation mounted at 120 cm.
- **STATION_001 retains 0.70 mm/tip**, the existing configured value. This work does not supply new controlled-volume calibration evidence.

No audit implementation in this period established the currently flashed physical profile or completed field acceptance.

### 5. ML/AI: what was actually achieved

The October 13 experimental path used an ERA5-trained rainfall Random Forest plus assumed controlled-basin physics. It was not a field-trained water-depth predictor. That scientific boundary is preserved.

The new operational product architecture supports an independently reviewed **local depth above a commissioned datum**, in cm, at 30/60/90-minute horizons. The first candidate adapter uses current valid depth and a causal measured-time rate. Rainfall is collected with interval/availability metadata, but is not an input to that first water-only adapter. Archived/future rainfall cannot be quietly substituted for available online features.

Preparation withholds complete events rather than randomly splitting neighboring rows. Evaluation compares persistence and rate extrapolation and adds event-based calibration, interval coverage, peak errors, missed/false-alarm events, lead time, missingness and reviewed strata. Approval needs real evidence, not just a favorable pooled score or a manually changed reviewed flag.

Published products carry an immutable ID, station/site/datum, source/configuration identity, cutoff, model/card/binding version, target times, generation and expiry. Web and mobile read the same stored product. Viewer requests do not retrain, alter assumptions or prolong validity. Revocation, stale/OOD inputs or configuration changes withhold current numeric output. Experiments cannot create measured alerts or official action notices.

**What has not happened:** no new field-qualified operational model, no validated flood-warning accuracy, no validated field prediction intervals and no real scientific approval. The empty/unapproved registry must produce unavailable forecasts. Retrospective rainfall scores remain rainfall scores; the UI retains the disclosure when first-hour persistence performs better.

### 6. Product and original UI restoration, 23–25 October

The fixed visual direction is to **preserve the original Figma mobile and web bases**, adapting existing components and controllers. Audit/security/data fixes stay underneath that design. A whole visual rewrite is not the current instruction.

Original Figma file: `YSzodsskD44OjBCaCyBHau`; mobile page `0:1`, web page `112:47`. Thirteen frames had full design context/screenshots captured. Later fresh MCP reads reached the Starter-plan call limit, so final comparisons used those captured originals and local exports. The Figma document was not edited.

**Mobile changes:**

- Restored the circular numeric depth dial beside the vertical gauge, including an em dash when there is no valid reading. It does not depend on powered hardware to appear.
- Preserved measured-history, forecast and rainfall panels and the raised central SOS navigation.
- Restored the prominent map frame, station/evacuation tabs, picker and legend; home/map/detail/forecast retain the shared data/freshness controller.
- Restored the large red circular SOS action and three supporting location/receipt/history cards. The circle opens consent/review; it never sends automatically. Existing receipts/outbox evidence remain prominent.
- Restored a circular solid-blue profile avatar and compact severity-bordered alert cards with timestamp/lifecycle hierarchy. Resolved alerts retain peak-tier, trigger-depth and recovery-depth meaning; full evidence remains in details.
- Corrected native light/dark defaults, readable unknown-state text, selected/muted navigation styling, map legend wrapping and large-text layouts.
- Preserved actual permission/preferences, source/quality/age, explicit test-environment disclosures and English-only translation-unavailable behavior.

**Web changes:**

- Preserved/restored dashboard statistics, map, depth chart, alert/threshold panels and the original navy/blue composition.
- Analytics includes stacked depth/rain charts, current station comparison and a database-selected range/event report. Rainfall's rolling journal scope is explicitly separate from the depth report/CSV.
- Missing/stale values cannot become current comparison bars; valid zero remains valid.
- Fixed numeric history aggregation query parsing so the UI's bucket options work; improved readable report times with exact timestamp metadata.
- Compacted System Health without conflating water, rain, heartbeat or lifecycle.
- Removed redundant standalone ML Evaluation/Published forecast sidebar entries; retained workspace tabs and functional detail/back navigation.
- Fixed theme icon masks/tints so inactive ML Configuration is muted when another sidebar section is selected.
- Fixed Users filters/role-card reflow, constrained its account dialog, and made its table a focusable horizontal-scroll region instead of clipping columns.

Shared language includes **Observed**, **Last known**, **No valid reading**, **Experimental projection** and **Official advisory**. Requested presentation wording was simplified, but wire/source flags and truthful test-only response boundaries were not erased. Sensor tiers are not public evacuation orders.

No example hazard, rainfall, unread count, forecast or static European map was restored as operational data just to match a Figma screenshot.

### 7. Verification evidence and its limits

This report was prepared by reading retained logs, implementation records, the previous report/conversations and selected current source. It did not rerun the long backend or firmware suites merely to write a report.

| Scope / date | Recorded result | Meaning and limitation |
|---|---|---|
| Initial audit, 21 Oct | Backend 240 passed; offline ML 45 passed; web 18 passed; mobile 91 passed | Earlier source snapshot before most remediation; not the current total. |
| Acceptance re-audit, 23 Oct | **Combined backend/ML: 698 passed, 1 failed, 1 skipped**, 24 warnings | The latest retained complete combined backend run is **not green**. |
| Isolated staff module after that failure | 7 passed | Does not replace the complete run's failure. |
| Latest focused channel/history-report checks | 17 passed | Tests the later report/aggregation behavior, not the entire backend. |
| Final web checks, 25 Oct | **122 passed**, production Webpack build/TypeScript succeeded | Local current web source. Not hosted CI or deployment acceptance. |
| Final mobile checks, 25 Oct | **242 passed**, analyzer clean | Unit/widget/contract/layout tests; includes both themes and large-text/contrast checks. |
| Final development Android build | Passed | Development debug APK, not a protected signed public release and not proof of phone installation. |
| Final resident browser build | Passed | Native map embedding is unavailable in this browser preview; explicit fallback is displayed. |
| Firmware re-audit, 23 Oct | Four host profiles and negative release guards passed | Actual source against host fakes; no new physical ESP32 flash/acquisition. Earlier target compilation is separately recorded. |
| Earlier synthetic browser accessibility work, 23 Oct | 24 automated axe scans, zero violations in the tested fixtures | Not rerun over every final populated screen; not WCAG certification or physical screen-reader proof. |
| Final web UI sweep | Eight sections × two themes × two widths = **32 recorded views**, 390px/1280px | One selected main-navigation item per view. Users overflow was found, fixed, rebuilt and rechecked in both themes. |
| Updated Users recheck | Main width = scroll width, 316px at a 390px viewport; table overflow auto; dialog inside viewport | Bounded observed responsive evidence, not every browser/zoom/device. |

Totals overlap across feature suites and repeated runs and must not be added together. Past dependency-audit and clean-source results are time/source-specific, not a fresh vulnerability or hosted-CI guarantee.

#### Latest complete backend failure

The failing test is `tests/test_staff_workspaces.py::test_provenance_cannot_be_relabelled`. Its unverified-scope assertion expects the new episode on the first default page, while other retained fixture episodes can precede it. The isolated module and a controlled pagination probe support that diagnosis. This is not demonstrated unauthorized physical-source promotion, but the test isolation/pagination issue still needs correction followed by a green full rerun. The PostgreSQL restore test was skipped because no target was configured.

### 8. Remaining re-audit findings and acceptance gates

The 23 October re-audit identified five additional issues. They must not disappear from the next handoff because UI checks pass.

1. **R1 — Web missing-coordinate fallback:** current `station-display.ts` can still borrow bundled fallback coordinates when API coordinates are null. Mobile uses the registry coordinates. This remains a real cross-client presentation inconsistency; a “planned” label does not make a point a verified registry location.
2. **R2 — PostgreSQL coverage:** the configured PostgreSQL lane exercises a small restore case, not the required concurrent telemetry/boot/duplicate, SOS location/resolution, stale-admin, outbox or privacy/identity interleavings. SQLite passes cannot close those engine-specific criteria.
3. **R3 — Exact release integration:** essential work remains untracked/unstaged. A sanitized source rehearsal can include it, but a normal hosted checkout only gets the eventual committed scope. No complete verified release revision/hosted run for the combined implementation has been established.
4. **R4 — Physical configuration review eligibility:** source authentication and configuration-hash agreement exist, but the shared sensor decision path does not enforce field-review status as a production operational-eligibility gate. A synthetic matching prototype configuration could create a current critical episode and notification intent. No external send occurred. Define/enforce the production policy or a deliberate audited exception without discarding critical raw observations or erasing incidents.
5. **R5 — Full-suite reliability:** fix the test isolation/pagination assumption and rerun the complete backend/ML suite, retaining the result and PostgreSQL skip/failure status honestly.

Other essential acceptance remains open:

- **Physical P0/F16:** installed sensor geometry, datum, uncertainty/range margin, every approved tier, blind-zone/fault/offline behavior and controlled-volume rain tests.
- Real station/authority/geographic/maintenance policy approval; no public-authority identity is fabricated.
- Real SMTP/MFA recovery, HTTPS/broker/proxy deployment and supervised workers.
- Real duty ownership, operating hours/fallback contacts, verified shelters/roads and witnessed SOS response drills.
- Physical phone permissions, background/offline/restart/upgrade/push-receipt stages; distinct Android and iOS acceptance.
- Reviewed paired field data, withheld real storms/negative events, baseline gains, calibrated uncertainty and accepted miss/false-alarm/lead-time tradeoffs.
- Actual resident/officer comprehension and NVDA/TalkBack/VoiceOver sessions. The recorded participant count remains zero.
- Organization-approved privacy/retention/access decisions, accountable service ownership, managed backups and full restore/no-replay drills against chosen RPO/RTO.

### 9. Phone and preview status at the last verification

An earlier restored development APK was installed on the USB Oppo CPH2269 and the circular dial was seen on the physical phone with no valid measurement. That does not establish the final build or native Maps/push behavior.

At the final October 25 pass, **ADB listed no connected device**. The newest APK was built but not installed. Earlier phone Maps failure coincided with an unvalidated/captive-portal network; USB API forwarding does not provide Google Maps internet access. No network security or certificate validation was weakened.

The final browser app's map explicitly says interactive maps are unavailable in this preview and retains text details. This is a platform limitation, not evidence that the Android map was deleted or that it currently works end to end.

Latest local preview addresses, as last verified:

- Staff web: `http://127.0.0.1:3011/analytics` (dashboard and other command sections remain available).
- Resident browser: `http://127.0.0.1:8095/#/main`.
- API: `http://127.0.0.1:8000`.

Older 8080 origins continued serving old UI from browser service-worker caches. Port 8095 was used as an isolated loopback origin and the final map explanation was visibly verified there. The cache/update behavior of any future distributed web app remains a separate release concern.

The UI preview API uses `data/ui-preview-20261023/agapay-preview.db`, an existing private migrated copy. Device ingestion, demo seeding, SMTP and external notification delivery are disabled for this preview. Therefore unknown measurements and unavailable forecasts are expected; they are not to be filled with demo numbers. Ports/listeners and USB presence are snapshots and should be rechecked before the next session.

### 10. Repository/data preservation

At report preparation:

- Branch: `feature/day1-foundation`.
- HEAD: `67f85e0`.
- **48 pre-existing staged paths remain**; substantial additional source/docs are unstaged or untracked.
- No staging, commit, push, merge or public deployment was performed for this audit/UI work or this report.
- The original operational/development database was not reset or reseeded. Copy upgrade/recovery rehearsals and test fixtures are separate from deployment acceptance.
- No ESP32 firmware flash, NVS erase or filesystem format was performed in this remediation/UI period.
- No operational emergency notification or real dispatch was sent.
- This handoff intentionally contains no passwords, station tokens, provider credentials, signing secrets or resident incident details.

### 11. Recommended next work for ChatGPT/Codex

1. Keep the existing architecture and the owner's original Figma design. Preserve the home circle/gauge, chart composition, map navigation and the implemented trust/null/freshness/SOS contracts.
2. Prioritize **R4 operational eligibility**, **R1 missing coordinates** and **R5 regression isolation/full rerun**. Inspect the actual current source before patching; do not automatically replay stale writes.
3. Add and execute the disposable **PostgreSQL concurrency and linked-data restore matrix**. Do not substitute SQLite or a one-station restore for that evidence.
4. Review the exact intended source/dependency/artifact scope and produce a clean, reproducible release candidate when repository publication is authorized. Execute its hosted profiles/containers/contracts and retain results.
5. Continue physical F16/IoT commissioning and phone acceptance separately. Preserve local fail-safe sensing and collect device plus broker/backend evidence.
6. Keep forecast output unavailable until the field/model/independent-review gates are genuinely met. Do not “complete” ML by approving synthetic evidence, loading placeholders or presenting ERA5 rainfall skill as flood accuracy.
7. Enable actual notices, public shelter inventory, operational response and public deployment only against real accountable procedures, authorities, privacy decisions and tested recovery.
8. Record future work as **implemented / tested locally / deployed / field-accepted** separately. Report failed and skipped tests, cache limitations and absent device evidence rather than claiming perfect completion.

### 12. Evidence index

Primary local records:

- Prior report: `agapay-docs/LATEST_ML_DASHBOARD_REPORT_2026-10-13.md`.
- Resident-only/ML bridge: `agapay-docs/ML_UI_MOBILE_PREVIEW_2026-10-21.md`.
- Original audit/backlog: `agapay-docs/audits/2026-10-21/`.
- Acceptance re-audit, matrix and failed full-run evidence: `agapay-docs/audits/2026-10-23-reaudit/`.
- Finding implementation/results/runbooks: `agapay-docs/security/F01-F02/` through `F40/`.
- Product workflow records: `agapay-docs/design/resident-decisions/`, `resident-sos-map/`, `staff-decisions/`, `forecast-operations/`, `shared-vocabulary/`.
- UI contract/restoration: `agapay-docs/design/UI-PRESERVATION.md`, `FIGMA-BASELINE-REVIEW-2026-10-24.md` (includes October 25 follow-up), and the dated theme/navigation/mobile review notes.
- Final UI/build evidence: `data/ui-preview-20261023/design-restoration/`, particularly `final-mobile-suite-verified.log`, `final-mobile-analyzer.log`, `final-mobile-apk.log`, `final-mobile-web-build.log`, `final-web-tests.log`, `final-web-build.log`, `final-web-responsive-checks.json`, `final-users-recheck.json` and final resident screenshots.
- Latest APK: `agapay-mobile/build/app/outputs/flutter-apk/app-development-debug.apk` — development artifact; not a signed public release or an installed-phone acceptance result.

**Handoff conclusion:** the system now has substantially stronger trust, data, workflow, release and UI foundations than the October 13/21 baseline. The next work is closing the explicit engineering and acceptance gaps above, not declaring production readiness or replacing the restored original UI.

