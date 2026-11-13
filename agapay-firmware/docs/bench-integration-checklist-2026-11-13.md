# Bench integration checklist: ESP32 to backend (2026-11-13)

**Status: prepared for review. Nothing in this checklist has been executed.**

This file contains no SSIDs, passwords, tokens, IP addresses or credential fingerprints.
Network names appear only as roles: "router" and "phone hotspot".

## Update: owner decision and hotspot diagnostics

**The owner chose the phone hotspot** as the temporary bench network. This replaces the router
recommendation in section 2A.

**Hotspot diagnostics** (2026-11-13, read-only):
- WPA2-Personal, 2.4 GHz, 802.11n, channel 11; signal 100% at the laptop.
- The ESP32 is associated, and the laptop resolved its MAC in ARP.
- Laptop to ESP32 ping: 10/10 and 5/5 replies, 71–272 ms. The latency is consistent with ESP32
  modem sleep.
- TCP from the laptop to closed ESP32 ports gets an active refusal from the device. **No client
  isolation.**
- **The hotspot subnet changed since 2026-10-13**, so `MQTT_HOST` in `secrets.h` is stale. Re-check
  the laptop's address immediately before the flash, and keep the hotspot on afterwards.
- Windows classifies this network as **Public**. Any inbound rule must apply to the Public profile,
  or the owner must reclassify the network.

**Credential exposure.**
- Neither the hotspot password nor the MQTT credentials appear in pushed history as an assigned
  credential.
- The hotspot password is a short, trivially guessable digit sequence that appears by coincidence
  in test IDs. Rotate it regardless.
- The hotspot's name and BSSID are in public docs. That is low sensitivity.

**Bench kit.** The kit is `data/bench-20261113/bench.py`. It is git-ignored, and every
credential-creating step is gated by `--approved`. It was validated end to end on a throwaway
loopback broker and DB:
- ACL tests: 18/18.
- Commissioning plus a credential gave one synthetic reading, persisted, with a `telemetry-ack` and
  a `not_trained` advisory forecast downlink.
- The 88 cm WARNING-level reading created zero alert, notification, SOS or dispatch rows.

## 1. Diagnosis (read-only)

The sources were:
- the post-flash serial capture of firmware 0.4.0 with OLED;
- the ignored local `secrets.h`, compared by length and equality only;
- this laptop's Wi-Fi state;
- the ignored demo broker config;
- the backend code at `87e6bb8`.

### Wi-Fi blocker

**The firmware is configured for the phone hotspot, and the hotspot is not broadcasting.**

| Evidence | Result |
|---|---|
| Configured SSID | The 6-byte phone-hotspot name, set on 2026-10-13 in the hotspot switch |
| Board scans: full, channel-11 active, channel-11 passive | The hotspot was **NOT SEEN** in any of them |
| Scan driver status | 0, with 5 APs found, so the radio and scanning work |
| Router (known BSSID) | Seen on channel 11 at **-74 dBm**, WPA/WPA2 mixed. The bytes differ from the configured SSID, so it is never adopted |
| Laptop | On the router (2.4 GHz, channel 11). It sees only that one network, not the hotspot |
| Result | `WL_DISCONNECTED`, retry every 10 s. Sensing, LEDs and buzzer continue offline |

This is not a radio, password or firmware defect. The board connected to the router on 2026-10-13
and to the hotspot later that day.

### Second network blocker: no broker reachable

Even with Wi-Fi working, MQTT would still fail.
- The firmware's `MQTT_HOST` is the laptop's old **hotspot-subnet** address. It is not on the
  laptop's current subnet.
- Only the stock Windows Mosquitto service is running, and it listens on loopback only. The
  AGAPAY demo broker (ignored `data/live_rain/broker`) is not running, and its LAN listener is
  bound to that old hotspot address.

### Provisioning blocker

`include/ingest_secrets.h` is absent. As designed, the dev build publishes nothing: it logs
`[INGEST AUTH] Station is not provisioned`. The firmware requires all of the following:
- `STATION_INGEST_TOKEN`: `agi_` followed by 43 URL-safe characters (47 in total), issued once by
  an administrator;
- `AGAPAY_DEVICE_ID`: 3–80 characters `[A-Za-z0-9_-]`, equal to the commissioned `device_id`;
- `AGAPAY_CONFIG_VERSION` ≥ 1, equal to the commissioning version.

