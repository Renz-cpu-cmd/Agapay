# AGAPAY live rain-gauge demonstration — October 13, 2026

**Readiness: software implemented and tested; physical demonstration is not yet verified.**

## Main dashboard integration

The main web dashboard now uses authenticated `POST /api/hybrid-projections/{station_id}`
through the existing account proxy. Install `requirements-rain-demo.txt` in the
backend environment (the helper uses `.venv-auth`), then start the API and web.
The adapter verifies the archived CSV and JSON estimator hashes, reuses the
saved Random Forest and shared volume-balance code, and never retrains a model.

Open **ML Configuration** (`/ml-configuration`) from the sidebar, confirm the
controlled basin/proxy and click **Start ML demonstration**. This uses a manually
configured depth and the selected archived
24-hour ERA5 window, explicitly labeled historical-context demonstration. It
does not claim current weather or measured water depth.

For hardware, on ML Configuration select **Live rain gauge · automatic updates**, choose physical
source and measured ESP32 or manual initialization, and click **Start automatic
live projection** once. The panel polls without overlap every 750 ms after each
response. Accepted tips update basin inflow; duplicates do not compound depth.
A newer measured depth resets the anchor, excluding rain already reflected in
that observation. Missing/stale feeds clear the future depth values; fresh
completed 24-hour coverage is required before live hours replace archived ML
context. Simulated sources always retain a SIMULATED label.

The dashboard displays only the resulting trend, three horizon values, source
and last update. It has no basin or ML input controls. **ML Evaluation**
(`/ml-evaluation`) displays saved rainfall metrics and provenance. Shared
projection state preserves the fixed initialization and ongoing polling during
sidebar navigation. Reloading or closing the command-center session stops the
demonstration; initialize it again in ML Configuration. Settings changes clear
the old forecast immediately.

Selecting a station pin on the dashboard map now selects the water-depth trend,
forecast, rainfall activity and threshold tiers together. The forecast has no
separate station dropdown. The selected station is shared with ML Configuration
and preserved across sidebar navigation for the current command-center session.

Rainfall Activity fills the lower right column beside the forecast. It reads the
authenticated rain-gauge snapshot independently, displays recorded rainfall in
the ongoing hour only while the matching feed is fresh, and leaves unknown hours
blank. When the configured ML demonstration uses archived context, its actual
24 past hourly inputs can appear in a clearly labeled historical chart; they
never populate the current gauge total or prove physical connectivity.

`AGAPAY_HYBRID_PROJECTION_ENABLED` defaults to true but the endpoint additionally
requires development environment and staff authentication. The legacy station
forecast endpoint remains separate. Physical readiness checks below still apply.

The operator confirmed **0.70 mm/tip** in this chat on October 12. Canonical
firmware and backend configuration agree. No serial ports were visible in the
execution environment. Mosquitto was not found on PATH or either standard
Program Files location. No firmware upload, GPIO voltage measurement, physical
tip, broker/hardware trial, production database change, FCM send or video recording
was performed. Do not equate the software results with a successful physical demo.

## 1. Verify hardware before power or upload

Disconnect all power. Identify the actual three gauge terminals from module
labels/documentation and record their functions. Do not guess which terminal is
power, signal or ground from wire color. Determine whether the output is a dry
contact, open collector or powered logic signal. GPIO4 uses INPUT_PULLUP and a
falling-edge interrupt; only a compatible verified electrical interface may be
connected. Establish common ground where applicable.

Measure the gauge signal high/low voltage and transients at the GPIO junction.
The [ESP32 datasheet DC characteristics](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)
specify the allowed high-level input relative to its I/O supply, with a maximum
of VDD + 0.3 V; design for normal 3.3 V logic with margin. A direct unprotected
5 V signal is not acceptable. Use an appropriate verified interface/level
translation if needed. Firmware cannot measure or certify this wiring voltage.
Retain the earlier [cardboard runbook](live-cardboard-demo-runbook.md) checks for
JSN-SR04T ECHO protection, active-low buzzer driver, LED resistors and sensor datum.

If using cardboard instead of water, label ultrasonic depth as a **cardboard-derived
water-level proxy**. It is a sensing demonstration, not river calibration. For
the rain-driven projected response, a manual controlled-basin initialization is
often clearer than pretending a stationary cardboard surface is filling with water.

