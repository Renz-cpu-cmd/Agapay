# F28/F29 verification — 2026-10-22

Software implemented; field and managed-database activation remain pending.

| Check | Observed result |
| --- | --- |
| Complete backend + ML regression, `python -m pytest -q --tb=short` | **554 passed, 1 skipped**; `backend-final.log`, exit 0 |
| Final ACK/proxy/security/lifecycle regression | **107 passed**; `backend-ack-proxy-final.log`, exit 0 |
| Final migration/restore-preservation/ACK/proxy checks | **19 passed**; `backend-final-smoke.log`, exit 0 |
| Existing development DB, consistent read-only source backup + copy-only upgrade | Every original row/value preserved; integrity and foreign-key checks passed; `database-copy-final.log` |
| Firmware host checks | Development, explicit bench, release and unprovisioned profiles passed; final observation-bound ACK checks in `firmware-host-release-final.log` |
| Expected release compile failures | Bench and unprovisioned release configurations rejected; `firmware-negative-release.log` |
| Actual ESP32 release compilation | **Passed**, final 0.4.0 source with synthetic credentials/CA; `firmware-release-ack-final-build.log`, exit 0 |
| Deployment template | YAML parsed; six service roles and explicit administration/delivery profiles checked; Docker/Compose not installed, no image deployment performed |
| Python source compilation / Git whitespace | Passed; original **48 staged paths** retained |

Test runs overlap and are not additive totals. The complete run preceded the final
ACK body binding and small restore/proxy hardening; their relevant focused checks
were rerun afterward. Earlier exploratory logs retain the obsolete rain-only ACK
assertion failures, which were corrected and verified in the passing final runs.
Logs are local ignored artifacts. Dependency deprecation warnings remain.

The copy upgrade preserved these original counts, along with every original value:

| Original table | Rows |
| --- | ---: |
| stations | 1 |
| telemetry | 131 |
| users | 6 |
| auth_sessions | 4 |
| sos_requests | 7 |
| administrator_setup | 1 |
| alerts | 3 |
| notification_devices | 2 |
| alert_transitions | 5 |
| notification_events | 3 |
| notification_deliveries | 4 |

The current verified private copy is
`development-final-contract-copy.db` in this directory. It is excluded from Git;
it contains personal/security data and must remain private. Other earlier draft
copies are not the current migration acceptance artifact. The original development
database was opened read-only and was not migrated or seeded.

Firmware checks cover restore after simulated reboot/outage, original boot/sequence
and JSON retention, bounded capacity and replay, corrupt and interrupted writes,
write/rename/delete failures, wrapped-slot ACK protection, full-observation mismatch
rejection and independent local GPIO behavior. Backend checks prove recent replay
cannot create live status or an alert/outbox, exact retry ACK follows a visible
commit, conflicting content gets no ACK, retained ingress is rejected and fresh
valid traffic can resume. The isolated TLS broker test verifies device ACK-read
scope, denial of device ACK publication, certificates and revoked credentials.
Proxy tests verify only the configured loopback peer can assert HTTPS.

The one skipped test requires a new, empty, isolated loopback PostgreSQL database.
No PostgreSQL/Docker runtime was available. PostgreSQL schema creation, actual
SQLite-to-PostgreSQL restoration, provider backup/PITR restoration, sequence handling,
table-lock behavior and concurrency still require real-engine acceptance. The
provided restore command rejects populated targets and unreviewed source tables,
uses a consistent source snapshot and an exclusive PostgreSQL table lock, and
verifies counts/fingerprints before committing application rows.

Before field claims, provision and verify a suitable LittleFS partition without
erasing existing NVS/data, then run actual device outage/reboot/brownout tests,
measure sensing latency during flash activity, drain rate, flash wear and power
use. The 10-second/360-observation policy is a configurable development default.
Per-boot gap counters and original timestamps do not prove lifetime completeness.
Existing station geometry/calibration acceptance remains separate.

No firmware upload, NVS erase, filesystem formatting, live database mutation,
broker reload, operational notification, deployment, staging, commit or push was
performed. Follow [README.md](README.md) for the explicit migration and rollout
sequence. Production startup deliberately refuses an unversioned/outdated schema;
the original development database still needs a separately executed upgrade when
the installation is deliberately activated.
