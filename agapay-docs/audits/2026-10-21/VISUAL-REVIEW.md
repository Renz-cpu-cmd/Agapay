# Current mobile visual review

October 21, 2026. These images were regenerated from the current source with the existing `test/theme_test.dart` widget fixture, `CAPTURE_THEME_PREVIEWS=true` and `--update-goldens`. Seven tests passed. They are synthetic test-fixture renders, not a connected phone, real sensor values or real map-service output. The source fixture deliberately uses a virtual station and warning values.

The live web and mobile browser sign-in pages were also viewed. Authenticated web dashboards and native phone screens were not visually traversed, so no broad visual sign-off is claimed for them. Older `build/previews/ml-*` images were not used as current evidence because those technical mobile pages were removed from the current resident journey.

## Home: light and dark

![Current mobile home, light theme, test fixture](/C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-docs/audits/2026-10-21/light-home.png)

![Current mobile home, dark theme, test fixture](/C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-docs/audits/2026-10-21/dark-home.png)

The themes provide consistent panels, spacing and navigation. The large depth value, visible severity and persistent SOS entry make the main concepts easy to locate. This is a usable visual foundation.

Changes recommended:

- Put selected area and station identity together. The screenshot's hardcoded San Vicente heading and fixture station identify different kinds of context without explaining the relationship.
- Make source/quality/freshness harder to miss than the small “VIRTUAL STATION” line. Exercise mode needs a persistent page-level banner and explicit entry; a failed feed must not activate example values.
- Separate observed hazard from official advice. “Flood water is rising” should be supported by valid rate evidence, and projected conditions should be visibly distinct.
- Reduce redundant threshold illustrations. The vertical gauge, large number and second threshold bar occupy much of the initial viewport, pushing trends and other useful actions down. Keep the number, one clear scale, observation age and next action; move secondary explanation to detail.
- Give the trend chart time labels, units and an accessible data alternative. A grid or isolated point alone does not communicate the time window or data gaps.
- Check the logo against both surfaces. In these fixture images it is visible in dark home but not discernible in the corresponding light-home logo area. Verify whether this is asset loading/rendering or contrast in the intended runtime before changing the asset.
- Measure contrast and large-text behavior instead of inferring accessibility from a screenshot. These captures do not demonstrate a specific WCAG violation.

## Profile: light

![Current mobile profile, light theme, test fixture](/C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-docs/audits/2026-10-21/light-profile.png)

The preference rows are legible and consistent. Their semantics need completion: Flood Alerts says it does not control delivery but has an active-looking switch; Location Services says Allowed without reporting the OS permission; Language implies whole-app translation; Barangay implies targeting that notification fanout does not implement. About/version labels remain dated. These are F11 and F18–F20 product-contract findings, not cosmetic fixes.

## Map fallback: light

![Current mobile map fallback, light theme, test fixture](/C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-docs/audits/2026-10-21/light-map.png)

The blank map with an icon is a fixture/runtime fallback; it does not establish a live Google Maps fault. A real unavailable-service view should explain the reason and retain a useful station/shelter list, last update, source/quality and relevant contacts. The selected station should consume the same aged monitoring state as home. The inspected map code currently keeps a separate request/store, so cross-screen consistency needs the F26 change.

## Required follow-up usability matrix

Test the actual authenticated products with residents and officers: first use, empty data, normal/critical observations, invalid sensor, stale water with fresh rain, API outage, GPS denied, Maps quota, forecast expiry, uncertain SOS send, concurrent officer action, dark/light, large text, keyboard, TalkBack and VoiceOver. Record task success and comprehension, not just visual preference. Repeat on the intended physical phones and their real permission/background settings before release.
