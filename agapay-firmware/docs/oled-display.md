# SH1106 OLED display (1.3", 128x64, I2C)

**Wiring:** 1.3" SH1106 at I2C address `0x3C`, SDA on GPIO21, SCL on GPIO22, bus at 400 kHz.

**Builds:** enabled by `-DAGAPAY_OLED=1` in the development and cardboard-demo builds. Off in
`esp32-production` until it is reviewed for release.

The display is a **read-only view** of decisions the firmware already makes:
- It never classifies water itself and never changes the LEDs, buzzer, sampling or MQTT.
- It runs in its own low-priority task on core 0, beside the network task. I2C transfers
  therefore cannot preempt the ultrasonic `pulseIn` timing or the sensor loop on core 1.
- If the panel is missing or unplugged, only the display's I2C writes fail.

## Values: what the code actually uses (the draft spec was corrected where it differed)

| Item | Implemented value / behaviour | Source |
|---|---|---|
| Station ID | `STATION_001`, the configured ID. The draft value happens to match. | `include/prototype_config.h` (`CONFIGURED_STATION_ID`) |
| Depth tiers | ADVISORY ≥ 60, WARNING ≥ 85, EVACUATE ≥ 100 cm **water depth**, where depth = 150 cm mounting datum − measured distance | `classifyAlert()`; values generated from the backend station configuration |
| Hysteresis | **None on the device.** The local tier changes on the next valid sample. The backend adds 2 cm hysteresis and 3-sample / 10 s recovery for *its own* alerts, so backend and OLED tiers can briefly differ. The OLED shows the **local** tier, the one driving the LEDs and buzzer. | `classifyAlert()`, `app/services/hazard_policy.py` |
| Cardboard demo | Tiers come from **raw distance** (≤ 60 / ≤ 35 / ≤ 25 cm), not depth. The OLED labels this `DEMO` / `DISTANCE (DEMO)` and shows the distance. | `classifyBenchAlert()` |
| Blind zone | Readings under 20 cm, or over 450 cm, are rejected (`blind_zone` / `out_of_range`) | `MIN_DISTANCE_CM`, `MAX_DISTANCE_CM` |
| Geometry | The 150 cm datum is **unvalidated bench geometry**. The health page shows `BENCH` until a reviewed `station_config.h` is used. | `prototype_config.h` |
| Rain | 0.70 mm per tip, confirmed by the operator on 2026-10-12. A durable lifetime counter is kept in NVS, plus a since-boot count. No 24 h total exists, so none is shown. | `RAIN_MM_PER_TIP`, `restoreRainCounter()` |
| Rain rate | Shown as mm/h **only after a full 60 minutes have been observed** this boot. Before that it reads "in N m". It is the real tip count over the last hour, not an extrapolation. | `oled::RainWindow` |
| Network | Wi-Fi state and RSSI, MQTT session state and IP, all from the network task that owns those clients | `networkTask()` |
| Battery | **No battery measurement hardware or ADC input exists**, so no battery value is shown | GPIO map |

## Pages

Six pages advance every 5 s. The header shows the page title, Wi-Fi bars (a slash means down), `M`
for MQTT (a slash means down) and `n/5`. A hairline under the header shows time to the next page.

1. **Dashboard:** water depth (large), rain since boot, and the alert strip.
2. **Rainfall:** since-boot mm and tips; last-60-minute mm/h once valid; time since the last tip;
   mm per tip; lifetime tips.
3. **Flood alert:** the tier, the measured level, a short action line, and the configured
   thresholds.
4. **Forecast (advisory):** predicted depth at +30, +60 and +90 min with its range, and how
   recently it was updated. See "Advisory forecast" below.
5. **Network:** Wi-Fi with RSSI, MQTT, station ID, IP, and whether alarms are running offline.
6. **Health:** sonar state and raw distance, last valid reading, rain-counter persistence,
   uptime, firmware, config revision and datum.

Mockups were rendered on the PC by the **real** renderer (`python tools/oled_preview.py`) and
are stored in [`oled-mockups/`](oled-mockups/), with an overview in
[`contact-sheet.png`](oled-mockups/contact-sheet.png).

```
 ________________________________        ________________________________
|AGAPAY            .ıl M     1/5 |      |███████  EVACUATE  ████████████|
|WATER LEVEL          | RAIN     |      |████████████████████████████████|
| 72.4 cm             | 8.4      |      |           103.2 cm             |
|                     | mm boot  |      |    Follow evacuation orders    |
|[ ===== ADVISORY ======= ]      |      |    Red LED + buzzer active     |
 --------------------------------        --------------------------------
```

## Emergency, sensor-error and fallback rules

