# F03/F04: ordered water observations and retained-message rejection

**Subsequent clock/source contract:** [F05/F06](../F05-F06/README.md) adds registry
source review and independent heartbeat/sample/retained-depth clocks. It changes
`last_ping` back to eligible receipt time while preserving the acquisition-time
ordering cursor and historical/replay exclusions described here.

Implemented locally on October 21, 2026, on top of [F01/F02](../F01-F02/README.md). This is a coordinated backend/publisher contract upgrade. Deployment and physical device testing have not been performed.

## Operational rule

HTTP and MQTT call the same ingestion transaction. A database write lock on the parent station serializes telemetry, boot registration, cursor updates, alerts, transitions and notification enqueue across workers. An ORM cursor is refreshed after waiting for the lock. A failed transaction rolls everything back.

Each water observation now includes:

| Field | Meaning |
|---|---|
| `schema_version` | Exactly `2` |
| `config_version` | Current admin-reviewed commissioning version |
| `source_id` | Exact commissioned `device_id`, checked against the authenticated station |
| `boot_id` | Stable identity for one boot/sequence session |
| `boot_sequence` | Durable, increasing boot ordinal, persisted before transmitting |
| `sequence_no` | Positive sequence within the boot; may restart in a new boot |
| `device_uptime_ms` | 64-bit monotonic uptime **at acquisition**, not receipt |
| `measured_at` | Acquisition UTC with a timezone, or explicit `null` when unsynchronized |

Water depth, rainfall, sensor quality and firmware version retain their existing types. The MQTT wrapper still contains `ingest_token` and `telemetry`; HTTP uses the separate station Bearer token. The rain counter/ACK protocol is unchanged.

A new operational observation must belong to the newest observed boot ordinal in its current configuration, have a synchronized measurement time within 120 seconds of receipt (at most 5 seconds ahead), and advance the last operational measurement time. Within the same boot, sequence **and** uptime must also strictly increase. The boot ordinal and ID are bound one to one. Once a newer boot is observed, a retired boot cannot become current again, even if it claims a later UTC time. Null timestamps do not receive a fabricated acquisition time. Clock rollback leaves samples historical until the clock advances beyond the cursor.

Sequence and uptime high-water marks advance even for unsynchronized/stale historical observations. A lower sequence cannot become current merely because it supplies a fresh-looking clock later. Newer configuration versions are possible only after reviewed commissioning and credential replacement. They permit a replacement device's boot ordinal to restart. Do not erase NVS to bypass the counter or automatically recommission a device after a conflict.

The database cursor selects `/api/telemetry/{station}/latest`. Monitoring depth, trend, freshness and forecast input use observations eligible for current state; late history cannot replace them. `last_ping` advances to the **measurement time**, never the reconnect/receipt time. Alert timestamps use measurement time. Forecast provenance is `device_measured`.

## Responses and history

- A new sample returns HTTP 201 with `eligible_for_current` and `disposition`. `current` means it was eligible when ingested; older qualifying history keeps that flag after a newer sample arrives.
- `late_measurement`, `out_of_order`, `retired_boot`, `stale_measurement`, `unsynchronized` and `pre_upgrade_measurement` remain immutable historical rows. They do not change the current cursor, station heartbeat/firmware, episodes, transitions or outbox. The public bounded history endpoint includes their metadata.
- Deduplication is `(station_id, config_version, boot_id, sequence_no)`. An identical retry returns 409 with `Duplicate telemetry: exact retry`; reuse with different measurement **or metadata** returns 409 with `Conflicting telemetry`. Boot ordinal/ID reuse also conflicts. MQTT logs those categories separately without raw bodies/tokens. Both duplicate/conflicting attempts consume the F01 ingress quota.
- `received_at` is always the actual server receipt time. For synchronized v2 observations, `recorded_at` equals `measured_at` for existing chart contracts. For unsynchronized/legacy history only, `recorded_at` is a receipt-based compatibility field; the explicit null `measured_at`, false eligibility and disposition identify that limitation.
- Missing v2 metadata, naive timestamps and out-of-range values fail validation. Wrong source/configuration fails authorization. Excessive future clock skew is rejected without a sample/boot write.
- Retained MQTT water **and rain** messages are discarded before parsing, authentication/quota, boot registration or persistence. This rejection was introduced with F01/F02 and is now covered explicitly at first subscription and reconnect. An unseen retained sequence cannot advance heartbeat, restore LIVE, or transition an alert. No retained message is acknowledged as a rain observation.

