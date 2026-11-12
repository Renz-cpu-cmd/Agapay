# UI consistency review — 24 October 2026

The visual baseline is the pre-audit AGAPAY design described in [UI-PRESERVATION.md](UI-PRESERVATION.md). This pass repairs its presentation and reflow; it does not replace the dashboard, charts, navigation, themes or resident home design.

## Confirmed problems and corrections

| Surface | Observed inconsistency | Correction |
| --- | --- | --- |
| App shell | Focusing/scrolling page content could scroll the hidden-overflow outer shell, moving the header and logo above the viewport. DOM inspection showed a nonzero shell scroll offset. | Clip outer-shell overflow; keep page content and sidebar as their own scroll regions. |
| Dashboard | Four fixed-height summary cards had insufficient room at intermediate widths. | Use two columns below 1100 px and allow card height to grow. Retain four columns on wider screens. |
| Shared pages | A legacy 837 px page minimum competed with narrow layouts. | Remove that minimum; let each page reflow within the original shell. |
| Settings | Account information and preference labels broke into very short fragments or individual letters. | Stack account fields and wrap preference controls at narrow widths, preserving original icons and settings rows. |
| Alert and health tables | Columns compressed into vertical letter fragments. | Preserve readable table widths inside horizontal scroll containers. |
| Health | Three narrow summary columns split labels midword. | Reflow into two columns on small screens; retain independent channel counts. |
| Station cards / map | The same observation, freshness, quality and source details appeared repeatedly in long paragraphs. | Keep compact independent observation, episode, heartbeat and latest-sample facts; retain full timestamps, reasons and provenance under Measurement evidence. Station navigation is an explicit button, separate from the disclosure. |
| Observation presentation | Missing depth could inherit a historical episode's severity color; a missing chart reading was described as last known. | Use observation color only for a current measurement, neutral missing/retained values, and No valid reading when no depth exists. Preserve the unresolved episode separately. |
| Forecast | Source text repeated No valid reading and other measurement facts. | Keep one concise input line and an expandable quality/timestamp record. No placeholder forecast values were added. |
| Notices | Empty pagination displayed 1–0. | Display 0 notices. |
| Themes | Dark was labelled Current theme even when light was selected, on both platforms. | Label the option Dark; the selected value identifies the active theme. |
| Station detail | Several borders used dark-only colors; gauge markers used a different fixed scale from the configured fill. | Use existing theme borders and the same station threshold scale for the markers and fill. Format thresholds numerically. |

## Verification and limits

- Web regression suite: 112 passing. The four-state measurement checks still require actual values or dashes, missing-data reasons, and original measurement timestamps.
- TypeScript check and production Webpack build completed successfully.
- Resident navigation tests: 2 passing. Resident theme tests: 7 passing, including theme persistence and map fallback behavior.
- Live narrow-browser review covers dashboard, stations, settings, alerts and system health. Screenshots and execution logs are in the ignored `data/ui-preview-20261023/design-restoration/ui-consistency-*` artifacts.
- The USB phone was not connected during this pass. The mobile label correction is source/test verified; installation and physical-screen verification remain outstanding.
- The subsequent [resident mobile consistency review](MOBILE-UI-CONSISTENCY-2026-10-24.md) adds rendered light/dark, narrow and 200% text checks across every tab and sensor detail, with its own corrections and final test evidence. Physical-phone verification remains separate.
- This pass does not establish a completed screen-reader, large-text, desktop/dark-theme visual matrix or resident/officer usability study. It also does not certify the application as operationally ready. Missing observations and unavailable approved forecasts intentionally remain unavailable.
- No account, telemetry, incident, outbox or original development database was reset. No commit or push was made.
