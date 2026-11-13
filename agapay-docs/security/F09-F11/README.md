# F09–F11: stable sensor episodes, issuer notices and targeted push

Implemented locally on `feature/day1-foundation`, based at `67f85e0`. The app owner requested usable prototype defaults while no external client/operator policy exists. [prototype-policy.json](prototype-policy.json) records those choices. Live activation and physical validation remain separate from code verification.

## Sensor policy

Version 0 uses 2 cm exit hysteresis at every tier, three consecutive recovery samples spanning at least 10 seconds, a maximum 15-second sample gap, and a provisional plausibility limit of 10 cm/second. Values outside sensor height also require review. These are application defaults, not calibrated flood-domain thresholds. Entry thresholds remain the station's existing configured values.

Every severity increase is immediate. A suspicious critical rise still escalates and is flagged for review. Downward spikes cannot recover an episode. Recovery checks every crossed exit band; a fall just below 60 cm cannot resolve an advisory and create another episode at the next borderline sample. Invalid samples, excessive gaps, a new boot/session and policy changes reset recovery persistence. Durations use ordered device measurement times inside the same station ingestion transaction used by HTTP and MQTT. Late, retained and duplicate traffic cannot advance recovery.

`hazard_decisions` records each eligible sample's observed tier, resulting episode tier, policy version, decision reason and review flag. `GET /api/stations/{id}/hazard-policy` exposes provisional or station-reviewed configuration. Administrators can approve a station policy through `POST` to the same path with `expected_version`, `rules`, `validation_evidence` and `reason`. Conflicts return 409 without retrying or overwriting a newer policy. Previous and new rules remain in the governance audit.

Monitoring separates `observation_tier` from the active policy episode, exposes `hazard_policy_state`, `hazard_decision` and `hazard_review_required`, and keeps held episodes unresolved even when the latest lower measurement is fresh. Plausibility-review samples cannot initialize hybrid projections and invalidate ordinary model input windows. Web current-value statistics exclude review samples. Mobile displays the observation, episode and policy state separately.

Authorized staff can record `confirmed`, `investigate` or `request_escalation` reviews at `POST /api/sensor-alerts/{id}/reviews`. The request includes authority, reason and the current `expected_telemetry_id`; stale reviews return 409. Reviews never rewrite sensor measurements or bypass recovery. A human action message uses the separate notice workflow.

## App advisories and public-authority actions

Sensor episodes, experimental forecasts, app advisories and authority-issued action messages have different representations. No sensor threshold says “Mandatory evacuation” or claims that a normal/unknown tier establishes safety.

`official_notices` is a separate immutable record stream. Each message stores issuer identity/class, affected area IDs/names, actor, issue/effective/expiry times, Actual/Test/Exercise status, urgency, severity, certainty, category, instructions and reason. Updates and cancellations reference the current previous message, reject already superseded references, and preserve the issuer/status. Clients display references and recompute expiry while a response is cached. Failed or malformed notice responses cannot claim that the notice feed is confirmed.

The metadata and reference lifecycle are informed by [OASIS CAP 1.2](https://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2-os.pdf). This is not a claim of CAP XML conformance, digital signature verification, government authorization or external public-warning integration.

**AGAPAY App Operations** is an internal `app_operator`, suitable for app advisories. Its `AGAPAY:APPLICATION` identifier represents an application audience, not geography or flood exposure. An Actual authority action requires a separately registered `public_authority`, geographic area identifiers and an explicit staff jurisdiction grant. No government issuer is invented or automatically commissioned.

Staff use **Alerts → App advisories and authority notices → Compose notice**, then choose an authorized issuer, areas, status, category, urgency/severity/certainty, instructions and validity. Existing messages have correction/cancellation controls. The composer defaults to Test. Residents see the distinct notice feed in mobile Alerts with persistent Test/Exercise labels and issuer/lifecycle metadata. Notice publication creates an in-app record; it does not silently send citywide push.

## Explicit notification audiences

Ordinary sensor escalation now captures only active resident devices whose owners explicitly subscribed to the station or one of its registered affected areas. Resident subscriptions, verified geographic/application identifiers and station-to-area bindings are separate from free-text profile locality, selected map station and staff jurisdiction.

Residents manage these choices at **Profile → Push alert subscriptions → Choose stations and areas**. Versioned writes reject stale changes. Nothing auto-enrolls a new user or replays older events. A profile barangay edit cannot change targeting. The community sensor feed remains citywide visibility; push subscriptions are a separate delivery choice.

Each outbox delivery captures the subscription revision and, for area targeting, the station-area binding revision. Workers recheck these, device/account eligibility and superseding transitions before sending. Unsubscribe/re-subscribe or remove/re-add of an area mapping cannot revive an old queued send. Legacy unscoped deliveries are suppressed rather than broadcast. Existing no-replay handling for ambiguous provider outcomes remains intact.

Citywide distribution is a separate staff action: `POST /api/alert-governance/transitions/{id}/citywide` requires an active explicit citywide authority grant, a substantial reason and expiry within one hour. It rejects resolved/superseded escalations and duplicate dispatches, captures currently registered devices, and never replays an existing delivery, including UNKNOWN outcomes. The audit records issuer, actor, reason, transition, expiry and recipient count. Citywide push identifies its distribution and authorizer while remaining a sensor notification. It is not an evacuation order.

## Activation

No live schema migration, account/authority grant, subscription enrollment, service restart, deployment, mobile installation, firmware operation or external notification was performed by this implementation.

First follow the [F01/F02](../F01-F02/README.md), [F03/F04](../F03-F04/README.md) and [F05/F06](../F05-F06/README.md) prerequisites. Back up the target database and deploy backend/web/mobile together. From `agapay-backend`, review and apply only the additive governance tables:

```powershell
.\.venv-auth\Scripts\python.exe -m app.migrate_alert_governance
.\.venv-auth\Scripts\python.exe -m app.migrate_alert_governance --apply
```

The following prepares the internal app issuer for an **existing active administrator**. Replace the example address with the actual administrator. The first command checks the plan; the second applies it. Existing differing grants cause an error, never a silent overwrite. No residents are subscribed and no station-to-area mapping is inferred.

```powershell
.\.venv-auth\Scripts\python.exe -m app.bootstrap_prototype_governance --admin-email admin@example.com --station STATION_001
.\.venv-auth\Scripts\python.exe -m app.bootstrap_prototype_governance --admin-email admin@example.com --station STATION_001 --apply
```

Citywide permission is disabled by default. Deliberately add `--allow-citywide` only for an administrator authorized to perform that application function. A differing existing grant must be changed through the versioned grant API. This flag grants permission; sending still requires a separate audited dispatch request.

Administrative API operations are available under `/api/alert-governance`: create areas/authorities; version staff grants; explicitly bind station areas; revoke bindings with their current revision; and inspect the audit. Area IDs are registered against their stated identifier scheme/evidence and must never be inferred from nearest-station distance or profile labels. Initial bindings use revision 0, rebindings provide `expected_revisions`, and revocations use `expected_revision`. Live public-authority credentials, geographic scope and physical policy approval require real evidence.

See [verification results](RESULTS.md) for observed local checks and limitations.
