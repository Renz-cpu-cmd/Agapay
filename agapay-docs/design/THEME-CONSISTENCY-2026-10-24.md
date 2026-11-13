# Theme consistency follow-up — 24 October 2026

This corrects observed defects; it does not certify every screen or emergency workflow as complete. Preserve the supplied design, original charts and existing data contracts.

## Confirmed defects corrected

- Sidebar SVGs carried their own blue/white paints and some carried 50% opacity. They did not follow selected or muted labels. Navigation now uses the original vector silhouettes as fully opaque masks with `currentColor`. Original exported assets remain intact; themeable copies live under `public/figma/website/monochrome`.
- Hover previously looked like selection. Hover and selected backgrounds now differ, with one active section and consistent icon/label color. Nested ML pages retain their ML parent selection.
- Dark adaptive tokens were only partially defined inside chart containers. ML tabs, callouts, parameter surfaces and other controls could resolve to inherited white/transparent. Both themes now define the shared palette globally; charts use the same tokens.
- Profile monochrome controls follow the current foreground, with branded raster imagery preserved.
- Analytics scope fields now share label spacing, aligned control rows and responsive columns. ML setup labels have consistent space beside wrapping values.
- Flutter light mode copied a dark `ThemeData`, retaining white native icons. A regression test reproduced the mismatch before the fix. Both themes are now built for their actual brightness with shared app geometry and explicit foregrounds.

## Verification

- Web tests: 122 passed; TypeScript production build succeeded.
- Mobile: 241 tests passed; analyzer found no issues; development debug APK built.
- Mobile regression checks selected and muted bottom-navigation colors across every resident tab through light → dark → light. Existing rendered reflow checks cover 390px and 320px/200% text in both themes.
- Live web checks recorded eight views through dark → light → dark → light on Dashboard, Settings, ML Configuration and Analytics. Each recorded view had one selected section, icon color equal to label color, and no horizontal main-content overflow at the inspected 1280px viewport. Dashboard map changed between Google Dark and Default. The original light preference was restored.
- Evidence: `data/ui-preview-20261023/design-restoration/theme-live-checks.json`, `theme-dashboard-light.png`, `theme-dashboard-dark.png`, `theme-ml-dark.png`, `theme-report-dark.png`, and synthetic renders under `theme-transition-mobile/`.
- USB Oppo CPH2269: `adb install -r` succeeded; API reverse tunnel configured; updated development app launched and was confirmed foregrounded. Screenshot `theme-phone-current.png` is physical-device evidence, distinct from synthetic widget renders. App data was not cleared. Physical-phone theme transitions have not been claimed as verified.

## Separate issues still observed

Follow-up: [Figma baseline review](FIGMA-BASELINE-REVIEW-2026-10-24.md) records the subsequent circular-dial/map restoration, successful USB installation, Analytics composition restoration and report-query fix. The query rejection listed below was resolved in that follow-up.

- Phone map: Google Maps JavaScript could not be downloaded; fallback station content remains visible.
- Phone: encrypted offline saving reports unavailable.
- Analytics preview: explicit `bucket_seconds=60` is rejected by the running API's numeric Literal query validation. This functional report issue is not a color or layout fix and remains open.
- The preview reports degraded live services and has no current verified water measurement. Missing values remain unavailable; no readings were invented for visual review.

No database reset, reseed, commit or push was performed. This review does not establish screen-reader or physical-device accessibility acceptance for all flows.