The per-tip volume and actual collector/basin areas must be measured if physical
volume accuracy is to be claimed. Existing hybrid defaults are explicitly assumed;
do not enlarge areas or suppress outflow to exaggerate a displayed change.

## 2. Prepare the local broker

Use [official Mosquitto](https://mosquitto.org/documentation/) if not installed.
The following commands are an operator procedure, **not commands already run on
physical infrastructure**. Use a private local demonstration network. The current
firmware uses plaintext MQTT; these are demonstration-only credentials, not real
account passwords. No public anonymous broker is used for physical station data.

In a PowerShell terminal at the repository root:

```powershell
$RainDemoRoot = Join-Path (Get-Location) 'data/live_rain/broker'
New-Item -ItemType Directory -Path $RainDemoRoot -Force | Out-Null
$RainMosquitto = 'C:/Program Files/mosquitto/mosquitto.exe'
$RainPasswordTool = 'C:/Program Files/mosquitto/mosquitto_passwd.exe'
if (-not (Test-Path -LiteralPath $RainMosquitto)) { throw 'Install Mosquitto or set its actual executable path.' }
$RainPasswordFile = Join-Path $RainDemoRoot 'passwd'
# Run -c ONLY when creating a new password file; it overwrites an existing file.
if (-not (Test-Path -LiteralPath $RainPasswordFile)) {
    & $RainPasswordTool -c $RainPasswordFile <mqtt-username>
} else {
    & $RainPasswordTool $RainPasswordFile <mqtt-username>
}
& $RainPasswordTool $RainPasswordFile backend-demo
```

Create `data/live_rain/broker/acl` with:

```text
user <mqtt-username>
topic write agapay/stations/STATION_001/telemetry
topic write agapay/stations/STATION_001/rain
topic read agapay/stations/STATION_001/rain-ack

user backend-demo
topic read agapay/stations/+/telemetry
topic read agapay/stations/+/rain
topic write agapay/stations/+/rain-ack
```

Create `data/live_rain/broker/mosquitto.conf`, substituting absolute paths and the
**currently verified laptop LAN IPv4 address**:

```text
listener 1883 REPLACE_WITH_LAPTOP_LAN_IP
allow_anonymous false
password_file REPLACE_WITH_ABSOLUTE_PASSWD_PATH
acl_file REPLACE_WITH_ABSOLUTE_ACL_PATH
```

Check `Get-NetIPAddress -AddressFamily IPv4` to identify the active adapter.
The ESP32 must use the laptop's reachable LAN address, not `localhost`. With a
broker bound specifically to that LAN IP, use the **same LAN IP** for the backend
BrokerHost argument. Permit only the necessary broker port on the verified
private demonstration network according to local policy; do not broadly disable
the firewall. Broker ACLs bind permitted publishers to the expected station topics.
The `data/` directory, including password files and journals, is ignored by Git.

Start the broker:

```powershell
& $RainMosquitto -c (Join-Path $RainDemoRoot 'mosquitto.conf') -v
```

See the [official configuration reference](https://mosquitto.org/man/mosquitto-conf-5.html)
for the installed version's password/ACL configuration. These classic directives
remain documented; newer releases also offer authentication plugins.

## 3. Start the isolated backend and dashboard

In a second PowerShell terminal at repository root:

```powershell
# Replace this with the LAN IP configured in the broker listener.
./agapay-backend/start-live-rain-demo.ps1 -BrokerHost REPLACE_WITH_LAPTOP_LAN_IP
```

The script prompts for the `backend-demo` MQTT credentials, enables rain events,
sets STATION_001 to 0.70 mm/tip, disables FCM, and uses:

- `data/live_rain/demo-api.sqlite3` — separate demonstration API database.
- `data/live_rain/rain-events.sqlite3` — durable rain journal, independent of
  operational telemetry tables. Do not erase this journal or firmware NVS to fix
  a counter mismatch; retain evidence and reconcile it manually.

The existing API creates its normal schema and seed station in the **separate**
demo database. No operational-schema migration was added by this implementation.
Keep it isolated from any earlier development notification outbox. No notification
worker is needed for this task.

In a third terminal:

```powershell
Set-Location agapay-web
$env:AGAPAY_API_URL = 'http://127.0.0.1:8000'
$env:AGAPAY_WEB_ORIGIN = 'http://127.0.0.1:3000'
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000/login`. Create the local demo administrator through
the existing local setup flow if this separate database has no account, then
sign in. The rain endpoint requires staff authorization. Open `/hybrid-demo`.
API and dashboard loopback access can remain on the laptop even though MQTT
must be reachable by the ESP32 over LAN.

## 4. Configure, build, and upload only after the physical checks

Edit only the locally ignored `agapay-firmware/include/secrets.h`: actual 2.4 GHz
Wi-Fi credentials, reachable laptop broker IP, port 1883, `<mqtt-username>` username
and its demo-only password. Never paste secrets into reports or commit the file.
Canonical source is `agapay-firmware/src/main.cpp`, GPIO4, 50 ms debounce,
0.70 mm/tip. Do not upload the old standalone example as the integrated firmware.

Build/upload/monitor commands, from repository root:

```powershell
& agapay-backend/.venv-ml/Scripts/python.exe -m platformio run -d agapay-firmware
# Operator: identify the actual port; substitute COM_PORT after wiring/safety checks.
& agapay-backend/.venv-ml/Scripts/python.exe -m platformio run -d agapay-firmware -t upload --upload-port COM_PORT
& agapay-backend/.venv-ml/Scripts/python.exe -m platformio device monitor -p COM_PORT -b 115200
```

The build command was verified; upload and physical monitor commands were not.
No NVS erase is needed. `[RAIN]` Serial lines show lifetime/boot counts and
persisted rainfall. `[RAIN MQTT]` distinguishes publication from backend ACK.
The counter is persisted outside the ISR before publication and survives normal
reboots. A sudden power cut in the small ISR-to-NVS commit window can still lose
uncommitted RAM tips; NVS failures explicitly warn and withhold new publication.
Flash endurance needs review before prolonged operational use.

## 5. Physical demonstration sequence

1. Power on the ESP32 after the unpowered wiring/voltage checks.
2. Confirm Wi-Fi and MQTT connection, backend subscriptions, rain snapshots and
   acknowledgements. Wait for a fresh baseline heartbeat before tipping.
3. On `/hybrid-demo`, select **LIVE RAIN-GAUGE DEMONSTRATION** and **PHYSICAL
   tipping-bucket gauge**. Enter the registered station ID.
4. Select an actual archived ERA5 origin for the preceding 24-hour ML context.
   With insufficient live history the panel says exactly **ML rainfall forecast:
   historical-context demonstration**. No future archived rainfall is used as
   measured live rainfall and no incomplete hour is inserted into an ML slot.
5. Set actual measured/estimated/assumed basin parameters. Choose **MEASURED —
   ESP32** or explicit **MANUAL** fallback depth, and confirm the controlled
   basin/cardboard-proxy scope.
6. Click **Connect automatic live feed** once. Baseline counts and all three
   projections should appear. No Generate button is needed in this mode.
7. Physically actuate one bucket tip. Check Serial, count +1, increment +0.700 mm,
   session/incomplete-hour totals and the new-reading indicator. The trajectory
   recalculates automatically. Display uses three decimal places without
   amplifying the physical calculation.
8. Repeat at least five tips. Count should increase exactly once per valid tip;
   no duplicate/bounce inflation should occur. In historical-context mode, the
   RF future rainfall input stays unchanged while live observed rain affects
   the controlled-basin state. It changes only if its valid input context changes.
9. For manual depth, every recalculation starts from the fixed initialization
   plus accepted rain since that time and elapsed outflow. For measured depth,
   newer valid observations reinitialize the state; earlier rain is not added
   again. Recovered outage rain with uncertain occurrence timing is retained in
   totals but excluded from automatic newer-depth initialization and hourly ML.
10. Disconnect/reconnect the network while watching local sensor outputs.
    Local sensing/LED/buzzer logic remains independent of network and predictions.
    Offline rain accumulates durably. Reconnect must recover the cumulative delta
    once; uncertain hourly timing is flagged instead of filled. Inspect any
    NVS/counter error instead of resetting away the evidence.
11. Verify existing local thresholds using the approved cardboard travel or
    controlled water test. No forecast output can independently trigger an alert.
12. Record a backup video with a phone showing physical bucket movement, Serial,
    live count and depth updates, source labels, and network-loss/local-output
    behavior. Keep the video offline. No such physical video was recorded here.

## 6. Event contract and timing semantics

Topic: `agapay/stations/{station_id}/rain`; ACK: same prefix plus `rain-ack`.
The [generated JSON Schema](rain-gauge-event.schema.json) matches FastAPI validation.
Fields are station ID, boot ID, packet sequence, lifetime cumulative tip count,
boot-start counter, acknowledged interval-start counter, mm/tip, reported interval
increment, uptime, last tip uptime, interval-start uptime, persisted-counter flag,
firmware version and source (`physical_rain_gauge` or `simulated_rain_gauge`).

The backend validates a registered active station, source/calibration, counter
and timing consistency; it commits the actual new cumulative delta before ACK.
Identical repeats are harmless, conflicting duplicates are rejected, retired
boots cannot become current again, and counter regressions require reconciliation.
Retained MQTT snapshots cannot establish live connectivity. No rain event enters
the operational alert/telemetry ingestion function.

There was no WebSocket infrastructure to reuse. The existing authenticated
dashboard polling mechanism is extended: a completed request schedules the next
poll after **750 ms**, with bounded requests and no overlapping polling. Source
and freshness are rechecked each time. New tips update the visual indicator,
counts, totals, curves and generation/target timestamps automatically.

Heartbeat is normally every five seconds; >30-second receive gaps make coverage
unknown. UTC completed-hour bins require real counter/heartbeat coverage around
the entire interval. Only 24 consecutive valid completed hours can activate
genuine current-data ML. Hourly timestamp is the interval end; incomplete-hour
and uncertain recovered accumulation remain separate. Last-tip UTC is estimated
from device uptime anchored to server reception; server receipt is authoritative
for the current ingestion ordering, not proof of a synchronized hardware clock.

## 7. Verification, measured latency, and fallback

Observed software results:

- ESP32 PlatformIO build passed: RAM 45,616 bytes (13.9%), flash 770,225 bytes (58.8%).
- Actual firmware host tests passed with fake GPIO/NVS/network: sensor/filtering,
  independent local outputs during disconnection, 50 ms debounce, interval reset,
  cumulative retention, persistence failure/recovery, ACK, reboot, and both JSON
  contracts. Six telemetry and two rain snapshots validated.
- Full backend suite: **231 passed**, including eight new rain tests. The final
  rain-only rerun passed all eight, and the retained-message rejection check passed.
- ML/history regression suite: **45 passed**; JavaScript suites: **nine passed**.
- Web typecheck and production Webpack build passed. Model artifact hashes and
  100-example sklearn/browser parity remain unchanged. No model was retrained.
- Browser test used an explicitly **SIMULATED** loopback feed and the actual
  rain journal/live projection UI. One 0.70 mm accepted event changed the modeled
  state from 20.000 to 21.120 cm using the existing assumed parameters. Missing
  ESP32 data visibly selected MANUAL fallback; subsequent events updated without
  clicking Generate.
- Recorded simulated events measured **135 ms, 607 ms and 598 ms backend-receipt-to-render**.
  This excludes real gauge debounce, ESP32 persistence, Wi-Fi and MQTT transport.
  These are three software samples, not physical tip-to-screen latency or an SLA.
  The panel and run JSON retain the measured scope and value.
- Physical tipping accuracy, signal voltage, actual device/MQTT transport,
  mounting datum, water-depth changes, ≤2.5-second physical latency and backup
  video are still unverified. Measure real latency using the physical video/trace;
  do not substitute these software numbers.

If the internet fails, a local broker/backend/web network can still deliver live
events; the model and archived context are already bundled. If the local hardware
network fails, switch to the verified historical replay/backtest or the explicit
simulator. The standalone HTML has no direct MQTT client and cannot receive
physical events by itself; its relative live API requests require the running,
authenticated AGAPAY web origin. Do not describe server-free HTML as a live feed.

Test-only MQTT publisher (enable `-AllowSimulator` only on the isolated demo API,
and select SIMULATED in the UI):

```powershell
# Backend terminal can launch with the deliberate test switch:
./agapay-backend/start-live-rain-demo.ps1 -BrokerHost REPLACE_WITH_LAPTOP_LAN_IP -AllowSimulator
# Separate test publisher terminal; supply demo broker credentials through local environment.
Set-Location agapay-backend
& .venv-ml/Scripts/python.exe -m app.ml.hybrid_demo.simulate_rain --host REPLACE_WITH_LAPTOP_LAN_IP --station STATION_001 --mm-per-tip 0.70 --tips 5 --spacing 2 --starting-count 0
```

The test publisher always labels its packets `simulated_rain_gauge`; it cannot
publish packets labeled physical. Fresh test sessions must not reuse or regress
an existing simulated lifetime counter. A fresh isolated journal/station is
appropriate for new test fixtures; otherwise pass the last accepted SIMULATED
lifetime counter through `--starting-count`. Supply the test publisher with
the `<mqtt-username>` broker username/password locally (that user has rain-topic write
permission); the `backend-demo` account is read-only on rain topics. Never erase
the physical journal to restart counts. Do not run this command as proof of
physical receipt.

Hardware-independent browser rehearsal harness:

```powershell
Set-Location agapay-backend
& .venv-ml/Scripts/python.exe -m app.ml.hybrid_demo.simulate_live_server --bundle ../data/demo/hybrid_rain_v01_20261012T003510Z_fdaff56583ad/index.html --port 8012
# Open http://127.0.0.1:8012; choose LIVE + SIMULATED, confirm scope, connect once.
# Separate terminal: explicitly inject one simulated event:
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8012/api/test-tip
```

This loopback harness uses a separate `SIMULATED-browser-*.sqlite3` journal and
contains no physical feed, operational database, safety writes or authentication
claims. It is a software test server (not literally server-free); the historical
HTML is the truly server-free fallback.

Exact verification commands used, from repository root unless stated:

```powershell
& agapay-backend/.venv-ml/Scripts/python.exe -m platformio run -d agapay-firmware
& agapay-backend/.venv-ml/Scripts/python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-backend/.venv-ml/Scripts/python.exe -m ziglang c++'
# From agapay-backend:
& .venv-auth/Scripts/python.exe -m pytest tests -q --basetemp .pytest_cache/rain-full --tb=short
& .venv-auth/Scripts/python.exe -m pytest tests/test_rain_gauge.py -q --basetemp .pytest_cache/rain-final --tb=short
& .venv-ml/Scripts/python.exe -m pytest app/ml/tests -q --basetemp .pytest_cache/rain-ml --tb=short
node --test app/ml/tests/live_rain_test.cjs app/ml/tests/hybrid_browser_test.cjs
& .venv-ml/Scripts/python.exe -m app.ml.hybrid_demo.verify_artifacts ../data/models/hybrid_rain_v01_20261012T003510Z_fdaff56583ad
& .venv-ml/Scripts/python.exe -m app.ml.hybrid_demo.build_demo ../data/models/hybrid_rain_v01_20261012T003510Z_fdaff56583ad --output ../agapay-web/public/hybrid-demo
# From agapay-web:
npm run typecheck
npm run build -- --webpack
```

Initial test errors in the rain-journal SQL insert and an account-test fixture
were fixed before the passing results above. No final test failures remain.
Temporary browser-test services are stopped after verification. No commit, push,
deployment, model retraining, NVS erase or physical upload was performed.

Files changed for this extension: firmware `src/main.cpp` and its three host-test
files; backend `app/config.py`, `app/main.py`, MQTT subscriber and `.env.example`;
new rain schema/store/router, eight backend rain tests, startup PowerShell script,
`requirements-rain-demo.txt`, firmware host-test dependencies and generated event
schema; hybrid HTML/builder/README plus new `live.js`, `live_ui.js`, test publisher,
simulated browser harness and live JavaScript tests; Next's existing authenticated
account proxy. Existing application telemetry schema, prediction contracts, model
artifacts, alert thresholds and notification provider were not changed.
