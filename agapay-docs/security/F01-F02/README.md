# F01/F02: station authentication and audited provisioning

**Source review update:** [F05/F06](../F05-F06/README.md) requires an admin-reviewed
source class/stream for operational ingestion. Old identities are not silently
promoted to physical; simulators use the separate exercise namespace.

**Subsequent contract update:** [F03/F04](../F03-F04/README.md) adds required
water boot/source/configuration and acquisition-time metadata, plus an explicit
SQLite preservation migration. Its v2 water contract supersedes the original
inner telemetry examples below. Rain events/ACKs retain the F01/F02 contract.

Implemented against the existing working tree on October 21, 2026. This changes the ingestion contract. An old unauthenticated firmware/simulator publisher will be rejected by the updated backend. Existing operational records are retained, and no existing station is automatically granted a credential.

## Behavior

- `POST /api/telemetry` requires `Authorization: Bearer <station-ingest-token>`. A staff/resident login session is never a station credential.
- HTTP and MQTT use the same station credential store, identity/version checks, expiry/revocation and per-station channel budgets. Credentials contain 256 bits of generated randomness; only SHA-256 hashes are stored. Tokens are returned once to the issuing administrator.
- Tokens are bound to one commissioned station/device record and may allow `http`, `mqtt` or `both`. A copied token cannot write another station. A stolen token can impersonate its assigned station until revoked: TLS, physical secret handling and broker ACLs remain necessary.
- MQTT uses an envelope: `{"ingest_token":"<token>","telemetry":{...original telemetry...}}` or `{"ingest_token":"<token>","rain":{...original rain event...}}`. The inner measurement contracts, rain counter behavior and ACK fields are unchanged. Tokens are never persisted with measurements or logged to Serial/backend logs.
- Naked legacy MQTT bodies, retained ingress, invalid/expired/revoked tokens and topic/payload/credential station mismatches are rejected. Rejected rain receives no ACK. Rain is journaled before ACK, while the station security lock prevents a concurrent revocation from overtaking an in-flight authorized write.
- Ingress bodies are capped before parsing: 4,096 bytes for HTTP telemetry/MQTT and 8,192 bytes for station administration, including HTTP streams without Content-Length. Default per-minute budgets are 120 telemetry attempts and 240 rain attempts per station; HTTP/MQTT and rotated credentials share these database-backed budgets. Exact duplicate attempts consume quota too. Fixed windows can permit a boundary burst; these budgets are not a substitute for unauthenticated IP/connection limits at the gateway/broker.
- Only active admin accounts can provision, commission, issue/revoke credentials or inspect provisioning/audit data. Officers, residents and device credentials cannot administer stations.
- New stations begin inactive/pending unless the administrator explicitly commissions them with verified coordinates, a named reference datum, a device ID, calibration notes and a reason. Commissioning is a recorded operator review, not proof of field accuracy. Do not mark unverified measurements as verified merely to enable a demo.
- Commissioning updates require the current `expected_version`. A conflict returns 409 for manual review. Every update revokes credentials for the previous configuration/binding. The administrative station status is distinct from this security gate: an already commissioned device's water observations can still report through maintenance, preserving the prior alert-history policy. Pending/decommissioned identities cannot ingest.
- Station creation/commissioning and their audit record are atomic. Audit details contain actor, reason, reviewed datum/calibration, device binding, thresholds, coordinates, activation and version. Credential audit entries contain metadata, not the token/hash.
- Public `GET /api/stations`, station detail and bounded latest/history telemetry endpoints remain public, read-only monitoring information. Account/SOS/device-credential/audit data remains protected. Changing that public-data policy is outside these two findings.

## New API operations

All operations below except the public monitoring GETs use a normal administrator login bearer session. Never send an admin session as an ingestion token.

| Method | Path | Body / result |
|---|---|---|
| POST | `/api/stations` | Existing station fields plus required `commissioning` object; creates station + identity + audit atomically |
| GET | `/api/stations/{id}/provisioning` | Current binding/configuration version; 404 means the existing station is not yet commissioned |
| POST | `/api/stations/{id}/commission` | Commissioning fields plus `expected_version`; use 0 only when no identity exists |
| POST | `/api/stations/{id}/credentials` | `expected_version`, `label`, `transport`, `reason`, optional `expires_at`; returns one-time `ingest_token` |
| GET | `/api/stations/{id}/credentials` | Up to 100 newest credential metadata rows; no token/hash |
| POST | `/api/stations/{id}/credentials/{credential_id}/revoke` | `reason`; idempotent revocation |
| GET | `/api/stations/{id}/audit?limit=50&offset=0` | Bounded administrative audit history |

