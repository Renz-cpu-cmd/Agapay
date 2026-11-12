# Original Figma baseline review — 24 October 2026

The user's original UI bases are the [Agapay_Mobile page](https://www.figma.com/design/YSzodsskD44OjBCaCyBHau/Agapay?node-id=0-1) and [Agapay_Website page](https://www.figma.com/design/YSzodsskD44OjBCaCyBHau/Agapay?node-id=112-47). These govern visual restoration; the audit does not authorize replacing their design with another information architecture.

The Figma MCP was used to read page metadata and obtain full design context plus screenshots for thirteen frames. The Figma document was not edited.

| Surface | Original node | Elements to retain or adopt | Comparison / implementation status |
| --- | --- | --- | --- |
| Mobile home | `445:3899` | AGAPAY header, warning card, source strip, vertical gauge beside a circular numeric readout, threshold scale, rainfall/station summary and forecast cards | Circular readout was missing despite the earlier restoration claim. Restored in Flutter, including the no-data case; it does not depend on hardware being powered. Current additions include measured trend panels and quality evidence. |
| Mobile map | `489:984` | Segmented station/evacuation tabs, prominent map frame, station legend and raised bottom SOS navigation | Restored tab framing, 360px map region, station picker/detail composition and observation legend. Actual Google map tiles remain dynamic. Purple means no current measurement; connectivity and quality remain separate facts. |
| Mobile SOS | `533:1894` | Dominant red circular action, supporting location/response/history cards | Restored the circular red action and three supporting cards. Activation opens consent/review, never sends directly. Receipt/outbox evidence stays visible. Original “Instant Dispatch” promises are replaced with truthful receipt/response wording. |
| Mobile alerts | `545:1994` | Severity-bordered cards and timestamp hierarchy | Adopted compact list cards with severity dot, lifecycle, transition time, station/area and latest depth. Resolved cards retain peak-tier, trigger and recovery labels. Full timelines remain on detail screens. No sample notices or invented unread counts. |
| Mobile settings | `94:1104` | Circular blue avatar, account card, grouped preferences, dividers, about/privacy cards and bottom navigation | Restored the circular solid-blue avatar. Current security, permissions and delivery controls remain functional additions within the account/preferences groups. |
| Web dashboard | `233:2` | Four statistics, left sidebar, large map, right alert/threshold panels and depth chart beneath the map | Existing composition retained. Current forecast/rain panels are later additions; source/quality/age remain visible. Real coordinates replace the design's illustrative Europe map. |
| Web stations | `423:31` | Two-column cards, severity badge, connection row, depth/rain metrics, trend and depth bar | Existing composition retained with missing-data and freshness states. Card density and evidence disclosure remain differences to review. |
| Web analytics | `431:390` | Stacked depth/rain charts, station comparison and flood-event report | Restored the rainfall panel and current station-comparison panel, with the selected event/range report beside it. Rainfall is explicitly a separate rolling journal window; CSV remains scoped to the selected database depth report. Missing/stale measurements cannot become current bars. Fixed numeric query parsing so the UI's aggregation options work. |
| Web health | `434:1561` | Summary cards, outage strip, channel table and affected-station detail | Retain composition, but water, rain, device heartbeat, broker and administrative state must remain independent. Original combined offline/active assumptions cannot be restored. |
| Web settings | `434:2513` | Account header, two-column profile facts, grouped preference rows and logout block | Composition retained. Theme selector and audited security/privacy tools are additional controls. |
| Web alerts | `425:30` | Active/historical tabs, search/filter strip and severity table | Original composition remains; current authority-notice panel and separate manual-test records preserve source boundaries. |
| Web SOS | `430:202` | Status filters, resident request table and attention cards | Composition remains; active cards only appear for actual active requests, not the Figma sample counts. |
| Web users | `433:1285` | Search/role filter, role totals and account table | Composition retained with authorized version-checked account mutations. |

## Boundaries of adoption

- Adopt layout, component shape, spacing, navy/blue palette and graphic hierarchy. Light mode is a corresponding theme; these original frames specify the dark baseline.
- Keep the user's later removal of redundant navigation. Do not reintroduce an extra profile/header shortcut, root-tab Back link or separate ML Evaluation sidebar entry simply because an old frame contains one.
- Preserve unknown/stale/invalid observations and real timestamps. A circular dial should remain present with an em dash when no measurement exists.
- Do not replace operational maps with the static Europe bitmap or restore example rainfall, forecasts, station counts, unread counts or hazard values.
- Preserve source identity, actual permissions, null handling, calibration/configuration, authorization, SOS receipts and conflict handling beneath the original visual layout.

## Evidence and limits

