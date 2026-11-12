# Published forecast evidence and resident-service operations

Implemented in the existing staff web application. The new **Published forecasts** navigation opens `/forecasts`; **Operations console** retains `/system-health`. Existing station monitoring, published products, model registry, themes, review permissions and delivery evidence are reused. Mobile remains resident-only.

## Forecast decisions

The forecast workspace answers “What was published, with what evidence?” before offering private experiments or privileged changes:

- Selected station, current publication availability/reason, deployed binding and model review state, including current versus bound review versions and independent review digest.
- Bounded, immutable product history. Each product shows its own forecast ID, generation/expiry, model/configuration versions, datum, source identity/registry version, measured input coverage/cutoff, calibrated intervals, calibration/test-event counts, nominal/observed coverage and display resolution. A real zero remains a measurement; missing forecasts do not become zero.
- Historical, expired, superseded and revoked products retain original values while losing any current-use label. Reopening or refreshing cannot extend a product's expiry. An unavailable read, mismatched station or expired check cannot establish current publication.
- Evaluation is fetched for the exact deployed model ID, station, configuration and review version. The immutable bundle digest is checked before its evidence is returned. Display candidate/reference depth errors and reuse the existing event-based decision evaluation. Current deployed evidence is explicitly distinguished from approval of a historical release.
- Private rainfall/basin experiments and model/binding reviews have separate entry points. No experiment setting writes a published product. Reviewed changes retain reasons, captured versions, independent approval and manual conflict review.

The registry form now initializes to the recorded deployed model instead of implicitly selecting “disable forecasts.” Binding and model-review reasons are separate. Mutation failures block another submission until explicit manual refresh/review. A failed registry read is not presented as an empty trained-model catalogue.

## Service decisions

The operations console answers “Is the service working through to residents?” with:

- Required-capability readiness and specific dependency fault codes. Optional/disabled delivery is never proof of a resident service.
- Platform-wide unresolved pending, processing, overdue, unknown and failed delivery counts, original queue ages, configured budgets and provider mode. Detailed delivery rows retain the existing administrator/jurisdiction restrictions.
- Bounded eligible-packet ingress progress; independent station channels remain available in a secondary disclosure. Receipt progress is not last-valid-depth freshness or rain health.
- Worker heartbeats and last successful progress, with expiring current-state labels. A healthy heartbeat without recent successful progress stays unconfirmed/degraded.
- Five-minute workflow event/failure counts and p95/p99 histogram upper bounds. Empty metrics are unknown, not zero latency. Unique durable app receipt/open and explicit resident acknowledgement now record server-observed queue-to-stage durations without inventing missing stages or counting exact duplicate callbacks twice. Callbacks do not independently prove phone display.
- External provider quota/billing evidence is explicitly **unknown** where telemetry is not connected. Local resource budgets are shown separately from provider capacity.
- Existing versioned delivery reconciliation, guided investigation/recovery steps, downloadable captured diagnostics and an administrator-only audited recovery-review receipt. Review references are hashed in the browser; plaintext external references are not submitted.

A recovery review is an operator attestation. It does not restart services, clear faults, resend a message, reset UNKNOWN/PROCESSING, acknowledge a resident action or release restore quarantine. Actual service supervision and encrypted restore procedures remain controlled operational actions outside this console. Stale or failed evidence blocks delivery review; manual refresh clears the old review page while reloading.

## API and contract changes

- `GET /api/forecast-workspaces/{station_id}?limit=5&offset=0`: staff-only publication/binding state and stable history pagination, capped at 20 records.
- `GET /api/forecast-registry/{model_sha256}/evidence`: staff-only evaluation tied to the immutable registered bundle; integrity failure returns unavailable.
- `GET /api/operations/diagnostics`: adds safe worker, ingress, queue, local-budget and unknown-provider-quota evidence. Worker detail strings and credentials are not exposed.
- `POST /api/operations/recovery-reviews`: administrator-only append-only audit receipt with captured diagnostic time, fault code, completed activity, reason and evidence digest. Future or older-than-one-day captured checks require refresh. Namespaced audit fields preserve redaction of generic verification-code/opaque-source fields.
- Web proxy paths/methods and bounded query forwarding are allowlisted. Shared OpenAPI artifacts and TypeScript/Dart contract fingerprints were regenerated. No database schema migration, demo bootstrap, firmware flash or live data reset was needed.

## Observed validation

- **65 backend tests passed**: new workspaces plus registry, operational health, delivery evidence and generated/shared contracts. Includes approval revocation, immutable history, stable pagination, bundle corruption, overdue/missing-time processing, fractional worker-heartbeat age, role/time/body restrictions, audit redaction, unique app-stage latency and preservation of uncertain deliveries/faults.
- **102 web checks passed**, including publication expiry/binding/review identity, unknown/zero distinctions, worker progress, stale diagnostics, existing review conflicts and preservation of the current deployment selection.
- **26 mobile forecast/contract tests passed** after regenerating the shared fingerprint. No resident staff/ML controls were introduced.
- Final production webpack build passed, including TypeScript validation.
- New production-browser workflow passed exact model/coverage/intervals, historical and revoked products, station switch/empty state, delivery conflict/manual review, hashed recovery receipt, outage locking and resident staff-boundary checks. Four both-theme automated accessibility scans report zero violations; 390px/200% text checks pass.
- Existing forecast/privacy/keyboard workflow and staff incident/station workflow also pass. Their 16 additional automated accessibility scans report zero violations. These are automated and synthetic checks, not a blanket accessibility certification or physical-phone delivery test.

All browser identities, stations, products, model states, provider outcomes and review receipts are synthetic loopback fixtures. External browser requests are blocked. No real Firebase, email, Maps, resident delivery, authority approval or operational recovery was performed. PostgreSQL-specific concurrency, production quotas, field uncertainty calibration, physical receipt and operator drills remain separate deployment evidence.

## Previews

- [Forecast workspace — light](forecast-light.png) · [dark](forecast-dark.png) · [narrow large text](forecast-narrow.png)
- [Operations console — light](operations-light.png) · [dark](operations-dark.png) · [narrow large text](operations-narrow.png)
- [New-workspace accessibility results](accessibility-results.json) · [existing-workflow accessibility results](existing-workflows-a11y.json)

Browser validation is exposed as `npm run test:forecast-operations` and included in web CI alongside the existing browser workflows. No commit or push was performed; the pre-existing staged set was preserved.