Commissioning object:

```json
{
  "device_id": "REPLACE_WITH_DEVICE_REGISTRY_ID",
  "state": "pending",
  "coordinates_verified": false,
  "reference_datum": "REPLACE_WITH_REVIEWED_LOCAL_DATUM",
  "calibration_note": "REPLACE_WITH_EVIDENCE_OR_EXPLICIT_PENDING_DETAILS",
  "reason": "REPLACE_WITH_OPERATOR_REASON"
}
```

States are `pending`, `commissioned`, `decommissioned`. Device IDs must be unique. Commissioned state requires non-null station coordinates and `coordinates_verified=true`. Any state change invalidates prior credentials. An operator still has to verify the supplied statements; this is not automated surveying or calibration. No endpoint deletes past telemetry/alerts/SOS/outbox data.

When adopting an existing station or completing a pending one, the commission operation may include `latitude` and `longitude` together. Omit both to retain the current location. Reviewed coordinate updates are included in the version check and before/after audit; a pending station with no location does not require manual SQL or recreation to complete commissioning.

Credential issuance body example:

```json
{
  "expected_version": 1,
  "label": "Reviewed ESP32 publisher",
  "transport": "mqtt",
  "reason": "Initial device provisioning"
}
```

Default expiry is 30 days. An explicit ISO timestamp must be in the future and within 366 days. Store the returned token securely at issuance; it cannot be retrieved later. Rotate by issuing a replacement and revoking the old ID; recommissioning revokes all prior versions automatically. Creating a credential does not install it on a device or create a Mosquitto password.

## Data-preserving rollout

No live database migration, broker restart, station authorization, credential installation or firmware upload was performed automatically. Coordinate activation because enforcing the new protocol stops old publishers from being accepted.

1. Preserve the current database and rain journal using the normal backup process. Keep existing data; do not reseed or delete it.
2. From `agapay-backend`, with the environment for the intended database selected, run the check-only command:

   ```powershell
   & .venv-auth/Scripts/python.exe -m app.migrate_station_security
   ```

3. Review the selected database configuration without printing credentials. Apply the additive tables when ready:

   ```powershell
   & .venv-auth/Scripts/python.exe -m app.migrate_station_security --apply
   ```

   This creates only `station_identities`, `station_credentials`, `station_audit_events`, and `station_ingress_budgets`. It never changes old station columns/rows, seeds accounts or removes telemetry/outbox history. It is repeatable. Normal application initialization also creates missing tables, but the explicit command makes the intended rollout reviewable.

4. Restart the backend with the updated code in a coordinated service window. A deliberately preview-only server that bypasses normal startup must have the additive tables applied first. The existing isolated tests are not the live deployment.
5. Sign in as an existing administrator. Use the API operations to adopt existing stations (`expected_version=0` initially) or provision new ones. Record actual operator-reviewed metadata; use pending state when review is incomplete. Issue a separate credential for each device/transport.
6. Configure a per-station broker identity/password and the reviewed ACL described below. Install the station ingestion token in the ignored firmware header, then build and upload only as a separate explicit device operation. Do not erase NVS; preserve rain/sequence counters. Existing `secrets.h` is not overwritten by this change.
7. Confirm an authenticated sample reaches the intended station and that revoked/wrong-station credentials fail. Verify real device serial, broker and backend evidence separately. Check the rain ACK and cumulative counter after the coordinated restart. Do not infer field calibration or external notification receipt from a successful write.

The default firmware alarm-range issue F16 is unchanged. Local cardboard output profiles remain separate from actual depth thresholds and field warning validation.

## PowerShell admin session without echoing credentials

Use this against the intended local development API, or replace the base with the approved HTTPS deployment origin. This obtains a new administrator session; it does not create accounts. Do not paste token values into chat, logs, command-line arguments or source files.

