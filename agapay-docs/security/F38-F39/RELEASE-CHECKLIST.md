# Protected release checklist

## Android artifact preparation

1. Finish review and explicitly preserve the desired source in Git. Use a clean checkout of that exact full revision. Do not build a store artifact from an unreviewed dirty tree. This tooling does not stage, commit or push changes.
2. Establish ownership of the final application ID, HTTPS API origin, Firebase project, notification sender, Maps billing/quota and store account. Register each flavor's exact application ID. Preserve existing accounts/server records during app upgrades; development/staging application IDs intentionally have separate application storage.
3. Provision an upload key outside the repository using the organization's protected secret store. Record the intended upload certificate SHA-256 and recovery/rotation owners. Store signing material and symbols with restricted access and tested backup. Do not use an Android Debug certificate. Play App Signing may use a separate installed-app signing certificate; restrict Android providers against the appropriate actual certificate and application ID.
4. Supply secret environment variables: `AGAPAY_KEYSTORE_PATH` (absolute path), `AGAPAY_KEYSTORE_PASSWORD`, `AGAPAY_KEY_ALIAS`, `AGAPAY_KEY_PASSWORD`, `AGAPAY_UPLOAD_SIGNER_SHA256`. Inject them without command echo or persistent shell history. Flavor-specific `google-services.json` belongs under `android/app/src/staging/` or `production/`, never in source control. No service-account/private provider key belongs in the app.
5. Copy `tools/release-config.example.json` to an ignored, protected `release-config/` directory. Set the real environment, semantic version, previously unused increasing store build number, full committed revision, unique release ID and root HTTPS API origin. Build-number uniqueness must be enforced against the store/release register; structural validation cannot prove it. Leave maps `list_only` until hosted Maps acceptance is recorded.
6. From `agapay-mobile`, validate public configuration, then build to a new protected output directory:

```powershell
python tools/release.py --config release-config/staging.json --check
python tools/release.py --config release-config/staging.json --output release-output/staging-unique-id --flutter C:/flutter/bin/flutter.bat --format appbundle
```

For a directly measured ARM64 APK, use a different output directory and `--format apk`, with `AGAPAY_APKSIGNER` pointing to the reviewed SDK executable. APK mode requests Flutter's size analysis. The script does not upload or install anything. On non-Windows hosts, select that host's Flutter executable.

7. Review `release-manifest.json`, exact artifact SHA-256/size, expected signer, applied environment, configuration hash and excluded development assets. Retain the build log, dependency locks, toolchain versions, R8 mapping, split Dart symbols and available native symbols with the exact release ID. Upload matching symbols to the configured crash service/store separately; no crash service has been silently activated.
8. Verify the distributed installed artifact's certificate, application ID, version/build and displayed release identity. An upload-signed AAB alone does not prove the installed Play artifact's signer. Verify untrusted certificates, wrong API/environment, revoked login/session, Maps quota failure and denied permissions on the intended network.

## Physical Android acceptance record

Record device model, OS, release ID/artifact hash, tester, time, expected/observed result and linked evidence for each row. Status is PENDING until a real run is recorded.

| Gate | Required measurement/action | Status |
|---|---|---|
| Startup | Cold/warm launch p50/p95 over at least 20 launches on a representative low-memory phone; first useful unknown/cached state and first fresh value separately | Pending |
| Size/performance | AAB/APK bytes from manifest; Play download/install size separately; memory, scrolling/jank, network/battery in foreground/background on target hardware | Pending |
| Upgrade | Existing resident login/preferences/cache/SOS outbox survive supported signed upgrade; schema/account conflicts remain explicit | Pending |
| Permissions | Notifications allowed/denied/revoked, GPS denied/permanently denied/service off; honest status and fallback contacts/lists | Pending |
| Background | Suspend, kill, restart, airplane mode and reconnect; original cache age, no fabricated live state, no duplicate SOS | Pending |
| Push | Queued, provider accepted, app received, opened and acknowledged are separately evidenced on a controlled consenting phone | Pending |
| Crash symbols | Generate a controlled staging crash with no personal payload; symbolize using this release's Dart/R8/native symbols; verify redaction | Pending |
| Accessibility | TalkBack, large text, color independence, switch access, reduced motion and timed resident tasks from accessibility matrix | Pending |

Agree device-specific performance budgets before accepting a release. These suggested measurement procedures do not invent measured performance or approve emergency operation.

## iOS is a separate release gate

Windows does not validate Xcode signing, provisioning, entitlements, APNs or physical iOS behavior. Existing iOS project has no reviewed native environment schemes or APNs release provenance. Protected Dart startup requires a matching native flavor, so the unconfigured iOS release must not be presented as shippable.

On a controlled macOS builder, create reviewed development/staging/production schemes/configurations and bundle IDs, configure the correct Apple team and distribution profiles, per-environment Firebase configuration and APNs entitlement/provider credentials. Keep private keys in protected signing infrastructure. Validate ATS/HTTPS without development exceptions, archive dSYMs and split Dart symbols, verify the exported archive's signature/entitlements and TestFlight-installed build identity, then run the same permission/background/upgrade/offline/VoiceOver and controlled push matrix. Preserve a separate iOS evidence record. Android success cannot close these rows.

## Release approval and rollback

Retain the signed artifact, checksums, symbols, configuration and evidence as immutable release records. Production promotion uses the production origin/configuration and intended signing identity; changing environment requires a new build. Keep the previous compatible signed release, server compatibility window and supported rollback procedure. Never downgrade or erase resident storage to make an upgrade test pass. Store publication and real device rollout require the responsible organization's actual credentials and release review.
