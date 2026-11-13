# F38–F39: release controls and accessible operational presentation

Implemented locally on 2026-10-23. These findings remain open for the deployment/device and human acceptance evidence listed below. No keystore was generated, existing credentials changed, APK installed, store upload performed, or physical notification sent.

## Android release behavior

- `development` uses `.development`, `staging` uses `.staging`, and `production` uses the base application ID. Labels differ. Only development debug/profile and staging/production release variants exist.
- Release signing uses protected environment variables with an expected certificate SHA-256. There is no debug fallback. The native gate rejects missing/blank signing settings, Android Debug certificates, mismatched fingerprints, mixed native/Dart environments, insecure or local origins, missing provenance, missing Dart symbol settings, and absent flavor-specific Firebase configuration.
- Main Android manifest denies cleartext. Only development debug/profile overlays allow local HTTP. Dart startup independently validates protected configuration.
- Development configuration assets, including the Maps demo key, are flavor scoped. Resident exercise entry and forecast previews are unavailable in protected builds. The release archive inspector rejects development configuration assets and common private-key files.
- `agapay-mobile/tools/release.py` builds only from a clean, matching committed revision, supplies public build metadata, verifies the resulting upload signer, and archives hashes, byte sizes, Dart symbols, R8 mapping and available native symbols. No passwords enter public Dart defines or the manifest. CI builds only development and tests the rejection of unconfigured production signing.

Existing development Firebase configuration must be registered for the new `.development` application ID and supplied as the ignored `android/app/src/development/google-services.json`. Production and staging each require their own provider configuration. A generic root configuration does not activate protected push.

Read [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md) before creating a release. Public configuration examples intentionally contain invalid placeholders. The current dirty working tree is intentionally ineligible for a protected release; this change does not commit it automatically.

## Maps boundary

Protected builds default to `list_only`: station/shelter lists and contacts remain usable while the interactive map explicitly reports unavailable. A JavaScript Maps key bundled in a local WebView cannot be treated as an Android package-restricted native SDK key.

The optional `hosted` profile requires a reviewed HTTPS origin plus the SHA-256 of retained application/API-restriction evidence. That controlled page supplies its own HTTP-referrer/API-restricted browser key and implements the existing `window.agapayRender(config)` / `AgapayBridge` protocol from `assets/maps/agapay_map.html`. The app never passes its development key to that page and blocks cross-origin main-frame navigation. Deploying/reviewing that page, its CSP, quotas, privacy, restriction enforcement, malicious-origin rejection and route failures remains a real integration gate. Do not put resident access tokens in its URL or JavaScript. List-only is the deployable fallback until that integration is verified.

## Accessibility and hierarchy

Shared presentation tokens give unknown, stale, invalid, exercise and official states both words and distinct icons/colors. Official labeling does not establish an issuing authority; existing issuer/lifecycle contracts still apply. Shared mobile monitoring provenance is consistent across home, maps, detail and forecast. Published products and private experiments retain separate labels.

Mobile shared text has a 14 logical-pixel floor, with explicit metadata captions at least 12; controls use padded Material targets and larger home/back controls. Responsive wrapping replaces overflowing hazard/account rows, selected map controls have measured contrast, and reduced-motion disables SOS pulsing. Native text scaling remains enabled.

Charts use elapsed UTC measurement time rather than row index, reject missing/reordered time axes, leave invalid values and long gaps disconnected, label units/range/timestamps, and provide expandable timestamped text values. Chart display gap budgets are 30 seconds for water, one hour plus one second for completed rain hours, and 31 minutes for 30-minute modeled points. These are display continuity rules, not hazard/recovery policy or proof of data coverage. Valid zero remains a value. Unknown values remain explicit.

Web adds a skip link, visible focus, reduced-motion rules, readable compact labels, scrollable navigation, narrow-screen navigation and responsive content. The browser workflow uses loopback synthetic fixtures to check the published forecast record, outage, history, access boundaries, keyboard skip/dialog/focus return, narrow enlarged text and both-theme axe checks. Automated results cover the tested states, not blanket WCAG conformity.

See [ACCESSIBILITY-MATRIX.md](ACCESSIBILITY-MATRIX.md) for the remaining manual matrix and operational task hierarchy.

## Sources

- [Flutter Android release signing](https://docs.flutter.dev/deployment/android), [flavors](https://docs.flutter.dev/deployment/flavors), [obfuscation and symbols](https://docs.flutter.dev/deployment/obfuscate). Obfuscation does not protect embedded secrets.
- [Google Maps key restriction guidance](https://developers.google.com/maps/api-security-best-practices).
- [Flutter accessibility testing](https://docs.flutter.dev/ui/accessibility/accessibility-testing).
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) and [24×24 CSS-pixel AA target sizing, including exceptions](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum). Mobile practical control target is at least 48 logical pixels; a test matrix must assess effective hit areas rather than only visible glyph size.
