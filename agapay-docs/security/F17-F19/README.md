# F17–F19: station operations, real preferences and English-only context

Implemented locally on October 22, 2026. No live database migration, device upload, external push or deployment is part of this change. Verification and remaining activation work are recorded in [RESULTS.md](RESULTS.md).

## Station lifecycle policy

| State | Water and rain ingestion | Observations and incidents | External sensor push | Local hardware alarms |
| --- | --- | --- | --- | --- |
| Pending commissioning | Rejected | Existing records remain visible | Suppressed | No remote alarm control is claimed |
| Active, commissioned | Authenticated station traffic accepted | Escalation and configured sustained recovery | Explicit subscriptions and account delivery preference apply | Applied device fail-safe configuration continues offline |
| Maintenance, commissioned | Authenticated station traffic accepted | Escalation remains immediate; recovery is held; existing incident remains unresolved | Suppressed, including explicit citywide sensor dispatch | Continues offline; maintenance is not a remote mute acknowledgement |
| Inactive | Rejected | Last observations retain their real timestamps; incidents remain unresolved | Suppressed | Server state cannot prove the physical unit is muted or disconnected |
| Decommissioned | Rejected; station credentials revoked | History and incidents preserved | Suppressed | Physical removal and local output verification remain operator work |

Lifecycle transitions invalidate earlier notification epochs and reset recovery persistence. Reactivation does not replay sensor events captured in maintenance or queued before a transition. New qualifying observations are required for subsequent operational transitions. A send already claimed and in flight cannot be recalled. Official notice publication remains a separately authorized authority workflow; these controls govern sensor escalation push, not a remote public-warning cancellation.

Staff can read `GET /api/stations/{id}/operations`. Only admins can `PATCH .../metadata` or `POST .../lifecycle`. Every write requires a reason and the displayed operations revision; lifecycle writes additionally require the identity version. Concurrent or stale writes return 409 and require manual refresh/review. No client automatically retries them. Changes create actor/reason/before/after audit records. Descriptive metadata cannot silently alter installation geometry, coordinates, calibration or thresholds. Commissioning and versioned installation/configuration endpoints retain their existing review, authentication and conflict requirements.

The web station detail exposes administrative controls and maintenance policy. System Health and mobile Home display lifecycle context separately from device/channel freshness. Existing raw measurements remain visible, including maintenance observations; operational model initialization remains unavailable for non-active stations.

## Persistent delivery and location preferences

`GET/PATCH /api/auth/preferences` stores account-owned delivery choice, English locale, optional verified resident-area ID and optional community language request. Writes use `expected_revision` and an account lock with authentication rechecked after acquiring it. A 409 never silently overwrites a newer account choice.

- Flood Alerts off disables **all AGAPAY sensor push**, including critical and citywide sensor notifications, on every registration for that account. There is no silent critical override. In-app observations and notices remain readable. Already in-flight sends may arrive.
- Turning delivery back on requires fresh device registration. Old queued deliveries retain their old registration revision and do not replay. Both event recipient capture and worker eligibility consult the account preference.
- An OS notification denial and an unavailable push build are displayed independently of the saved account choice. Querying permission does not itself prompt for permission.
- API session expiry remains separate from enabled push registration. Explicit logout unregisters that installation; deliberate account delivery-off disables every account registration. No replay of UNKNOWN provider results was added.
- Application location choice and selected station persist per account on the device using secure storage. OS location permission and device location service availability are read independently. Turning the app choice off stops practice-SOS location sharing and blocks GPS map/SOS entry points, including pending-location completion.
- Resume refreshes account preferences and OS capabilities. The UI exposes unavailable/error states and manual refresh. It does not label an in-memory location choice as OS permission.

## Language, geography and build information

The user's explicit policy is **English-only; Filipino translation unavailable**. Mobile uses an English ARB resource and generated localization delegates for critical hazard descriptions/actions and capability guidance. English is the only supported locale; the backend rejects `fil` or any unsupported locale. There is no partly translated emergency journey or fake language toggle. Web and mobile disclose translation unavailability. A saved community language request records interest without changing operational language or implying a reviewed translation.

Resident area uses an active geographic identifier from the existing verified registry. Application-only exercise areas cannot be selected as real geographic context. Descriptive profile locality, verified resident area and selected monitoring station are distinct. Selecting an area does not enroll notification subscriptions, alter a station jurisdiction or establish flood exposure. No new geographic code or authority was invented or activated.

Mobile version/build labels come from `package_info_plus`, using native package metadata or the generated web `version.json`. Unavailable metadata stays explicitly unavailable. Current release version is the repository's `pubspec.yaml` value, not a handwritten profile/login label. The hardcoded San Vicente home context and Urdaneta profile suffix are absent; station context comes from station metadata.

## Additive rollout

Apply the prior F01–F16 schema prerequisites first. Back up the configured database and stop writers before applying migrations. From `agapay-backend`, inspect first:

```powershell
.\.venv-auth\Scripts\python.exe -m app.migrate_operations_preferences
```

When ready to activate the coordinated backend/client release:

```powershell
.\.venv-auth\Scripts\python.exe -m app.migrate_operations_preferences --apply
```

The migration only creates `station_operations`, `station_delivery_gates` and `account_preferences`. It preserves stations, samples, incidents, credentials, subscriptions and registrations; it neither seeds nor resets data. It is idempotent. Legacy accounts initially preserve the existing enabled delivery behavior; devices still need eligible registration and explicit subscriptions. Legacy station status remains in place until an admin reviews it. Old delivery events without a gate are eligible only before any managed lifecycle epoch change; managed commissioning/lifecycle writes invalidate that legacy eligibility.

Deploy backend, web and mobile coherently; verify native permissions, restart persistence and notification-off/on behavior on the installed app with an explicitly authorized provider test. No software result supplies physical calibration evidence or resolves F16's pending physical geometry acceptance.
