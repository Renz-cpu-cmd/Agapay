# Resident home and alerts — decision hierarchy

Implemented 2026-10-23 in the resident Flutter app, using the existing themes, panels, gauge, charts, account preferences, monitoring freshness, response registry and delivery evidence. The command web application and staff workflows were not redesigned in this change.

| Surface | Reading order |
| --- | --- |
| Home | Selected verified area → next action and help shortcuts → current area advisories → reviewed contacts/help → selected station depth, age and quality → expandable measurement details → measured trend/rain → separate published forecast → explicit exercise workspace |
| Alerts | Selected verified area → current notices/history controls → issuer, area, change/lifecycle, severity/certainty, instruction and effective/expiry times → separate all-station sensor episodes and resolved history → supported delivery acknowledgement evidence |

The top help shortcuts open practice SOS and a text contact sheet. SOS retains its existing practice/dispatch disclosure. Contact references must be reviewed, Actual and explicitly include the selected area; stale references keep a last-known label. Unreviewed references and references for other areas do not supply contacts. No response hours, telephone numbers or shelter activation were invented.

Area selection persists through the existing versioned account preferences. It filters reading scope, independently of sensor selection and push subscriptions. Failed/stale writes keep the saved advisory scope and require manual refresh. No free-text locality or nearest-station rule establishes geographic applicability.

## Contract changes

- `GET /api/official-notices` adds optional `area_id`, `status` and `current_only` filters, applied **before** bounded pagination. Exact JSON array membership supports SQLite and PostgreSQL syntax; a similar area-code prefix cannot match accidentally. Existing unfiltered callers remain compatible.
- Responses add `checked_at`, `has_more` and an echoed `scope`. Current scope includes unexpired terminal records, including cancellations and scheduled notices. History retains superseded/expired records. An update does not resurrect its superseded predecessor when it later expires.
- One account/area-scoped notice controller supplies both home and alerts. Current and paginated historical feeds stay separate. Requests and one-second expiry clocks are shared; history is fetched on demand. There is no per-screen notice polling loop.
- Operational notice reads request `status=Actual`. The controller rejects mismatched scope, another area's rows and Test/Exercise records. No selected area triggers no unscoped operational notice request.
- Successful server check times age in place; offline cache, errors, background pause and checks older than 90 seconds cannot supply confirmed current instructions. Resume requires a successful new check. This development freshness budget is a reading-state rule, not a delivery SLA.
- Account/area changes discard old feeds; generation checks reject delayed responses. The notice tab resets to current scope after such a change. Exact original timestamps remain visible in Philippine time independently of device timezone.
- Cancelled, expired, superseded, scheduled or unconfirmed instructions are explicitly recorded instructions, rather than current actions. “ISSUED” identifies the message type; the UI does not invent an unread/new badge. Official notices have no invented acknowledgement or responder receipt. Existing supported push-record acknowledgement remains separate.
- The home gauge retains nullable values, valid zero and original depth timestamps. Device heartbeat, rain health and measurement quality remain independent. Unresolved sensor episodes remain visible with retained readings. Configuration diagnostics and measured-time rate/range/coverage remain accessible in expandable sections; no hardcoded generic threshold progress bar is retained.
- Resident forecasts use the existing reviewed published product. They are collapsed in a separate region with approval/input/expiry context. Private ML/basin controls remain outside the resident operational journey; simulation still requires explicit exercise entry.

Deploy the compatible backend response first, then the mobile change. An older cached notice response without the new scope/check contract is treated as unavailable; it is not silently upgraded to current advice. No schema migration, demo bootstrap or live-data change is required by this redesign.

## Verification

- Backend governance suite: **14 passed**, including more than a page of other-area noise, exact area filtering before pagination, Actual/Test separation, cancellation visibility, superseded history, expiry and authentication.
- Full mobile suite after the layout/rate/navigation updates: **200 passed**. Subsequent final area-conflict/contact guards and two additional tests were checked in the **17-test** decision/accessibility subset; these overlap the full suite and are not additive unique-test counts.
- Flutter static analysis: see the final local `resident-redesign-analyze.log` in `agapay-docs/`.
- Both themes were exercised at 320 px / 200% text with reduced motion. Existing unknown, zero, stale, invalid, measured-time rate and shared freshness regressions were preserved. The contact sheet's navigation was exercised, including closing it before opening the shelter list.
- Synthetic 390×844 previews with bundled fonts were rendered and visually inspected: [home light](home-light.png), [home dark](home-dark.png), [alerts light](alerts-light.png), [alerts dark](alerts-dark.png). These are fixture screenshots, not live authority notices or physical-phone proof.

Commands from `agapay-mobile`: `flutter test` and `flutter analyze`. To refresh only the previews and decision regressions, set `AGAPAY_CAPTURE_RESIDENT_UI` to this directory's absolute path and run `flutter test test/resident_decisions_test.dart`. No preview environment option changes the production app or supplies operational data.

The PostgreSQL-specific notice membership path still needs real-engine deployment execution. TalkBack/VoiceOver, physical-phone behavior, large real notice inventories and timed resident/officer comprehension tests remain acceptance work. No blanket accessibility certification, operational SOS dispatch or live forecast readiness is claimed. Nothing was staged, committed or pushed; the 48 pre-existing staged paths were preserved.