| Situation | Display | Never |
|---|---|---|
| Local tier `EVACUATE` | Full-screen override, ending paging: a 1 Hz band, the level, "Follow evacuation orders" | Normal paging |
| A sensor fault after `EVACUATE` (the firmware keeps red + buzzer latched) | Override stays. `SENSOR ERROR`, "Last 103.2 cm, 14s ago" | Showing the old level as current |
| Latest sample invalid (`no_echo`, `blind_zone`, `out_of_range`, `insufficient_echoes`) | `SENSOR ERROR` in a dotted strip, a reason tag (`NO ECHO`, `TOO CLOSE`, `OUT OF RANGE`, `WEAK ECHO`) and `-- cm` | `NORMAL`, or a number |
| No sample completed yet since boot | `NO DATA YET` and `-- cm` | `NORMAL` |
| No new sample for more than 5 s (sampling stopped) | `DATA STALE` and `-- cm` | The last value shown as current |
| Wi-Fi or MQTT down | Slashed icons and `Offline: local alarms OK`. Pages and alarms keep running. | Hiding the local reading |
| Rain NVS persistence failing | `mm !NVS` on the dashboard; `! COUNT NOT SAVED (NVS)` on the rain page | Presenting the count as durable |
| Serial `ALERT TEST` | The header reads `OUTPUT TEST` | |

Visual language: an outline strip means calm, a double outline means ADVISORY, a filled strip
means act now (WARNING / EVACUATE), and a dotted strip means there is no trustworthy reading.

## Advisory forecast (page 4)

**Source.** The backend's MQTT owner publishes `agapay/stations/<id>/forecast` every 30 s
(`forecast_downlink_seconds`). It uses QoS 1 and is **not retained**, so a reconnecting device
never receives an old copy. The message is a compact copy of `/api/predictions/<id>`, built by
the same `forecast_registry.read_latest`, so every deployment, review, identity, clock and
expiry gate stays in one place. The broker ACL lets each station read only its own forecast
topic; only `backend-ingest` may write it.

**Message (schema v1):**

```json
{"v":1,"station_id":"STATION_001","status":"available","advisory_only":true,
 "published_at":1767400000,"generated_at":1767399980,"valid_until":1767400120,"ttl_s":120,
 "config":"<applied configuration hash>","model":"<16-char id>",
 "points":[[30,83.0,79.0,88.0],[60,86.0,82.0,91.0],[90,89.0,85.0,94.0]]}
```

Every other status (`not_trained`, `unavailable`, `insufficient_data`, `stale_data`,
`invalid_data`, `service_error`) carries **no numbers**. The backend also downgrades any
available forecast that is unbounded, unbound to a configuration, or already expired.

**The device shows numbers only when all of these hold** (`include/forecast_message.h`,
host-tested):
- it is the right station, schema v1 and `advisory_only`;
- the configuration hash equals the firmware's `APPLIED_CONFIG_HASH`, so it was computed
  against the same datum and thresholds;
- the horizons are 30/60/90 in ascending order, and every value is finite, between 0 and
  1000 cm, and inside its own range;
- `ttl_s` is no more than 2 h and fits within `valid_until`;
- with a synchronized clock, it is not expired, and it is not dated more than 5 minutes ahead.

The numbers disappear when the TTL runs out (measured on the device's own uptime).

| Situation | Page shows |
|---|---|
| Fresh, valid forecast | "+30 min 83 cm (79-88)" for each horizon, `ADVISORY updated 12s ago` |
| Server says not available | `No forecast`, plus the reason (for example "Model not trained") and its age |
| Expired | `Forecast expired`, waiting for an update, with no numbers |
| Wrong station config, bad, future-dated or expired message | `Forecast rejected` with the reason, and no numbers |
| Nothing received yet | `No forecast yet`, either waiting for the server or offline |

Every state also shows "Alarms follow sensor only". The forecast **never** changes the local
tier, LEDs, buzzer, telemetry or the EVACUATE override.

**Today:** the backend only makes a forecast `available` for a `field_reviewed` station
configuration with a reviewed, deployed model. The current bench configuration is neither, so
the page will normally say `No forecast` / "Model not trained" or "Not published" until a model
is reviewed and deployed.

## Build and check (no upload)

```
python -m platformio run -e esp32doit-devkit-v1
python tools/oled_preview.py --u8g2 <U8g2 Arduino library> --cxx "python -m ziglang c++" --cc "python -m ziglang cc"
```

`oled_preview.py` also runs `tests/oled_model_test.cpp`: the display-state host tests.

## Before relying on it operationally

- Measure the true mounting height above the depth datum and confirm the 20 cm blind zone stays
  clear at the evacuate level. 150 − 100 = 50 cm, which leaves 23 cm of margin with the current
  bench values.
- Confirm the delivered volume per rain-gauge tip.
- Replace `prototype_config.h` with a reviewed `station_config.h`; the `BENCH` tag then
  disappears.
