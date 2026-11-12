# Shared operational language and decision review

The production web and resident mobile interfaces use the same display vocabulary. Internal API enums and incident histories are preserved. The shared executable cases are in `../../contracts/operational-presentation-cases.json`; both platforms test them.

| Label | Meaning and required supporting facts |
|---|---|
| Observed | Fresh valid operational reading from a trusted source, with measurement time. This is a station observation, not an authority instruction or proof of conditions at a resident's home. |
| Last known | Retained reading or dated service information whose current state cannot be confirmed. Keep original time, age, source and the reason it is retained. An unknown timestamp is explicitly unknown. |
| No valid reading | No usable measurement is available. Show an em dash; do not substitute zero, sample data or a simulated hazard. Latest-sample invalidity is a separate fact when a prior valid value remains available. |
| Experimental projection | Private/experimental model output, separate from observed measurements and the reviewed published forecast. Preserve expiry, assumptions, input source and model state. |
| Official advisory | Issuer-verified public-authority advisory, with area, effective/expiry times and lifecycle. App-operator advisories, tests and exercises retain explicit source/status labels. Authority-issued actions retain their distinct category and issuer. |
| Practice SOS | Recorded drill request. Queued, unknown and server received are distinct; receipt does not mean an officer has read it or a responder has been dispatched. |

Use **Water depth (cm)** for the current local sensor-depth quantity. A station's reference datum appears separately; absent commissioning evidence is **unconfirmed**. These values are not a common geographic elevation. Do not relabel depth as gauge level or compare stations as if their datums were identical. Rain remains a separately dated interval product, including zero versus missing coverage.

## Independent facts

Home, station cards, station evidence and map descriptions expose observation tier, episode tier/lifecycle, connectivity/heartbeat age, reading label, latest-sample validity and measurement time. An invalid heartbeat may coexist with an online device and an unresolved EVACUATE episode. In that case the current observation tier is UNKNOWN; the historical episode remains visible. Marker color is a secondary hint. Map titles, text lists and selected-station evidence carry the same facts.

`StationStatusFacts` and mobile `MonitoringStatus` supply these words. The mobile home shows them without opening an evidence expander. Gauge semantics use Water depth and honor reduced-motion settings. SOS navigation uses Practice SOS. No wire names or stored episode severity have been renamed.

## Automated review scope

Run from the indicated project directories:

```powershell
# agapay-web
npm test
npm run build -- --webpack
npm run test:operational-states
npm run test:browser
npm run test:staff-workspaces
npm run test:forecast-operations

# agapay-mobile
C:/flutter/bin/flutter.bat analyze
C:/flutter/bin/flutter.bat test --reporter expanded
```

The new browser workflow renders real production pages against synthetic loopback HTTP fixtures. It checks zero/missing/critical/invalid/stale cases, missing rain, retained outage state and an empty registry. It captures light/dark desktop and 320 px / 200% text views, accessible-tree snapshots and axe results. External provider requests are blocked. The Flutter scenario tests check independent semantic facts in both themes at 320 px / 200% text. Existing workflow tests cover forecast expiry, staff conflicts and resident receipt/location/map behavior. These are automated checks, not live screen-reader sessions or observed emergency use.

See `scenario-review.csv` for coverage and gaps; `validation.md` records this run's actual results. Screenshot and `.aria.txt` files use synthetic identities/readings only. No real phone, gauge, Maps quota, notification receipt or human comprehension is established by these fixtures.

## Human review still required

Use `comprehension-protocol.md` and the empty `comprehension-results.csv`. Current participant count: **0**. Task comprehension, completion time, critical misunderstandings and native screen-reader outcomes are **not measured**. Do not treat visual polish, an accessible tree or zero automated violations as validation of emergency usability.

Run every scenario with real NVDA/keyboard on web and TalkBack/VoiceOver on supported physical mobile platforms; repeat light/dark, narrow widths, large text, focus return and interruptions. Record device/OS/app build, exact scenario, reviewer, date, observed outcome and issue evidence. Device checks and community/operator comprehension are release evidence that must be collected separately.