### Why the existing demo environment can't simply be reused

| Item | Finding | Consequence |
|---|---|---|
| Demo DB `data/live_rain/demo-api.sqlite3` | Pre-commissioning schema: no station identities, credentials or recovery tables | Cannot issue credentials without a migration, which is **prohibited** on existing DBs. Leave it as preserved evidence |
| Demo broker ACL | Per-user explicit rules; no `forecast` or `telemetry-ack` topics | The OLED forecast downlink and telemetry ACK would be **denied** |
| Device broker username | Not equal to `STATION_001` | Repo ACL `deploy/mosquitto/station-ingest.acl` requires `username == station_id` (`%u`) |
| Accounts | Has a `backend-demo` account, no `backend-ingest` | The repo ACL grants the backend role only to `backend-ingest` |

### Contract requirements (code at `87e6bb8`)

**Topics.** The firmware uses these, with station ID `STATION_001` from `prototype_config.h`:
- publishes `agapay/stations/STATION_001/{telemetry,rain}`;
- subscribes to `.../{telemetry-ack,rain-ack,forecast}`.

**Stream.** These are **operational** topics. `ingress_provenance.trusted_ingress` accepts them only
when the source registry has `stream=operational` and `source_class=physical_device`. That needs
non-default `provenance_evidence` text. The firmware has no exercise-topic mode.

**Credential issuance** (`POST /api/stations/{id}/credentials`) requires:
- `state=commissioned`;
- station `active`;
- `coordinates_verified=true` with latitude and longitude;
- a matching `expected_version`.

For a bench unit, these coordinates must be the bench's actual, operator-checked location, with a
datum and calibration note that say "cardboard bench, not field-installed".

**Eligibility gate.** Resident push, the staff operational queue and dispatch require a
**`field_reviewed`** installation configuration (`operational_review_required=True`, the default).
- A bench station must stay `prototype` or `bench_reviewed`, which keeps it out of every
  resident-facing path, even on the operational stream.
- Never set `operational_review_required=false`, and never mark the bench config `field_reviewed`.

**Config hash.** A firmware `APPLIED_CONFIG_HASH` mismatch does **not** block ingest. It shows as
`mismatch` and blocks ML and incident verification. That is acceptable for the bench, as long as
the mismatch is shown honestly.

**Forecast downlink.** The downlink is not retained. The backend publishes a fresh message every
`forecast_downlink_seconds`. With no field-reviewed model, the message carries only `status` and
no numbers. That is the expected OLED result.

## 2. Sequential procedure

Each **[AUTH]** step needs separate written approval from the owner. Steps marked *[prep]* change
no hardware, live credentials or existing data.

### A. Credential rotation (prerequisite)

1. **[AUTH, owner action]** Choose the bench network.
   - **Router (recommended):** the laptop is already on it, and the board can see it. Its signal
     is weak (-74 dBm vs -60 on 10-13), so move the board closer.
   - **Phone hotspot:** the IP changes per session.
2. **[AUTH, owner action]** If that network's password is one of the values exposed in public
   commit `9b3f1f6`, change it on the router or phone **first**. Use a long passphrase; the
   current configured one is 8 characters.
3. **[prep]** Create new broker accounts only for the isolated bench broker:
   - `STATION_001`: the device account, required by `%u`;
   - `backend-ingest`.

   Use unique long passwords, stored only in ignored files. This also retires the old device
   account named in history, which is the MQTT rotation.

### B. Isolated bench backend

The bench backend sits in a new folder, for example `data/bench-20261113/`. It does not use
`agapay_dev.db` or the demo DB.

4. **[prep]** Bench broker: a new `mosquitto.conf` with:
   - `allow_anonymous false`;
   - a LAN listener bound to the laptop's **current** address on 1883 and loopback on 1884;
   - the repo ACL `deploy/mosquitto/station-ingest.acl`, copied unchanged.

   Start it on its own data directory, and leave the stock service alone.
5. **[AUTH, owner action]** Allow inbound TCP 1883 on the Windows Firewall *Private* profile,
   limited to the bench subnet. This is a system setting, so the owner makes the change.
