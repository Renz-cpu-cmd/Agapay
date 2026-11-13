# F07/F08 — measurement availability and resident exercise isolation

Implemented locally October 21, 2026 on `feature/day1-foundation`, HEAD `67f85e0`. Client rollout is pending. The original audit remains a snapshot of the earlier behavior.

Web stations now carry `depth` and `rain` measurement objects with nullable values, measurement timestamps, ages, quality, latest-sample quality, state and reason. Missing and invalid readings show an em dash. Valid zero remains numeric. Last-known values remain visible with their actual measurement time and retained/stale reason. Rainfall quality is independent of ultrasonic quality.

Current depth extrema and mean include only fresh, valid measurements from trusted operational sources, with a station coverage count. A historical maximum uses only recorded valid samples and reports its own window coverage; an empty window has no maximum or tier. Invalid samples remain chart gaps. Comparison charts join station samples by timestamp rather than array index. Reports and CSV exports share the same measurement/coverage rows; CSV includes every station in the current filter. The bounded received history is not presented as a complete day or week.

Dashboard, station cards/detail, analytics, map footer, system health and the forecast's measured-depth panel use the availability contract. Model projections remain separately labeled as projections.

Resident home and station alert details now start with an explicit UNKNOWN hazard and unavailable gauge, without example depth, rainfall, trend or rate. Loading, an empty response, an invalid first reading and API failure preserve this state. Real cached measurements retain their age and last-known labeling. The home heading uses the selected station, then the account's barangay. `AppController.alert` is derived from monitoring and cannot be set by exercise controls.

Use **Open exercise workspace** at the bottom of resident home to enter practice. The separate route has a persistent **EXERCISE · SIMULATED DATA** app bar and local scenario state. It has no operational controller or API writes. Returning to home leaves the operational measurements and alerts unchanged. Feed failure never opens the route.

Deploy the web and mobile clients against the F05/F06 backend contract after following the [source/freshness rollout](../F05-F06/README.md). F07/F08 add no backend schema migration. Rebuild/release the web client and install/release the Flutter client through the normal deployment process. Confirm the four measurement states and explicit exercise entry against the deployed services before marking rollout complete.

See [verification results](RESULTS.md). These checks use local builds, component rendering, mocked requests and widget tests; they do not attest real-device connectivity, calibration or emergency readiness.
