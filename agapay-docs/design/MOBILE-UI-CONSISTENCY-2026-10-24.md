# Resident mobile UI consistency — 24 October 2026

This pass preserves the pre-audit resident design, navigation, gauge and visible home charts. See [UI-PRESERVATION.md](UI-PRESERVATION.md).

## Rendered review

Reviewed the actual Flutter widgets for Home, Map, Practice SOS, Alerts, Profile and sensor detail in light/dark themes at 390 px with normal text and 320 px with 200% text. Captured top, middle and bottom positions for the five tabs, plus sensor-detail views. The test harness supplies **synthetic service responses**; screenshots are layout evidence, not live station readings, physical sensor evidence or phone screenshots. Platform Maps is represented by its test fallback.

| Finding | Correction |
| --- | --- |
| Chart endpoints displayed long ISO timestamps that collided and wrapped into fragments. | Compact, labelled PHT endpoints; stack them at narrow widths/enlarged text. Exact UTC timestamps remain in the expandable data list. |
| Sensor detail began with a long provenance paragraph, placing the title and primary reading far below it. | Restore the heading and primary card first. Preserve full provenance in Source and measurement details, with observation and episode facts still visible on the card. |
| At 200% text, the side-by-side detail metric left the trend only a few pixels wide, creating a very tall column of letters. | Stack the metric and trend at enlarged text sizes. Check that the primary depth remains in the initial viewport. |
| Detail and map could use episode severity for an observed reading while Home used the observation tier. | Use the shared observed tier for the reading/marker; retain the unresolved episode separately. An unresolved higher episode remains in the action guidance. |
| A valid depth with a missing observation tier could be described as No valid measurement. | Show Observed water depth and disclose the unavailable tier. Do not infer a missing tier or fabricate a measurement. |
| First-contact and administrative states could be presented as Offline. | Preserve no_data, maintenance and inactive in the shared heartbeat view; API failure remains unconfirmed. |
| Map/alert filters lacked a consistent selected appearance, and large-text navigation colored every icon alike. | Shared selected filter styling and selected semantics; distinct selected/unselected large-text navigation. |
| Appearance/profile-locality labels could break into short fragments beside a fixed-width trailing value. | Place trailing controls below the label at enlarged text sizes; keep the original compact row at normal sizes. |
| Profile mixed inconsistent settings heading/icon styles and dense permission metadata. | Match the original heading/icon treatment; keep OS location permission and delivery capability visible, with detailed notification evidence expandable. Keep account security reachable within the account card. English-only operational content remains explicit. |
| Light-theme bottom navigation cast a heavy gray strip, avatar text inherited a dark color on a saturated background, and detail guidance used translucent white on a light card. | Use a lighter light-theme shadow, explicit white avatar text and the shared readable text color for guidance. |

## Verification

Execution logs and before/after captures are in the ignored `data/ui-preview-20261023/design-restoration/mobile-consistency-*` artifacts. Regression coverage includes retained measurement time, first-contact/admin connectivity, observed normal depth versus unresolved critical episode, valid depth with no tier, PHT date rollover, and every tab's narrow/large-text layout.

The final full Flutter suite passed **239 tests**; static analysis reported **No issues found**. The development APK build succeeded (`assembleDevelopmentDebug`, 73.8 s), producing `agapay-mobile/build/app/outputs/flutter-apk/app-development-debug.apk`. The build result is recorded in `mobile-consistency-apk.log`. No release-signing or physical-device claim follows from a development build.

## Remaining physical verification

ADB reported no connected USB device during this pass. The changes therefore require installation and a physical-phone check, including Maps, OS text scaling, TalkBack, keyboard/permission sheets, background/resume and actual offline/cache behavior. These rendered checks do not establish emergency usability, WCAG certification, physical notification receipt or operational readiness.

No original database reset, operational SOS submission, external notification, commit or push was performed.
