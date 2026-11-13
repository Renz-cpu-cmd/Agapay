# F05/F06: registry provenance and independent measurement freshness

Implemented locally on October 21, 2026, after [F01/F02](../F01-F02/README.md) and [F03/F04](../F03-F04/README.md). Source and client changes are reviewable; live activation has not been performed. See [verification results](RESULTS.md).

## Source authority and isolation

Firmware version is stored as software metadata. It no longer chooses whether a source is physical or simulated. Admin commissioning now records an immutable source designation for that commissioning version:

| Setting | Values / behavior |
|---|---|
| `source_class` | `physical_device`, `simulator`, `unverified` |
| `stream` | `operational` or `exercise` |
| `provenance_evidence` | Operator's review evidence; an explicit entry is required for physical designation |

Omitted settings default to **unverified / exercise**. Only a reviewed physical source may use the operational stream. A physical device used as an exercise/proxy can be assigned to the exercise stream; that does not authorize operational model initialization. Class or stream changes use the existing admin-only, version-checked commissioning operation and revoke previous credentials. Every version and its review evidence persist in `station_source_registry` and the commissioning audit.

The server takes credential identity from successful authentication, not from a body field. It validates station, active commissioning version, registry device ID, source ID, transport permission, credential expiry/revocation and stream under the station lock. Operational telemetry persists credential ID, authenticated ingress identity, transport, class, stream and registry version in `telemetry_provenance`. Tokens are never stored with observations. Public telemetry responses expose source metadata, not credential IDs or secrets.

An HTTP simulator registered as `simulator / exercise` cannot become physical by sending `1.0.0`, `physical`, or another firmware string. Adding source/trust/credential fields to the telemetry body fails validation. A registry-designated physical identity remains physical even if its firmware version contains `simulator`; that string is not evidence in either direction.

This is **registry-based provenance, not hardware attestation**. An administrator must actually review identity/evidence. Possession of a stolen physical-source credential can impersonate that source until revoked, including through an authorized transport. These changes do not prove secure boot, hardware keys, sensor wiring, accurate clocks, physical calibration, or emergency effectiveness. Device TLS and stronger hardware identity remain separate work. The cardboard setup remains a demonstration proxy and must not be silently classified as a validated operational flood station.

### Separate streams

| Channel | Operational | Exercise |
|---|---|---|
| HTTP water POST | `/api/telemetry` | `/api/exercises/telemetry` |
| HTTP water latest | `/api/telemetry/{station}/latest` | `/api/exercises/telemetry/{station}/latest` |
| HTTP water history | `/api/telemetry/{station}` | `/api/exercises/telemetry/{station}` |
| MQTT water | `agapay/stations/{station}/telemetry` | `agapay/exercises/stations/{station}/telemetry` |
| MQTT rain | `agapay/stations/{station}/rain` | `agapay/exercises/stations/{station}/rain` |
| MQTT rain ACK | `agapay/stations/{station}/rain-ack` | `agapay/exercises/stations/{station}/rain-ack` |

Both water POSTs use station Bearer authentication, the v2 measurement body and the shared station telemetry quota. MQTT keeps the authenticated envelope. Wrong namespace/registry stream returns 403 over HTTP or is dropped without rain ACK over MQTT. Retained and oversized messages remain rejected. Exercise telemetry is stored in a separate table with duplicate/conflict checks and read-only history. It has no operational telemetry row, cursor, boot watermark, station heartbeat, episode, transition or notification event. Exercise responses explicitly identify the stream and are never `eligible_for_current` or trusted for operational initialization. Read endpoints retain the existing public, bounded telemetry policy.

The HTTP water simulator now sends only to the exercise endpoint. The rain simulator uses only the exercise MQTT namespace. Operational dashboards/maps/reports read the operational monitoring endpoint; exercise data does not silently replace their observations. A dedicated exercise UI is not added by this change.

MQTT rain also checks its claimed rain class against the authenticated registry. Journal entries save ingress metadata in a new additive `ingress_provenance` table. Existing rain events remain unchanged and unverified; their labels are not retroactively upgraded into provenance. Rain counters, calibration values, gap rules and ACK fields retain their existing contracts. The broker ACL example includes the new exercise namespaces with the same station isolation and backend read/ACK-only policy; it has not been applied to a running broker.

## Monitoring clock contract

`GET /api/monitoring/stations` now distinguishes:

| Fields | Meaning |
|---|---|
| `heartbeat_at`, `heartbeat_age_seconds`, `heartbeat_fresh` | Receipt and age of the latest new, order-eligible operational sample, including invalid water samples |
| `latest_sample_at`, `latest_sample_age_seconds` | Acquisition time and age of the latest eligible sample |
| `sensor_quality` | Quality of that latest sample, not the retained depth |
| `last_valid_depth_at`, `depth_age_seconds` | Actual acquisition time and age of the retained last valid depth |
| `depth_fresh`, `depth_status` | `fresh`, `retained`, `stale` or `missing`; a newer invalid sample cannot make retained depth currently observed |
| `rainfall_observed_at`, `rainfall_age_seconds`, `rainfall_fresh` | Time/freshness of the rainfall interval in water telemetry, independent of ultrasonic quality; the durable rain journal is a separate channel |
| `source_class`, `source_trusted` | Latest sample's persisted registry provenance; legacy/missing provenance is unverified |
| `depth_source_class`, `depth_source_id`, `depth_source_trusted` | Retained depth's provenance; initialization trust requires the current commissioned identity/version |
| `hazard_state`, `active_hazard_tier`, `active_alert_id` | Whether a hazard is currently observed, remains unresolved, is absent or is unknown |

The last two valid observations are queried independently of chart history length. Invalid heartbeats cannot evict the retained valid depth just because `history_limit` is short. The chart still contains its requested recent eligible sample window, including invalid samples. The retained value can therefore legitimately predate every point in the displayed chart; its date and age remain explicit.

Compatibility aliases are deliberate: `observed_at` and `age_seconds` now refer to the retained valid depth, while `last_ping` refers to the eligible receipt heartbeat in monitoring and station metadata. This supersedes F03's intermediate measurement-time meaning of `last_ping`; the ordering cursor still uses acquisition time. `connection_status` / `is_online` use heartbeat freshness; `is_stale` describes a retained/stale depth. Consumers must not interpret `is_online` as proof of usable water measurements. Retained, late, unsynchronized and out-of-order historical traffic still cannot advance the operational heartbeat; this preserves F03/F04's replay boundary.

Example: a depth of 105 cm last valid one hour ago followed by a fresh invalid sample returns online heartbeat age 0, depth age 3600, the original valid-depth timestamp, `sensor_quality=invalid`, `depth_fresh=false`, and `hazard_state=unresolved` with the active EVACUATE tier. It does not report a newly measured 105 cm, resolve the episode, or disappear when the chart contains only invalid points.

Web station cards/details, dashboards, forecast displays, both map renderers and CSV reports use retained-depth dates/ages separately from heartbeat labels. Maps distinguish unavailable measurements from offline stations. Mobile home/details/maps/trend displays use the same fields; maps share the monitoring controller's current model instead of independently interpreting a raw response. Both clients age cached values from server check time and stop calling retained measurements current after expiry/errors.

Hybrid sensor initialization requires a trusted registry-designated physical source in the operational stream, a current commissioning binding, a fresh heartbeat, fresh valid depth, and the actual `last_valid_depth_at` within the freshness bound. It rejects simulator/unverified/legacy/exercise, stale and invalid data. The general forecast adapter also excludes rows without trusted operational physical provenance. Firmware text cannot satisfy either gate. No model was retrained or validated for real flooding by this task.

## Coordinated activation

1. Stop all intended backend writers and back up the intended database. Apply F01/F02 and F03/F04 prerequisites as documented there. This task has not applied any migration to live data.
2. From `agapay-backend`, with the intended `AGAPAY_DATABASE_URL` and configured Python environment:

   ```powershell
   python -m app.migrate_station_provenance
   python -m app.migrate_station_provenance --apply
   python -m app.migrate_station_provenance
   ```

   Default mode inspects only. `--apply` creates only the three missing provenance/exercise tables. It does not rewrite readings, accounts, alerts, outbox rows or source classes. It never trusts an existing identity automatically. Normal `create_all` can also create these additive tables; it cannot perform the earlier F03 uniqueness migration.

3. Review every source with an administrator. Recommission existing identities using the current `expected_version`, actual review evidence and intended class/stream. An example of the **additional fields** is:

   ```json
   {
     "source_class": "physical_device",
     "stream": "operational",
     "provenance_evidence": "Replace with the actual commissioning record and identity checks"
   }
   ```

   Include the existing device/calibration/datum/coordinate/state/reason fields required by the commissioning request. This example is not evidence; do not copy it as a physical verification claim. Simulators use `source_class=simulator, stream=exercise`. Unverified/default identities remain exercise-only. Missing registry designation denies operational writes until reviewed; it is not repaired from firmware text.

4. Issue replacement station credentials for the returned commissioning version. Update the publisher's configured device ID/version and install its token privately. Existing firmware uses the same v2 body; no new sensor or GPIO change is required for this backend classification. Deploy backend/web/mobile contracts together, configure the exercise broker namespace where needed, and verify on a controlled source before activating operational traffic.
5. Verify that changing a simulator's firmware string does not change its class; exercise traffic creates no operational rows/notifications; invalid heartbeats keep a stale retained value's age/date; and model initialization refuses that stale value.

Existing unprovenanced telemetry and active historical episodes are preserved. They are not relabeled physical or replayed into notifications. Staff must review historical hazards rather than treating an invalid/stale stream as recovery. Registry commissioning and software checks do not replace field validation.