The circular restoration passed the full 242-test mobile suite and analyzer. Figma-follow-up map tabs/legend passed 26 targeted theme, freshness, SOS/map, dial and reflow checks and the analyzer. The newest APK was installed with `adb install -r`, launched and verified foregrounded on the USB Oppo CPH2269. `figma-phone-restored.png` shows the circular dial on the actual phone even with no measurement. A successful installation is not proof of physical map connectivity.

Web: 122 tests passed and the final production build succeeded. All 17 backend channel/report tests passed in the existing `.venv-auth` runtime. The core-only environment lacked paho for the independent rain test and the ML-only environment lacked SQLAlchemy; neither incomplete environment was reported as a passing suite. The isolated preview API was restarted against the same private database copy, with demo seeding, MQTT and external notification delivery disabled. The previously rejected explicit `bucket_seconds=60` request now loads successfully through the web proxy.

All eight command sections were opened in light and dark (16 recorded views). DOM checks found one selected navigation section per route, identical icon/label colors, and no main-content horizontal overflow at the inspected 1280px viewport; the health table has its own intentional horizontal scroll. `figma-web-live-checks.json` records these checks. Screenshot capture during rapid route changes can lag a frame, so sequential final Analytics screenshots and the explicit compact-health capture are the visual evidence, not every screenshot filename from the bulk navigation pass. This does not certify other widths, browsers or screen readers.

Reference screenshots are under `data/ui-preview-20261023/design-restoration/figma-bases/`. Rendered synthetic comparisons are under `figma-reference-mobile/`. The phone's data network was reported as captive portal/unvalidated when Google Maps failed. USB API forwarding does not supply internet for Google Maps. No network settings, certificate validation or provider restrictions were weakened.

This document deliberately does not claim every screen now matches Figma exactly. Current evidence controls and mobile settings details remain identified differences; no static sample map or example measurement has been restored as live data.

## Final adoption pass — 25 October 2026

Fresh Figma MCP reads reached the Starter-plan tool-call limit. This pass used the frames/screenshots and design exports already captured; it does not claim a new successful retrieval of every frame. The original design document was not modified.

Restored the remaining SOS circle/support-card composition, profile avatar and compact alert cards described above. Kept the original home dial, vertical gauge, map region, charts and navigation. Fixed large-text wrapping in the map legend. The SOS action preserves its accessible name and opens review; recorded receipt, consent, exact-payload retry and response distinctions are unchanged.

The actual resident browser was switched light → dark → light. That review exposed legacy unknown-reading gray text outside the shared token contract; it now resolves to the readable muted token in both themes and is included in the normal-text contrast regression. Rendered fixtures exercise both themes and 200% text; this is not a physical screen-reader certification.

The full mobile suite passed **242 tests**, including narrow/200% text layouts; the analyzer reported no issues. Rendered light/dark review images are in `final-adoption-mobile/`. The web suite passed **122 tests** and its production build succeeded. The responsive browser sweep covers eight command sections in both themes at 390px and 1280px and records one selected main-navigation item. It identified Users filter/role-card overflow at 390px and a clipped account table. Filters wrap, role cards stack at narrow widths, the table has a keyboard-focusable scrolling region, and the account dialog is constrained to the viewport. The rebuilt Users page was rechecked in light and dark: main content width and scroll width both 316px, table overflow `auto`, and dialog bounds inside the 390px viewport. See `final-web-responsive-checks.json` and `final-users-recheck.json` for measured evidence.

The updated resident browser preview loaded successfully, signed into the existing preview account, and displayed the circular depth dial with a true unknown reading. Home, SOS and Map were opened without submitting a request. Native map embedding is unavailable in this browser build; an explicit platform explanation now replaces the otherwise unexplained map icon, with station/shelter text details retained. This is not evidence of native Google Maps connectivity. Actual browser captures are `final-resident-home-browser.png` and `final-web-analytics-narrow.png`.

After the final map-fallback and unknown-text changes, the complete mobile suite again passed all 242 tests and the analyzer reported no issues. Both the development APK and debug browser build succeeded. The local previews are `http://127.0.0.1:3011/analytics` and `http://127.0.0.1:8095/`. Existing browser service-worker caches on the older 8080 origins continued serving earlier UI after ordinary reloads; 8095 is an isolated loopback preview origin for the final artifact. The API explicitly allows that local preview origin. The original development database was not replaced; the API uses the existing private preview copy with external notification delivery and device ingestion disabled.

The USB device was absent from `adb devices -l` during this pass. The newly built APK has not been installed/verified on the phone. Google Maps provider access on the phone, physical screen-reader checks and resident comprehension testing remain distinct acceptance work. The 48 previously staged paths were preserved; no files were staged, committed or pushed.
