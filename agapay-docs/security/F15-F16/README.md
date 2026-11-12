# F15/F16 — rainfall intervals and installation configuration

Local implementation, October 22, 2026. [Verification evidence](RESULTS.md) and the [physical acceptance record](PHYSICAL-ACCEPTANCE.md) distinguish software checks from measurements that remain pending. Existing data and prior staged work are preserved. No database migration, configuration activation, device upload or external notification was performed.

## Rainfall authority and envelope versions

Water telemetry **v3** adds `applied_config_hash`, `sensor_fault`, `local_alert_profile` and an optional explicit `rainfall_interval`. An interval has aware start/end timestamps, tip count, mm/tip, calibration hash, quality and source. It must be positive, at most one day and end no later than the water measurement time; its amount must equal tips × coefficient. When no interval is reported, `rainfall_mm` must be null. Firmware 0.3.0 sends null rainfall in its water envelope and publishes rainfall only through its durable cumulative counter stream.

V2 water envelopes remain accepted for compatibility until a reviewed installation is configured. Their historical raw rainfall numbers are retained, but have **undefined intervals**. Monitoring history emits null water-envelope rainfall, panels ignore it, and the generic prediction adapter supplies null rainfall with unknown interval. It does not sum publishing windows or cumulative snapshots into hourly features.

The independent rain envelope **v2** identifies its calibration/configuration hash and quality, alongside the existing boot/counter baselines and uptime interval. Legacy v1 rain records retain the explicit label `legacy-unversioned`; their payloads are not rewritten. Once a station has a reviewed configuration, MQTT rainfall must match its hash and per-station coefficient.

The durable rain journal reconciles against committed high-water counts, rather than summing overlapping ACK increments. Retries add no tips; reboot baselines add no fabricated rain; counter regression requires reconciliation. Recovered counts remain in durable totals but uncertain occurrence time prevents hourly allocation. A coefficient/version change breaks timing coverage and cannot reprice prior committed events. Session totals sum the recorded per-event amounts.

Journal products now include interval boundaries, source, quality, tip count, calibration version and coverage. Completed hours require continuous receive coverage and remain null when unknown. The current-hour product is **received tips during an incomplete UTC hour**, with explicit coverage gaps; its amount is not a complete hourly total or completed-hour ML feature. Receipt intervals do not establish exact tip occurrence during an outage. Web/mobile rainfall cards and measurement notes show these semantics. Independent rain freshness expires even if water traffic continues.

## Configuration, geometry and disagreement

Admin-only `POST /api/stations/{station_id}/configuration` records:

- An expected revision, datum, installation height, sensor range, uncertainty and range margin.
- Advisory/warning/critical thresholds and the station's rain coefficient.
- Fault policy, validation status, evidence, reviewer, reason and current effective time.

`GET` on the same route returns the configuration for authorized administrators. A stale expected revision returns 409 and requires manual review; no automatic overwrite occurs. Changes create immutable revisions and an audit event. Mathematical validation requires ordered thresholds, near-range margin at critical depth including uncertainty, and far-range margin at the zero-depth datum. It does not establish physical approval.

The canonical SHA-256 hash binds station ID, installation revision and all installation fields. It is distinct from the existing identity `config_version` used to authorize station credentials. The configuration applies immediately; historical or scheduled effective-time replacement is unsupported. The firmware header is installed through an explicit reviewed build, so local sensing and fault rules work offline without an API configuration fetch.

V3 samples with missing/wrong applied hashes are retained as `configuration_mismatch`; they cannot advance current telemetry, alert episodes or notification outbox. Once a reviewed installation exists, legacy v2 samples also lack the required matching hash. Cardboard local-output samples are retained as `exercise_local_outputs` and cannot clear an operational episode. Monitoring shows expected/reported hashes, revision, review state, sensor fault and local output profile. Web System Health and mobile home surface disagreement. Model initialization rejects an old configuration; historical reports count mismatched/exercise-output rows as review exclusions.

Mobile gauge labels, colors and scale now use the selected station's server thresholds/configuration. An absent threshold is not replaced by an operational default. ML Configuration and rain panels use the station coefficient, or an em dash when unknown. STATION_001's configured **0.70 mm/tip** remains an existing configuration value, not newly measured calibration evidence.

## Firmware default and fault behavior

The old 120 cm height / 100 cm critical / 20 cm minimum geometry has no range margin and is rejected by the new validator and firmware static checks. No critical threshold was lowered.

The checked-in fallback is explicitly **UNVALIDATED BENCH GEOMETRY**: height 150 cm, accepted range 20–450 cm, uncertainty 2 cm, margin 5 cm, unchanged 60/85/100 cm tiers, and 0.70 mm/tip for STATION_001. Critical depth corresponds to 50 cm distance, with 30 cm to the nominal near limit. These are prototype software parameters, not measured installation values. **This profile is not a drop-in update for a sensor mounted at 120 cm.** A deployment must use a reviewed header matching actual installation geometry. No currently flashed profile or physical mounting was established in this task.

The reviewed-policy candidate is `latch_hazard_signal_fault`. A blind-zone echo invalidates the complete burst even when other echoes look valid. Missing/invalid readings do not imply recovery. A fault turns green off and blinks yellow; an existing critical red/buzzer state remains latched. Temporary output self-tests cannot mask a fault. A subsequent valid acquisition restores measured outputs. The policy is provisional pending physical/operator review.

`cardboard_bench` remains a deliberately selected, separately reported output profile. Its distance zones are not flood thresholds. The new 150 cm bench geometry changes depth conversions; old presentation notes quoting 95 cm at 25 cm distance describe the archived 120 cm setup. Do not generalize a cardboard-derived water-level proxy or host GPIO test into real-water or emergency validation.

## Preservation migration and reviewed header export

Complete the F01–F14 prerequisites first. Stop application writers and back up the configured database. From `agapay-backend`, inspect, then explicitly apply when ready:

```powershell
.\.venv-auth\Scripts\python.exe -m app.migrate_interval_configuration
.\.venv-auth\Scripts\python.exe -m app.migrate_interval_configuration --apply
```

The SQLite preservation migration keeps telemetry IDs, existing raw rainfall, indexes and inbound references. It adds v3 metadata, makes rainfall nullable and creates the installation revision table. Unexpected partial schemas/custom triggers or indexes require review. It is idempotent and does not seed records. API startup fails clearly when an existing database needs this migration. New databases receive the schema through model metadata.

Submit a reviewed configuration using the admin API and save its response JSON. The [prototype example](prototype-configuration.json) documents software geometry only; it is not an activated station record or field approval. Render a new local header from the actual API response, from the repository root:

```powershell
agapay-backend/.venv-auth/Scripts/python.exe agapay-firmware/tools/render_station_config.py --input reviewed-station-response.json --output agapay-firmware/include/station_config.h
```

The renderer verifies the hash, refuses to overwrite an existing header and makes no network/database/device changes. Preserve and review an old header before choosing a replacement. `station_config.h` is ignored by Git. Keep the separate device credential/identity configuration in place; the installation hash does not replace authentication. Compile and conduct the recorded physical tests before an explicitly authorized upload and rollout.
