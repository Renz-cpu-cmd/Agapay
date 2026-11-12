# Staff decisions and station evidence

Implemented in the existing staff web application using its themes, monitoring controller, maps, rain panel, forecast panel and lifecycle administration. Mobile remains resident-only.

## Command center

- Persistent sensor episodes lead the page, ordered on the server by critical/warning/advisory tier, then oldest episode, before bounded pagination.
- Trigger and latest observation must both have a recorded physical source designation matching their historical registry version to enter the physical-source scope. Legacy/unverified episodes have a separate review scope; counts for both scopes remain visible. This is identity evidence, not proof of physical calibration, exposure or an official evacuation order.
- Show episode reference, start time and elapsed time, recorded owner and change time, verified area bindings, current measurement quality/age and a specific next evidence check.
- Staff can take unassigned review responsibility or release their own responsibility. An administrator can record a supervised release. Taking another person's assignment is rejected. Reasons and before/after ownership are appended to existing governance and general audit records.
- Station faults, maintenance, station-location context and measured trends follow the queue. Authority notices/history, service/delivery diagnostics and response resources retain their existing workspaces. Practice SOS and private experiments are separate, explicitly named regions.

## Station workspace

- Provisioned identity, historical last-valid ingress identity, current source/depth trust, identity version, reference datum, configuration revision/expected/applied hashes, local profile/fault and administration precede charts.
- Latest eligible measured/received times, independent last-valid measured/received times, latest packet receipt/disposition and heartbeat time stay distinct. A delayed packet or invalid heartbeat cannot date a retained depth as new.
- Water, rain counter, heartbeat and broker health use the shared independently aged monitoring view.
- Charts use numeric measured timestamps and linear segments, preserving invalid values and gaps longer than the monitoring expiry. Unknown measurement times are excluded from the plotted timeline and retained in the timestamped text alternative. The monitoring history contract now explicitly includes nullable `measured_at` and `received_at`; legacy `recorded_at` remains compatible.
- Configured thresholds retain reviewed/provisional labels. Show calibration documentation, each station's rain coefficient, bounded audit logs and separate administration controls. Longer-range reports use the existing persisted history workspace.
- Valid provisioned station IDs can open a workspace; the former route guard that allowed only bundled demo station IDs was removed. Missing stations and unavailable registry reads have explicit states.

## Contracts and conflict behavior

`GET /api/alerts/command-queue?scope=operational|unverified&limit=20&offset=0`

`POST /api/alerts/{id}/ownership` requires action, reason, expected ownership revision and expected latest telemetry ID. Station-row serialization is shared with ingestion. Resolved episodes, changed samples, changed ownership or another owner return a conflict. No automatic mutation retry occurs; the UI requires an explicit refresh and manual review. Responsibility does not acknowledge a public notice, dispatch a responder, resolve the hazard or send notifications.

`GET /api/stations/{id}/workspace?limit=20&offset=0` returns a staff-only, allowlisted identity/sample/log view without credentials, tokens or arbitrary audit details. New response schemas are exposed in OpenAPI. The web proxy allowlists these paths/methods and bounded scope/page parameters. Existing database tables are reused; no live migration or bootstrap was run.

## Verification and limits

Production-browser fixtures use a synthetic officer, station, identity, area and incident. They demonstrate invalid current water, an hour-old retained depth, independent stale rain and a configuration mismatch. No real account, field device, Maps request, resident delivery or dispatch is involved.

- Web: 97 unit/contract checks pass; production webpack build includes TypeScript validation.
- Backend: seven focused workspace tests pass, including concurrent SQLite ownership claims, priority before pagination, stale/closed conflicts, supervised release, source separation, sample-time contracts and redacted log pagination. The broader run passed 118 related checks; its additional workspace fixture used an unauthenticated request with an unsupported one-row limit, which was corrected and passed in the focused rerun. PostgreSQL ownership concurrency was not exercised here.
- Browser: ownership conflict stays blocked across polling; manual refresh and saved ownership work; proxy scope, dynamically provisioned station route, invalid/retained measurement evidence, chart gaps, incident-service outage and resident staff-access denial are checked. Four automated WCAG scans (two surfaces, both themes) report zero violations. A 390px viewport at 200% text has no document overflow. These checks do not replace manual screen-reader or operator field trials.
- Existing browser regression workflow also passes forecast expiry/withdrawal/outage and zero-value presentation, privacy-request receipt/password clearing, anonymous/resident staff boundaries, keyboard skip link, dialog focus and focus return. Its 12 additional both-theme automated accessibility scans report zero violations. The final build and screenshots include the neutral unconfirmed-depth header state.
- Screenshots: [command light](command-light.png), [command dark](command-dark.png), [station light](station-light.png), [station dark](station-dark.png), [narrow large text](station-narrow.png). All data is synthetic.

Affected-area polygons, current flood extent, dispatch readiness, field calibration and authority approval are not invented. The map shows available station context; verified bindings are listed as configured relevance, not measured flood exposure. Physical commissioning, operational procedures and domain approvals remain separate release evidence.
