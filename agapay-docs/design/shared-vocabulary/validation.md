# Validation record — 23 October 2026

All browser identities, stations, readings, publications, receipts and review writes were synthetic fixtures. External provider requests were blocked. Mobile checks used Flutter unit/widget fixtures, not a physical device.

| Check | Observed result | Evidence |
|---|---|---|
| Web contracts/components | 112 tests passed | `../../vocabulary-web-tests.log` |
| Production web build | Passed, including TypeScript | `../../vocabulary-build.log` |
| Flutter analysis | No issues found | `../../vocabulary-mobile-analysis.log` |
| Full mobile unit/widget suite | 225 tests passed | `../../vocabulary-mobile-tests.log` |
| Shared presentation matrix | Passed, including zero/missing/invalid/stale/critical, missing rain, empty registry and retained API outage | `../../vocabulary-browser.log` |
| Staff evidence and concurrent actions | Passed; stale write remains blocked until manual review | `../../vocabulary-staff-browser.log` |
| Forecast/login/privacy regressions | Passed; expiry, withdrawal, outage, role boundaries, keyboard skip/dialog/focus return | `../../vocabulary-forecast-browser.log` |
| Published evidence and operations regressions | Passed; unknown delivery remains ambiguous and conflicting actions require refresh | `../../vocabulary-operations-browser.log` |

The four production browser workflows recorded **24 automated axe scans with zero violations**: shared state matrix 4, staff workspace 4, existing forecast/account flows 12, publication/operations workspace 4. These scans cover their fixture states, not every combination in the review matrix. The shared matrix captures both themes at 1440 px and at 320 px with a 200% root text size, reduced motion and accessible-tree evidence. The other workflows also exercise narrow/enlarged-text layouts. Browser text-size emulation is not a physical screen-reader or device-permission test.

The mobile suite includes 14 shared-state semantics cases (seven scenarios in both themes) at 320 px with a 2× text scaler, plus separate existing tab, chart, contrast and touch-target checks. It also verifies that an observed zero/NORMAL reading can coexist with an unresolved WARNING episode without borrowing its severity. Original measurement times, missing rain, invalid latest samples and API uncertainty remain independently described.

Issues found and corrected during review:

- Station cards retained two columns at narrow widths; they now reflow to one column, with wrapping connections and long severity labels.
- Critical severity text narrowly missed automated contrast checks against its dark badge background; dark text tokens now pass the inspected screens.
- API failure previously presented a physical device as offline on the web; connectivity now reads unconfirmed while retained measurements age.
- Mobile home used episode severity for the current reading during recovery; it now uses the observation tier and exposes the unresolved episode separately.
- Display strings such as Water level, Water-level forecast, LIVE and STALE READING were replaced at the presentation boundary with the shared vocabulary. Internal enum/state contracts remain unchanged.

Screenshots and semantic trees: `stations-light.png`, `stations-dark.png`, `stations-light-narrow.png`, `stations-dark-narrow.png` and matching `.aria.txt` files. The station-state axe data is `accessibility-results.json`; additional baseline results are `existing-workflows-a11y.json`. Staff/publication-console evidence remains in the neighboring design folders.

**Human evidence:** participant count 0; task times, comprehension/error rates and live NVDA/TalkBack/VoiceOver sessions remain unmeasured. `scenario-review.csv` marks those gaps explicitly. Use `comprehension-protocol.md` and `comprehension-results.csv` for actual sessions; do not treat this automated record as emergency-usability validation.

No staging, commits, pushes, live-database migrations, firmware flashing or external alert delivery were performed. The 48 pre-existing staged paths were preserved.
