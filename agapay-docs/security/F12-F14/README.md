# F12–F14: channel health, measured-time rise and persisted reports

Implemented locally October 21–22, 2026. See [verification results](RESULTS.md). These changes extend the matching F01–F11 backend and client contracts; deploy them together.

## Independent health

`GET /api/monitoring/stations` includes independent `channel_health` entries for water sensor, rain counter, device heartbeat, broker ingestion and calibration. Administrative status remains a separate field. System Health counts maintenance/inactive stations separately from unexpected active-station outages; awaiting first data and unknown health are also separate.

Water health uses sample quality, review status, trusted provenance and measured-time freshness. Device heartbeat uses the latest water receipt or authenticated rain receipt and does not prove valid water measurement. Each retained value keeps its original observation time. The web ages each channel independently and changes fresh health to unknown on an API failure.

Rain health reads the independent rain journal in read-only mode and does not create a journal when none exists. It requires current commissioned identity, credential/provenance and matching configured mm/tip. Zero cumulative tips is a valid counter observation; it is distinct from unknown rainfall. Rain receipt freshness currently expires after 30 seconds. A counter heartbeat does not prove the tipping mechanism works. Water telemetry cannot refresh rain health.

Broker health records accepted operational MQTT receipts separately from HTTP traffic. Connection callbacks describe only the subscriber in this API process; this is not a broker-wide availability or ACL probe. Calibration shows configured values and commissioning documentation, with physical validation explicitly pending. Existing STATION_001 configuration remains 0.70 mm/tip.

## Measured-time rise

Web and mobile consume the backend rate in **cm/minute**, slope range, coverage and reason. Unknown timing/coverage produces unknown trend; no example rate or implicit stable label is substituted.

The estimator uses a five-minute window with at most 1,200 samples, cadence-adaptive median bins of 10–60 seconds, at least three bins spanning 30 seconds and at least 80% bin coverage. Invalid/reviewed observations, timing reversals, boot/source/configuration changes and gaps over 60 seconds break the usable segment. A stale latest measurement cannot supply a current rate. This query is independent of chart history length.

The rate is the median pairwise slope of bin medians. The displayed central 80% slope range describes slope dispersion, **not a calibrated confidence interval**. Provisional presentation boundaries are 0.5 cm/min for rise/fall and 4 cm/min for rapid rise. A range crossing classification boundaries produces unknown classification. These defaults need physical/domain validation; they do not modify the separate F09 alert escalation and recovery rules.

## Database report scope

Staff-only `GET /api/monitoring/history` accepts aware `start_at`/`end_at`, repeated `station_id`, optional `event_id`, `timezone` (`UTC` or `Asia/Manila`) and `bucket_seconds` (30/60/300/900/3600). A sensor event selects its persisted trigger/recovery interval, or the report cutoff for an unresolved episode. Explicit dates can narrow an event. Long episodes must be narrowed to the supported bounds.

Bounds are seven days, twenty stations, 20,000 station/bucket points and 100,000 measured rows. Exceeding a budget returns an error, never a partial success. Select fewer stations or a coarser bucket when necessary. Existing authorization governs station visibility; reports require admin/officer access.

Buckets are anchored at the selected start. The range includes both endpoints; only the final bucket includes its upper boundary. Samples are assigned by device measurement time. Synchronized late historical observations are included, while receipt-only unsynchronized legacy records are excluded and counted separately. The receipt cutoff is returned as `checked_at`. Reporting does not change current measurements or alert episodes.

Chart values are arithmetic means of valid registry-physical operational samples per bucket. Statistics retain exact minima/maxima and sample-weighted mean across qualifying database records. Invalid, reviewed and unverified counts remain explicit. Source metadata records authenticated class/identity/transport/registry version at capture; it is not independent hardware attestation. Coverage means buckets with qualifying samples divided by expected buckets, not proof of continuous measurement.

Analytics requires **Load report** for the selected station/range/event/timezone. Changing a filter invalidates the loaded report and export. Numeric timestamp keys align bucket intervals; unavailable intervals remain null and lines do not bridge them. Chart, statistics and CSV share exactly the loaded scope, including units, quality, source, coverage and event metadata. This is a **water-depth report**. Independent rainfall remains in Rainfall Activity; no rainfall total is inferred from the water stream.

## Existing database rollout

Complete the preservation migrations in the [F03/F04](../F03-F04/README.md), [F05/F06](../F05-F06/README.md) and [F09–F11](../F09-F11/README.md) guides first. Back up the configured database and schedule schema changes appropriately. From `agapay-backend`, inspect the measured-time history index:

```powershell
.\.venv-auth\Scripts\python.exe -m app.migrate_history_index
```

Apply the additive index explicitly when ready:

```powershell
.\.venv-auth\Scripts\python.exe -m app.migrate_history_index --apply
```

The migration checks prerequisites, is idempotent and changes only the index; it does not rewrite or seed telemetry. No live migration was performed during this task. New databases receive the index through model metadata. Live broker reconnects, physical rain-feed interruption, device/calibration validation and deployed web/mobile behavior remain separate rollout checks.