```powershell
$stationApiBase = 'http://127.0.0.1:8000'
$stationAdminEmail = Read-Host 'Existing administrator email'
$stationAdminPassword = Read-Host 'Administrator password' -AsSecureString
$stationPlainPassword = [System.Net.NetworkCredential]::new('', $stationAdminPassword).Password
try {
    $stationLoginBody = @{ email=$stationAdminEmail; password=$stationPlainPassword; audience='web' } | ConvertTo-Json
    $stationAdminSession = Invoke-RestMethod -Uri "$stationApiBase/api/auth/login" -Method Post -ContentType 'application/json' -Body $stationLoginBody
    $stationAdminHeaders = @{ Authorization='Bearer ' + $stationAdminSession.access_token }
} finally {
    Remove-Variable stationPlainPassword,stationLoginBody -ErrorAction SilentlyContinue
}
# Supply the reviewed JSON objects from the API contract above in $stationBody.
# Example call pattern; do not print an issuance response containing a token:
# $stationResult = Invoke-RestMethod -Uri "$stationApiBase/api/stations" -Method Post -Headers $stationAdminHeaders -ContentType 'application/json' -Body ($stationBody | ConvertTo-Json -Depth 5)

# When all administration is finished, revoke only this new session:
# Invoke-RestMethod -Uri "$stationApiBase/api/auth/logout" -Method Post -Headers $stationAdminHeaders
# Remove-Variable stationAdminSession,stationAdminHeaders,stationAdminPassword -ErrorAction SilentlyContinue
```

## Device and simulator configuration

Firmware: copy `agapay-firmware/include/ingest_secrets.example.h` to ignored `ingest_secrets.h` only if it does not exist. Put the issued token for the matching `STATION_ID` there. The broker username/password stay in existing ignored `secrets.h`; the username must match the station ID for the provided ACL. Missing/malformed ingestion configuration withholds network publication while local sensing and durable rain counting continue. Nothing falls back to anonymous publication. Serial output no longer prints serialized telemetry envelopes.

The current firmware transport remains plaintext `WiFiClient`: use only controlled private development infrastructure for that profile. The new server refuses MQTT without broker credentials and requires TLS outside development. A certificate-validated device TLS profile is still deployment work under F27; this patch does not claim to complete it or expose a plaintext device listener publicly.

HTTP simulator: set `AGAPAY_STATION_INGEST_TOKEN` in the process environment using a secure prompt or an ignored protected configuration source. No `--token` argument is provided, to avoid exposing a token in process listings/history. Dry-run generation needs no token. A real send refuses missing tokens and refuses non-loopback cleartext HTTP. Example after the process has its token:

```powershell
# From agapay-backend. Use a credential with http/both transport for this station.
& .venv-auth/Scripts/python.exe simulator/simulate_http.py --station-id STATION_001 --scenario normal --count 4 --interval 2
```

The simulated rain publisher additionally needs station-scoped `AGAPAY_MQTT_USERNAME` / `AGAPAY_MQTT_PASSWORD`, `AGAPAY_STATION_INGEST_TOKEN` with mqtt/both scope, and TLS outside loopback. Simulated rain remains explicitly labeled and requires the backend's existing simulator opt-in; a token does not override that gate.

## Independent broker protection

Review `agapay-backend/deploy/mosquitto/station-ingest.acl` and `mosquitto.production.conf.example`. They are deployment inputs, not modifications to the running broker.

- `allow_anonymous false`; broker passwords are different from application ingestion tokens.
- Each device broker username equals its station ID. It may publish only its own telemetry/rain and read only its own rain ACK.
- The dedicated `backend-ingest` broker account reads telemetry/rain across stations and publishes only rain ACKs. If deployment uses a different backend username, explicitly adjust the ACL and backend settings together. Do not reuse a device account for the backend.
- Restrict listener reachability, use validated server certificates/TLS outside development, limit packets/queues/connections and protect password/private-key files. The example uses port 8883, not the live demo's ports.
- Broker password revocation/reload and application token revocation are independent. Revoke both after a device compromise. Application expiry/revocation is checked on every message, so an already-connected MQTT client cannot bypass it.
- Disable retained device publications. Broker SUBACK/CONNACK alone does not prove authorization or ingestion: exercise allowed and denied reads/writes and verify backend/journal state.

The optional test starts a separate temporary loopback Mosquitto with generated test-only passwords. It verifies anonymous/wrong-password rejection, station-topic isolation, ACK publisher isolation, and valid traffic. It never reads/reloads the actual broker or uses its ports/credentials. It skips when Mosquitto is not installed; CI should install Mosquitto to require this lane.

## Verification and remaining scope

See the adjacent test/build logs and `RESULTS.md` for the commands actually completed. Security tests exercise denial without telemetry/episode/outbox/heartbeat changes, credential hashing/redaction, explicit commission/conflicts/audit, shared durable quotas, body limits, HTTP/MQTT valid paths, rain ACKs, additive migration, and revalidation if expiry/revocation occurs between quota charging and ingestion.

These changes do not resolve delayed-sample ordering (F03), domain validation, physical calibration, official warning authority, geographic notification targeting, or other audit findings. Retained messages are rejected here because retaining authentication envelopes is unsafe; that also closes the retained-telemetry path noted in F04. No live device acceptance is claimed until the coordinated configuration and physical verification are performed.
