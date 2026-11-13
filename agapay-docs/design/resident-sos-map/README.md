# Resident SOS and maps — receipts, responsibility and usable resources

Implemented 2026-10-23 in the resident Flutter app. Existing themes, panels, SOS drafts/outbox, monitoring views, response registry, drill activity and map components were reused. No backend schema, live database, deployment or external provider was changed. No real request, GPS fix, shelter activation, route or response coverage was invented.

## Resident SOS

Reading order is practice boundary → receipt/outbox evidence → explicit request/retry action → verified contact fallback → received history. Details lead with server receipt and immutable request reference, followed by recorded ownership/action evidence and the request's location/consent information. The oversized pulsing hero and duplicated received-only outbox summary were removed.

- **Queued:** saved on the device, not sent. **Unknown:** a transmission may have reached the server; the same saved reference/payload is retained for receipt lookup or deliberate retry. **Received:** evidence that the server stored the request, independently of staff review or dispatch. Rejected/conflicting requests retain their explicit review/discard rules. No stale conflict is automatically overwritten.
- The full request UUID is selectable alongside the server record ID. Both send responses and receipt lookups must match the saved reference before they can confirm receipt. A mismatched receipt remains unconfirmed.
- An existing receipt's status is labelled last-known when cached, failed or outside the reading freshness budget. A server receipt does not prove that any human saw it or that help was sent.
- Live sharing starts **off**. The resident can capture an optional one-time location and separately opt into foreground updates. Source, capture time/age and accuracy remain distinct; absent accuracy is unknown, never `±0 m`.
- Account changes clear selection, private map state, form content and sharing state. Generation checks prevent late location captures or send callbacks from filling another account/form. Cancelling a capture invalidates that result. Private SOS coordinates reach Maps only after the existing explicit map/directions action.
- Coordinator, assigned drill participant, stage and action timeline come from recorded response activity. Missing ownership remains explicitly unconfirmed. Acknowledgement is review evidence, not dispatch acceptance. Earlier actions use the existing bounded event cursor; browsing history cannot fabricate an action or owner.
- Response reads stop in the background. On resume, ownership remains last-known until a successful new check. Pending responses for an older account/request/lifecycle generation are discarded.
- The existing area-scoped reviewed contact sheet remains available as fallback. SOS remains a **practice workflow**; this redesign does not enable operational dispatch or invent a duty roster, ETA or response SLA.

## Resident map and resource list

Reading order is selected area → station/resource choice → text list and source state → optional map or generic directions. The list does not depend on Google Maps or GPS.

- Station cards use the same immutable freshness views as home/detail/forecast: original depth age, source, quality, heartbeat, rain state and unresolved hazard. Stations without coordinates remain selectable in the list; they get no invented map pin. Station geography is not inferred from distance or free-text locality.
- The station map loads only after a deliberate action and uses actual station coordinates. A failed/unavailable map leaves the list usable. Selected station controls use palette-aware foreground/background colours in both themes.
- Shelter, road and preparedness reads pass the selected `area_id` to the existing backend filter **before pagination**. An unselected area is explicitly an all-published-area view. Account/area changes discard old results and clear shelter selection, route and captured origin. The controller rejects another area's records and non-Actual inventory.
- Each resource channel has bounded page controls and an independent source-check time. Paused/background, failed, cached or aged checks cannot establish current availability. Resume requires another successful check. The 90-second reading budget is a development UI policy, not a physical availability guarantee or SLA.
- Verified active shelters sort before other statuses. Full, inactive, unverified, expired and last-known resources remain distinguishable. Capacity keeps its own observation timestamp and missingness: an hour-old occupancy report cannot establish current space even when the registry was just read successfully. Directions still require a current eligible source and do not certify space or flood-safe access.
- Source instructions, contacts, addresses, accessibility/services and road reports remain readable as text. Route/GPS failures do not remove them. Unreviewed instructions/contacts remain withheld under the existing registry contract.
- Current verified closures/restrictions have a different map presentation from last-known, expired or reopened reports, with a text explanation. Partial coverage or an empty list does not establish open roads. Generic walking directions explicitly do not incorporate these reports and never claim flood-safe access.
- Independent page-storage keys prevent navigation from confusing scroll offsets with expansion state. The existing home/alert detail expansions received the same key correction where needed.

## Verification and previews

The final full regression run passed **209 mobile tests**, including the background/resume and cancelled-GPS guards. The earlier **49 focused checks**, subsequent **18 lifecycle/SOS checks**, and final **22 preview/resource/accessibility checks** also passed and overlap that suite. Flutter analysis finished with **No issues found**. Final logs are recorded locally as `agapay-docs/resident-sos-map-*.log` (logs are ignored by Git).

The tests cover exact-reference retries and lost-response lookup, reference mismatch, rejected/conflicting sends, account clearing, explicit location consent, cancelled late GPS, background/resume checks, older response actions, shared station aging, coordinate-less stations, area changes, bounded inventory pages, map/GPS/route failure, capacity missingness, navigation and 320 px / 200% text in both themes with reduced motion.

Synthetic previews with bundled fonts:

| State | Light | Dark |
| --- | --- | --- |
| Queued SOS | [Preview](sos-queued-light.png) | [Preview](sos-queued-dark.png) |
| Received SOS | [Preview](sos-received-light.png) | [Preview](sos-received-dark.png) |
| Station list | [Preview](stations-light.png) | [Preview](stations-dark.png) |
| Shelter list | [Preview](shelters-light.png) | [Preview](shelters-dark.png) |

Run `flutter test` and `flutter analyze` from `agapay-mobile`. For fixture previews only, set `AGAPAY_CAPTURE_RESIDENT_RESPONSE_UI` to this directory's absolute path and run `flutter test test/resident_sos_map_test.dart`. The preview flag supplies no operational data or app capability.

Physical phone GPS/permission/background behavior, actual map quota/provider operation, real closure/shelter records and timed resident comprehension remain device/operational acceptance work. No dispatch, flood-safe route, physical receipt or blanket accessibility certification is claimed. No files were staged, committed or pushed; the 48 pre-existing staged paths were preserved.