## Data-preserving SQLite upgrade

The existing SQLite inline uniqueness constraint must change to support sequence reuse after reboot. `create_all` cannot perform that change. Startup now fails with migration instructions when the old telemetry schema is detected.

1. Stop all backend/MQTT/test writers to the **intended** database. Confirm `AGAPAY_DATABASE_URL` and the selected environment; test/preview databases are separate targets.
2. Take and verify a SQLite backup, including any WAL contents using SQLite's backup API. Keep it with the previous application version for recovery.
3. From `agapay-backend`, use the configured backend Python environment:

   ```powershell
   python -m app.migrate_station_security
   # Apply F01/F02 first only if its four tables are absent:
   python -m app.migrate_station_security --apply
   python -m app.migrate_telemetry_ordering
   python -m app.migrate_telemetry_ordering --apply
   python -m app.migrate_telemetry_ordering
   ```

4. Install the updated publishers and reviewed source/configuration metadata, then restart the backend and verify current, late, duplicate and retained cases on a controlled station before operational use.

Without `--apply`, both commands inspect only. The ordering migration uses an exclusive transaction to copy/swap the telemetry table without renaming the original first. It preserves every legacy sample ID/value and all inbound alert/transition references, checks row counts and foreign keys, and recreates indexes. It refuses unexpected partial schemas, custom telemetry indexes/triggers and existing FK violations for manual review. This migration supports the project's SQLite database; a non-SQLite deployment needs a separately reviewed migration.

Old rows retain their old `recorded_at`, copied into `received_at`; they become `schema_version=1`, `disposition=legacy`, `measured_at=null`, and ineligible for current state. Existing stations, episodes, transitions, accounts and outbox rows are unchanged. No old data is replayed through alert processing. The first v2 observation must be newer than the preserved last receipt, preventing a delayed pre-upgrade observation from resolving an existing episode. Until a qualifying observation arrives, current monitoring may show no data; preserved active alert records remain available.

## Firmware and simulator installation

In the ignored `agapay-firmware/include/ingest_secrets.h`, keep the station token private and add the reviewed metadata from provisioning:

```cpp
constexpr char STATION_INGEST_TOKEN[] = "<one-time station token>";
#define AGAPAY_DEVICE_ID "<exact commissioned device_id>"
#define AGAPAY_CONFIG_VERSION 1 // replace with the actual commissioning version
```

Do not overwrite an existing secrets header with a template. Source/configuration missing from an older header causes water publication to be withheld. Local sensing/alarms and the rain protocol continue independently.

The ESP32 reuses its existing persisted sequence-block counter as the durable boot/session ordinal; its boot ID is `STATION_ID-ordinal`. The reporting queue carries that ordinal with each report. The sensor acquisition snapshot carries `esp_timer_get_time()/1000` uptime and UTC acquisition time. Nonblocking SNTP requests clock synchronization; before a valid UTC clock exists, it transmits `measured_at:null`, which the backend stores only as history. A report queued before synchronization is not retimestamped at publication. GPIO, calibration constants, local alarm tiers, rain NVS and ACK behavior are unchanged. SNTP/credential possession is not independent proof of physical sensor accuracy or trusted time; field validation remains separate.

The HTTP simulator requires an explicit boot ordinal for each run and a dedicated commissioned simulator identity:

```powershell
# Set AGAPAY_STATION_INGEST_TOKEN privately as described in F01/F02.
python simulator/simulate_http.py --station-id SIM_STATION --device-id SIM_DEVICE --config-version 1 --boot-sequence 1 --scenario rising
# Increment --boot-sequence for the next run; never share the physical station's identity.
```

The firmware still needs the separate production device TLS work identified in F27. Compilation/host tests do not establish broker/device delivery, NTP availability, physical calibration, or real-world emergency readiness. No live database migration, broker restart, credential installation, board upload or external notification was performed for this change.

See [verification results](RESULTS.md) for observed checks.
