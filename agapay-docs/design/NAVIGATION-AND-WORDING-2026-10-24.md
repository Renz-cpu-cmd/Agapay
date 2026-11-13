# Navigation, wording and visual consistency — 24 October 2026

This follow-up implements the user's request to remove redundant navigation and the practice/simulation wording from the public interface while retaining the original visual design.

## Navigation

- Web has one ML Configuration sidebar entry. Configuration, Evaluation and Published forecasts are sibling tabs inside that workspace. Evaluation and published-product routes select their ML parent in the sidebar; direct links and staff authorization remain valid.
- Removed the extra ML Evaluation sidebar entry, ML header Back to dashboard shortcut, repeated model-review callout link, repeated forecast-workspace footer links and the Published forecast link in Settings.
- Mobile Profile remains in the bottom navigation; its duplicate home-header shortcut is removed. The home bell opens notification delivery history rather than duplicating the Alerts tab.
- Mobile primary Map and SOS tabs do not have an extra Home/back shortcut. Detail pages retain back navigation.
- Map evidence stays with each station. Removed the second selected-station evidence disclosure below the same list.
- Contextual actions such as viewing a station, opening a particular alert, inspecting forecast evidence and going to a shelter remain available; these carry a selected record or task context rather than adding another top-level destination.

## Public wording and presentation

- Navigation and action labels use SOS. Existing test-only response behavior remains disclosed as Test environment with no emergency dispatch or external notifications connected.
- Generated readings and previews use Synthetic data / Synthetic preview labels. Private assumed-basin work remains explicitly experimental; unavailable forecasts remain unavailable.
- Internal source enums, request practice flags, historical records, user-entered text and transport validation are unchanged. Renaming public labels does not activate operational dispatch, promote synthetic data to physical provenance or approve a model.
- ML page padding and card gaps use the same tokens as the other command pages. ML tabs wrap when needed; long artifact identifiers wrap within their cards. The preview selector uses the shared themed input.
- Account-only web pages display Signed in in a neutral color rather than a green Online label that could be confused with sensor/service readiness. Fresh observations retain their independent live-state presentation.

## Observed verification

- Web: 119 checks passed, including single ML sidebar entry, nested route selection, unique subpage links and officer/admin visibility. TypeScript check and production Webpack build passed.
- Mobile: 240 tests passed; analyzer reported No issues found; development Android APK built successfully. Includes actual Flutter widget renders for all resident tabs and sensor detail in light/dark at normal and 200% text, plus navigation behavior and data-provenance regressions.
- Rebuilt web preview was inspected through Configuration → Evaluation → Published forecasts and SOS. A fresh desktop preview showed one ML sidebar link, the correct parent selected and no horizontal page overflow at 1280 px. Mobile captures are synthetic-fixture renders, not phone/sensor evidence; native Maps is represented by its test fallback.
- Logs and screenshots are in ignored `data/ui-preview-20261023/design-restoration/navigation-wording-*` artifacts. Backups of the wording edits are in `wording-navigation-before/` alongside those artifacts.
- USB device inventory remained empty, so the new APK was not installed or physically checked on a phone. No original database reset, operational SOS submission, external notification, commit or push occurred. The pre-existing staged set remains 48 paths.