6. **[prep]** Bench API: a **fresh, empty** database (new SQLite file or disposable PostgreSQL)
   created by the normal startup migrations. Settings:
   - `environment=development`;
   - `mqtt_enabled=true`, pointed at loopback 1884 as `backend-ingest`;
   - `notification_provider=disabled`;
   - `exercise_notifications_enabled=false`;
   - `operational_review_required=true`, the default;
   - `AGAPAY_DELIVERY_LEDGER_PATH` set to a new bench folder, then
     `python -m app.delivery_recovery initialize` on the empty DB.

   No Firebase credentials. A fresh bench admin account with a generated password, recorded only
   in an ignored local file.
7. **[AUTH]** Commission the station in the bench API:
   1. `POST /api/stations` for `STATION_001`, with `commissioning.state=commissioned`;
      `device_id` = a new bench device ID; `source_class=physical_device`; `stream=operational`.
      - `provenance_evidence` must be factual, for example: "Bench ESP32 (STA MAC observed on COM9
        serial 2026-11-13), cardboard rig, not field-installed".
      - Use the real bench coordinates with `coordinates_verified=true` only if they were actually
        checked.
   2. Optionally, `POST /configuration` with `validation_status=bench_reviewed`. **Never
      `field_reviewed`.**
8. **[AUTH] Issue the credential.** `POST /api/stations/STATION_001/credentials` with
   `transport=mqtt` and a short expiry (for example 7 days). The token is shown **once**. Write it
   straight into ignored `include/ingest_secrets.h` without displaying it. Set `AGAPAY_DEVICE_ID`
   and `AGAPAY_CONFIG_VERSION` to the commissioned values.

### C. Firmware configuration (one combined flash)

9. **[prep]** Update ignored `include/secrets.h` with the chosen SSID and the new password, the
   laptop's current LAN address as `MQTT_HOST` (port 1883), and `MQTT_USERNAME=STATION_001` with
   its new password.
   - Keep the dev build: no `AGAPAY_RELEASE_BUILD` and no `station_config.h`. Prototype geometry
     stays shown as prototype.
   - Build and run the host tests. Do not upload yet.
10. **[AUTH] Upload once.** A normal upload to COM9, the same as the last flash: no
    `erase_flash`, no partition change, and no formatting of the depth-history storage.
11. **Pre-flash check, so it isn't wasted:** from the laptop, confirm that `STATION_001`
    credentials can connect to the LAN listener and are denied on another station's topic
    (`tools/check_mqtt_connection.py` against the bench broker).

## 3. Pass criteria, in order

| # | Check | Pass when |
|---|---|---|
| 1 | Wi-Fi | Serial shows `[WIFI ASSOC] Link established`, `[WIFI DHCP] GOT_IP` and `[WIFI] Connected`, with RSSI better than about -70 dBm |
| 2 | Broker auth | `[MQTT] Connected state=0`. The broker log shows `STATION_001` connected, with no ACL denials on its own topics |
| 3 | ACL negative | `STATION_001` cannot publish to `agapay/stations/<other>/telemetry` or any `*-ack`/`forecast` topic. `backend-ingest` cannot publish telemetry |
| 4 | Provisioning | No `[INGEST AUTH] ... not provisioned` line. A telemetry publish is followed by a `telemetry-ack` the firmware logs as accepted |
| 5 | Persistence | The bench DB has telemetry rows with the same `sequence_no`, `boot_id` and `water_depth_cm` (±0.1) as the serial log, `source_class=physical_device`, `stream=operational`, and config status `missing`/`mismatch`/`matched` exactly as the firmware hash implies |
| 6 | Web | The bench Next.js dashboard shows the same latest depth and sequence time for STATION_001, labelled bench/prototype, not field-reviewed |
| 7 | Mobile | The Flutter app against the bench API shows the same value. Resident warning surfaces stay ineligible |
| 8 | No delivery | Zero notification or exercise delivery rows. The provider is disabled. The staff operational queue shows no resident alert from this station, even when depth crosses WARNING |
| 9 | Forecast downlink | The backend publishes `agapay/stations/STATION_001/forecast` with `advisory_only=true` and a non-`available` status. Within one downlink interval the OLED forecast page shows that reason, not "Offline". LEDs and buzzer are unaffected |
| 10 | Offline fallback | Stopping the bench broker shows MQTT disconnected and local alerts continue, then a clean reconnect |

## 4. Out of scope here

- Formatting the depth-history storage.
- Solar power.
- Field calibration.
- Any `field_reviewed` designation.
- Rewriting history to remove the exposed credentials.
