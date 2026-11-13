# AGAPAY dry cardboard-target demonstration

Prepared 2026-10-12 for `feature/day1-foundation`, HEAD
`67f85e0a0db2e1d90b456b43d06e324b211b7669`.

**Current verdict: NO-GO for a complete physical end-to-end demonstration.**
Software preflight passes, but wiring, calibration, connected hardware, a local
broker, network configuration, and controlled FCM delivery remain unverified.
The mobile home source label also needs a separate correction before presenting
stale/offline behavior. This document is a procedure for later execution; its
setup, upload, database-creation and notification commands were NOT run in preflight.

The user will use **dry cardboard, not water**, to represent a water surface.
The ultrasonic distance must come from the real sensor. Describe the resulting
value as **DEMONSTRATION — cardboard-derived water-level proxy**. This verifies
sensing/integration and threshold behavior, not a calibrated river installation,
real rainfall, actual water-surface acoustics, or emergency-response effectiveness.
No solar panel, TP4056, 18650 charging circuit or unverified regulator is used.

## A. Components and unpowered wiring checklist — physical actions

First disconnect USB and all power. Photograph/record module labels privately,
then check the wiring with a meter before applying sensor power.

| Component | Verified firmware pin | Required physical check |
|---|---:|---|
| ESP32 DevKit V1 | Normal USB input | Board identity, undamaged USB connector, power-bank 5 V USB rating, suitable cable |
| JSN-SR04T TRIG | GPIO5 | Board revision/pin labels and 3.3 V trigger compatibility; do not impose an unknown boot-time pull on GPIO5 |
| JSN-SR04T ECHO | GPIO18 | ECHO must pass through verified voltage protection; never wire a 5 V echo directly to GPIO |
| Rain gauge | GPIO4 | Leave disconnected until the three terminals' functions and electrical interface are identified |
| Active-low buzzer **driver input** | GPIO25 | Confirm module supply voltage/current, LOW=on/HIGH=off, 3.3 V input compatibility and no 5 V signal pull-up |
| Green/yellow/red LEDs | GPIO26/27/14 | Each LED needs its own series resistor and correct polarity; confirm safe current from LED specifications |
| Ground | ESP32 GND | Verified common ground for all connected sensor/driver supplies; check breadboard rail splits |

For each LED, the intended arrangement is GPIO → series resistor → LED anode,
LED cathode → GND. Select resistance from `(3.3 V - LED forward voltage) / desired
current`; do not connect bare LEDs directly. Use low indicator current rather
than treating the chip's maximum output-current rating as a design target.

The buzzer GPIO is a logic signal, not a power supply. An unidentified two-pin
buzzer or module with excessive/unknown GPIO current must not be connected
directly. Use a verified driver appropriate to the module; preserve the firmware's
active-low control behavior. Buzzer OFF is set before GPIO25 becomes an output,
but a reset/boot transient still needs a physical check.

For a resistor ECHO divider, confirm ECHO → top resistor → GPIO18 junction,
and junction → bottom resistor → GND. Record actual measured resistor values;
calculate `Vjunction = Vecho * Rbottom / (Rtop + Rbottom)` using the module's
worst-case echo-high voltage and resistor tolerance. Confirm a valid ESP32 logic
HIGH while staying within the GPIO electrical limits, with margin. Verify supply
and divider continuity unpowered. If a powered voltage check is needed, keep the
GPIO disconnected and use appropriate pulse measurement equipment; a multimeter's
average of short pulses does not establish their peak voltage.

Sensor VCC must use a supply supported by its identified board revision. Only
use a verified USB-derived rail/output connection; do not guess a VIN pin's role,
feed an ESP32 GPIO as a supply, or connect an unverified regulator. Stop if the
sensor's required supply connection cannot be identified.

Three rain-gauge female terminals do not establish VCC/GND/signal or reed-switch
common/NO/NC. Obtain labeled-module documentation or electrical identification.
The firmware expects a debounced falling edge using a 3.3 V input pull-up. A
powered output must not apply an excessive voltage to GPIO4. With the gauge
omitted, report **rainfall not demonstrated**; zero counted tips is not proof of
measured zero rainfall. The 0.70 mm/tip coefficient remains provisional.

Electrical reference: [Espressif ESP32 datasheet](https://documentation.espressif.com/esp32_datasheet_en.html),
electrical characteristics and strapping pins. This does not identify the user's
sensor, buzzer, rain gauge or clone-board power wiring.

## B. USB power-bank startup — physical actions

1. Complete A with the circuit unpowered. Begin with the board alone if any
   peripheral supply/interface remains unknown.
2. Power the ESP32 through its **normal USB connector** from the USB power bank.
   Do not simultaneously inject another supply into VIN/GPIO. The laptop supplies
   USB during later flashing/serial work; switch to the power bank for the standalone
   demonstration instead of connecting competing USB supplies.
3. Check stable startup, repeated resets, cable movement and bank auto-shutdown
   over the intended presentation duration. Confirm the bank can sustain the
   actual board/sensor/driver load. No battery percentage is measured or published.
4. At boot the canonical firmware is UNKNOWN: all tier LEDs off, buzzer off until
   a trustworthy sample. Invalid echoes retain the previous valid local outputs.

## C. Measure calibration before choosing thresholds

Record these measured values; none are currently supplied:

- `H`: distance from the sensor's acoustic reference face to the cardboard at the
  agreed **zero demonstrated level**.
- Reliable minimum and maximum distance for this exact JSN-SR04T revision and
  this cardboard target, including a margin above the blind zone.
- Safe available cardboard travel, target size/alignment, and repeatability at
  every proposed target position. Keep hands/edges out of the beam; hold the target
  flat, perpendicular and stationary while each sample batch completes.
- Buzzer supply/input characteristics and ECHO protection measurements from A.
- Rain pinout/mm-per-tip only if rain is included; otherwise leave it out.

The physical calculation is `demonstrated_depth_cm = H - measured_distance_cm`.
Choose `H` from the **actual measured mounting/reference height**, not an invented
basin depth. Firmware currently assumes H=120 cm, minimum accepted distance=20 cm,
maximum=450 cm, and depth tiers 60/85/100 cm. No values were changed in preflight.
The largest valid depth under those current constants is 100 cm: EVACUATE sits
exactly at the accepted minimum-distance boundary, leaving no blind-zone margin.
These settings are not automatically feasible on the user's dry bench.

If and only if H really measures 120 cm, the existing 60/85/100 cm transitions
correspond algebraically to target distances 60/35/20 cm. These are **existing-code
examples, not approved target positions**. Do not attempt the 20 cm position unless
the actual sensor is reliable there with an appropriate margin; scaling is likely
needed if it is not.

Final numeric demonstration thresholds are BLOCKED until H, useful target travel
and reliable range are measured. Select ordered thresholds within that measured
travel, away from the blind zone. Keep firmware constants and backend station
thresholds identical. Do not change production/default classification logic.

## D. Isolated station/database and authenticated MQTT

Use a **new, separate demo database**; never copy/reset the existing development
database or modify its historical notification rows. Prefer STATION_001 in this
isolated database because the canonical firmware ID and mobile primary station
both currently use STATION_001. Rename this isolated row visibly to
`DEMONSTRATION — Cardboard target`; after measurement, set its sensor height and
thresholds to match the reviewed firmware calibration. These future demo-row
changes were NOT performed. Preserve default/real stations in their original DB.

A new DEMO_ESP32 ID is an alternative, but requires a reviewed firmware-ID change
and client primary/forecast-station selection work. Do not assume current mobile
home will select it: the controller prefers STATION_001. If scaling thresholds,
review fixed gauge marks/chart axes and alert-detail text as well; some current
presentation labels assume the old 60/85/100 cm defaults.

Confirmed laptop Wi-Fi address at preflight: **<laptop-lan-ip>/24**, 2.4 GHz,
channel 11, Windows profile **Public**. Recheck before the demo; DHCP can change it.
ESP32 and phone need the same reachable private demonstration LAN without client
isolation. MQTT_HOST on ESP32 must be this reachable laptop address, not localhost.
Backend and web on the laptop can use loopback. Internet is separately needed for
Google Maps and FCM; local sensing/MQTT do not require a public MQTT service.

Mosquitto was **not found** in PATH or its usual Program Files location. Install
an official local broker separately before the following commands. No broker
installation, listener, password file or firewall change was performed here.
Use [Mosquitto's authentication documentation](https://mosquitto.org/documentation/authentication-methods/)
and the installed version's [configuration reference](https://mosquitto.org/man/mosquitto-conf-5.html).

All commands below are PowerShell. Start with:

```powershell
$repo = 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
$demoRoot = Join-Path $repo 'agapay-web\.rebuild-qa\hardware-preflight-20261012\demo-local'
Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias Wi-Fi
New-Item -ItemType Directory -Path $demoRoot -Force | Out-Null
$brokerExe = (Get-Command mosquitto.exe -ErrorAction Stop).Source
$passwdExe = (Get-Command mosquitto_passwd.exe -ErrorAction Stop).Source
$passwdFile = Join-Path $demoRoot 'mqtt-users.passwd'
if (Test-Path $passwdFile) { throw 'Existing broker credentials: preserve them; do not use -c again.' }
& $passwdExe -c $passwdFile <mqtt-username>
& $passwdExe $passwdFile backend-demo
& $passwdExe $passwdFile observer-demo
```

These utilities prompt for passwords; do not pass passwords on the command line,
paste them into chat, or commit the local files. Create `mqtt-acl.conf` inside
`$demoRoot` with:

```text
user <mqtt-username>
topic write agapay/stations/STATION_001/telemetry
user backend-demo
topic read agapay/stations/+/telemetry
user observer-demo
topic read agapay/stations/STATION_001/telemetry
```

Create `mosquitto-demo.conf` in that same directory using the actual absolute
password/ACL paths (the current prepared directory is shown here):

```text
allow_anonymous false
password_file C:\Users\Asus\OneDrive\Documents\Agapay\Agapay\agapay-web\.rebuild-qa\hardware-preflight-20261012\demo-local\mqtt-users.passwd
acl_file C:\Users\Asus\OneDrive\Documents\Agapay\Agapay\agapay-web\.rebuild-qa\hardware-preflight-20261012\demo-local\mqtt-acl.conf
persistence false
listener 1883 127.0.0.1
listener 1883 <laptop-lan-ip>
```

If the installed broker version changes authentication syntax, follow its official
version-specific documentation before starting. This is authenticated **plaintext**
MQTT, not TLS or deployment-ready communication. Keep it on the controlled LAN.

Broker terminal, after confirming that controlled LAN and the installed config:

```powershell
& $brokerExe -c (Join-Path $demoRoot 'mosquitto-demo.conf') -v
```

For a trusted dedicated demo network, mark only that verified Wi-Fi connection
Private and allow TCP 1883/8000 narrowly from the demo subnet. These administrator
commands are later physical-network setup steps, NOT preflight actions:

```powershell
Set-NetConnectionProfile -InterfaceAlias Wi-Fi -NetworkCategory Private
New-NetFirewallRule -DisplayName 'AGAPAY demo MQTT' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 1883 -LocalAddress <laptop-lan-ip> -RemoteAddress <lan-subnet> -Profile Private
New-NetFirewallRule -DisplayName 'AGAPAY demo API' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -LocalAddress <laptop-lan-ip> -RemoteAddress <lan-subnet> -Profile Private
```

Do not change profile or open ports on an untrusted/shared network. Do not expose
1883/8000 to the internet or add router port forwarding. Remove these named rules
after the demo with `Remove-NetFirewallRule -DisplayName 'AGAPAY demo MQTT'` and
`Remove-NetFirewallRule -DisplayName 'AGAPAY demo API'` if they were created.

## E. Backend terminal — only after isolated demo setup is approved

The missing `paho-mqtt==2.1.0` dependency was added and installed in `.venv-auth`.
The current backend settings have MQTT disabled and FCM disabled. Starting the API
executes `create_all` and seeds STATION_001, so do not start it against the real DB
as a supposedly read-only preflight.

```powershell
Set-Location (Join-Path $repo 'agapay-backend')
$demoDb = Join-Path $demoRoot 'agapay_demo.db'
if (Test-Path $demoDb) { throw 'Choose/review an isolated demo database; do not overwrite existing records.' }
$env:AGAPAY_DATABASE_URL = 'sqlite:///' + ($demoDb -replace '\\','/')
$env:AGAPAY_MQTT_ENABLED = 'true'
$env:AGAPAY_MQTT_HOST = '127.0.0.1'
$env:AGAPAY_MQTT_PORT = '1883'
$env:AGAPAY_MQTT_TLS = 'false'
$env:AGAPAY_MQTT_TOPIC = 'agapay/stations/+/telemetry'
$env:AGAPAY_MQTT_CLIENT_ID = 'agapay-cardboard-demo-backend'
$env:AGAPAY_MQTT_USERNAME = 'backend-demo'
$brokerSecret = Read-Host 'Backend broker password' -AsSecureString
$env:AGAPAY_MQTT_PASSWORD = [System.Net.NetworkCredential]::new('', $brokerSecret).Password
$env:AGAPAY_NOTIFICATION_PROVIDER = 'disabled'
$env:AGAPAY_PREDICTION_PREVIEW_ENABLED = 'false'
.\.venv-auth\Scripts\python.exe -m app.create_admin
.\.venv-auth\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The CLI interactively creates a new isolated administrator; it does not seed a
known password. This creates data only after the separate demo setup checkpoint.
After initial startup stop and review/calibrate/label the isolated station before
physical publication. Reuse the approved DB on subsequent starts by deliberately
setting its same URL, not by copying a production DB or removing the safety guard
without checking the selected path.

## F. Web terminal

```powershell
Set-Location (Join-Path $repo 'agapay-web')
$env:AGAPAY_API_URL = 'http://127.0.0.1:8000'
npm run dev -- --webpack --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`, log in as the isolated staff account. The Next.js
account proxy forwards to the backend; the ESP32 never publishes through Next.js.
Verify Default and Dark appearance, station depth/history/tier, and persistent
Alerts history. Forecast previews must stay off. The actual model boundary is
untrained; preserve not-trained/unavailable/expired states. No forecast changes
authoritative depth thresholds or alert tiers.

## G. Flutter Android terminal

No Android target was detected at preflight. Connect/unlock the designated phone,
enable USB debugging, authorize this laptop, then inspect actual device IDs:

```powershell
adb devices -l
Set-Location (Join-Path $repo 'agapay-mobile')
flutter devices
$androidTarget = Read-Host 'Exact authorized Android device ID from the list'
flutter run --debug -d $androidTarget --dart-define=AGAPAY_API_URL=http://<laptop-lan-ip>:8000 --dart-define=AGAPAY_FIREBASE_ENABLED=false
```

The default Android API URL is the emulator address 10.0.2.2, so the LAN override
is required for a physical phone. Debug Android allows this controlled-LAN HTTP
test; release AuthApi rejects HTTP. Verify `http://<laptop-lan-ip>:8000/health` from
the phone first. Do not disable release HTTPS enforcement. Sign into a designated
resident account in the isolated database; mobile registration uses the backend's
resident audience. Web staff credentials are not a substitute for that flow.

## H. Canonical firmware build/upload/monitor commands

PlatformIO Core 6.2.0 is installed as a Python module; its standalone `pio` command
was not on PATH. Use `src/main.cpp`, not old example/sketch firmware.
`include/secrets.h` already exists but contains network placeholders. Edit locally
after checking the private LAN: Wi-Fi name/password, MQTT_HOST=<laptop-lan-ip>,
MQTT_PORT=1883, MQTT_USERNAME=<mqtt-username> and the prompted broker password.
Do not overwrite an existing secret header by blindly copying the example.

```powershell
Set-Location (Join-Path $repo 'agapay-firmware')
python -m platformio run -e esp32doit-devkit-v1
python -m platformio device list
```

No serial port was detected at preflight. After wiring/calibration approval,
connect the ESP32 to the laptop using a **data-capable** USB cable and verify the
actual USB serial chip/driver. Board-only connect/disconnect should establish the
correct port. Do not guess COM3 or another port. Only at the separate upload gate:

```powershell
$espPort = Read-Host 'Verified ESP32 COM port'
python -m platformio run -e esp32doit-devkit-v1 --target upload --upload-port $espPort
python -m platformio device monitor --port $espPort --baud 115200
```

These upload/monitor commands were NOT run. Do not use erase targets or erase NVS.
Firmware persists `agapay/boot_no` before reserving sequence blocks; ordinary
restarts avoid reusing sequence IDs. Erasing NVS requires a separately reviewed
station identity/sequence recovery plan. Publish is QoS 0, non-retained, every
10 seconds, with no backend receipt acknowledgement.

## I. Prove an actual physical telemetry record reached the backend

Ensure the HTTP simulator and virtual-station publisher are **not running** for
the same station. Show the moving cardboard and Serial distance/depth/valid/tier.
Serial `sent` means socket submission only. Require the backend log's
`Stored MQTT telemetry STATION_001/<sequence>` and the persisted record below.

After setting `$demoDb` to the approved isolated DB, use a read-only query:

```powershell
$env:AGAPAY_DEMO_READ_DB = $demoDb
@'
import os, sqlite3
from pathlib import Path
p = Path(os.environ['AGAPAY_DEMO_READ_DB']).resolve()
if not p.is_file(): raise SystemExit('Database does not exist; do not create it here')
db = sqlite3.connect(p.as_uri() + '?mode=ro', uri=True)
db.execute('PRAGMA query_only=ON')
print(db.execute('select station_id,sequence_no,water_depth_cm,sensor_quality,device_uptime_ms,recorded_at from telemetry order by id desc limit 1').fetchone())
print(db.execute('select previous_severity,new_severity,sequence_no,water_depth_cm from alert_transitions order by id desc limit 4').fetchall())
db.close()
'@ | .\.venv-auth\Scripts\python.exe -
```

Run this in `agapay-backend`. Match the exact sequence, depth, quality and device
uptime to the Serial/MQTT report. Backend UTC recorded_at is **receive time**, not
sensor acquisition time. Invalid water depth must be null; a timeout is not zero.

## J. Prove web/mobile received the same reading and measure latency

Read the authenticated monitoring API via the apps; compare its latest history
sequence/depth/quality with I, and the displayed depth/tier/history on both clients.
Use a small Node/browser or Flutter fixture only for automated tests, never as
the physical presentation's data source. Test theme changes in both clients.

Actual timing from source: firmware samples approximately every second with five
probes ≥60 ms apart, each echo bounded to 30 ms; it publishes every 10 seconds.
Web monitoring polls every 5 seconds while visible, skipping overlapping requests;
mobile monitoring polls every 5 seconds while signed in. Healthy foreground
updates may take approximately 15–17 seconds from target movement, plus request
and processing delays. This is an estimate, not a measured hardware guarantee.
There is no telemetry WebSocket guarantee. Backend stale detection is >30 seconds
since last receipt; subsequent client polling adds delay.

Web persistent alert resources schedule a poll 5 seconds after settlement.
Mobile active alerts poll at 5 seconds; history/detail refresh on navigation or
explicit refresh and push events. Do not promise continuous history polling.
Forecast polling is 30 seconds; no model training/replacement was performed.

**Remaining client blockers:** the mobile home label chooses LIVE for a device
with a last valid reading even when offline/stale. Both clients retain snapshots
on failed monitoring requests, so some connection counts/indicators may remain
cached. The web header was corrected separately to show OFFLINE for failed or aged
feeds. The protected 48-file candidate (including mobile home) was not edited.
Do not demonstrate mobile outage labeling as passed until a separately reviewed
fix is implemented; a source/build pass is not evidence that this behavior works.

## K. Demonstrate measured NORMAL → ADVISORY → WARNING → EVACUATE

After measured calibration is approved and matches firmware/backend, mark four
cardboard positions using `D = H - target_depth`. Start below ADVISORY (NORMAL),
then move the target **towards** the sensor for increasing demonstrated depth.
Use repeatable measured distances within the sensor's reliable range; don't
invent readings or inject HTTP telemetry to produce an escalation.

Hold each position until at least one valid published sample has been persisted
and both clients show it. Confirm green for NORMAL, yellow for ADVISORY/WARNING,
red plus active-low buzzer for EVACUATE. Advisory and warning share yellow locally;
Serial/backend tier names distinguish them. Query transition history after each
step. Invalid input must retain the previous tier without making a NORMAL recovery.
Move back to the measured NORMAL position to verify the episode resolves.

## L. Local safety behavior during Wi-Fi interruption

Keep the USB bank and verified circuit powered. Interrupt only the dedicated
demo network (don't shut down an unrelated/shared network), and continue moving
the cardboard between approved positions. Verify local GPIO/Serial tiers continue
changing independently of MQTT; confirm Wi-Fi retry is 10 seconds and MQTT retry
5 seconds. The network client runs on a separate FreeRTOS task.

Reconnect and require a new sequence/record. Offline, failed and ≥10-second-stale
queued reports are dropped; the latest-only queue can replace unsent intervals.
There is no durable replay or reconstruction of missed history/rainfall. A sensor
fault holds the last local tier; this is not a dedicated fault indicator.

## M. Controlled FCM procedure — separate explicit send checkpoint

No notification was sent during preflight. Current backend provider is disabled
and project/credential settings are not configured. Native Android configuration
exists, but project alignment, permission, registration, physical delivery and
tap navigation were not physically verified. Existing real DB inspection found
three historical UNKNOWN deliveries and one SENT delivery; do not replay, reset
or modify them. SENT/provider acceptance is not proof of a phone display or tap.

Use only the isolated demo DB. After physical MQTT→DB→clients is proven, configure
the intended Firebase project/credentials locally without exposing them. Enable
push on the designated phone by rebuilding G with
`--dart-define=AGAPAY_FIREBASE_ENABLED=true`, and grant notification permission.
Verify exactly one eligible enabled **active resident** Android device belongs
to that phone. Registration is session-independent and token rotations are handled;
do not log provider tokens, session hashes, token fingerprints or credential files.

Before creating a new physical escalation, inspect only allowlisted fields through
a read-only DB query: device ID/user ID/platform/enabled, queue ID/state/attempts,
event/transition/episode/station IDs, severity. Confirm no unrelated PENDING,
PROCESSING or due FAILED rows and no unknown recipient. Reconfirm immediately
before the proposed send. `--limit 1` selects the oldest sendable row; it is NOT a
device or delivery-ID filter. Stop if the queue/recipient gate fails. Do not run an
automatic or recurring worker.

After a **separate explicit user authorization**, and only if exactly the intended
new delivery is sendable, the existing bounded worker command is:

```powershell
# Backend terminal: same approved isolated DB and private credential settings.
$env:AGAPAY_NOTIFICATION_PROVIDER = 'fcm'
.\.venv-auth\Scripts\python.exe -m app.notification_worker --limit 1 *> (Join-Path $demoRoot 'worker-private.log')
```

Do NOT run this now. The worker log can contain token fingerprints: keep it private
and inspect allowlisted DB state instead of printing/uploading it. Require
SENT/accepted for provider acceptance, separate phone-display confirmation, and
separate tap confirmation. UNKNOWN and ambiguous PROCESSING outcomes are not
automatically retried. Taps must use SENSOR_ESCALATION with a positive alert_id,
restore authentication and fetch the matching persistent community alert detail.
Foreground push refreshes in-app alerts; OS background notification display must
be checked on the real phone. Internet/provider failures do not invalidate local
LED/buzzer or persisted in-app alerts.

## N. Recovery/fallback

- Bad echo/alignment: stop target movement, check dry target geometry and range;
  invalid samples remain null and local outputs retain their previous valid tier.
- Wi-Fi/MQTT loss: demonstrate verified local outputs; label server readings stale,
  then wait for a fresh matching sequence after recovery. Do not replay missing data.
- USB/bank failure: stop; check bank/cable/load, then restart normally without NVS
  erasure. UNKNOWN startup must not be represented as NORMAL.
- Backend/phone failure: keep local physical evidence and Serial logs, clearly
  label the server/mobile portion unavailable. Do not switch silently to virtual data.
- FCM failure: show persistent in-app alerts; identify push as unverified/unavailable.
  Do not retry UNKNOWN or send a batch to unverified recipients.
- Maps unavailable: use station list/detail and measured telemetry. Map network
  availability is independent of MQTT and depends on external Google services.

## O. Final go/no-go gates

All physical/network entries are currently pending:

- [ ] ECHO protection, LED resistors, sensor supply and active-low buzzer driver verified unpowered.
- [ ] Rain module identified/calibrated or explicitly omitted without a rainfall claim.
- [ ] USB-bank stability and exact ESP32 board/serial port verified.
- [ ] Actual H, usable minimum range, target travel and repeatability recorded.
- [ ] Reviewed demo calibration matches firmware and isolated backend station; visibly labeled DEMONSTRATION.
- [ ] Local authenticated broker installed and bound only to approved LAN/loopback; private firewall reviewed.
- [ ] Firmware network placeholders replaced privately; MQTT enabled only for the isolated backend.
- [ ] No simulator publishing for that station; physical sequence matches Serial, MQTT ingestion and DB row.
- [ ] Web/mobile depth, chart and authoritative persistent alert transitions verified in both themes.
- [ ] Mobile stale LIVE label corrected separately; stale/cache behavior demonstrated honestly.
- [ ] Local LEDs/buzzer continue during Wi-Fi interruption, and fresh telemetry resumes without replay.
- [ ] Designated Android login/device registration and Firebase project alignment verified.
- [ ] Exactly intended sendable FCM recipient/delivery verified; separate send approval obtained.
- [ ] Provider acceptance, phone display and tap navigation recorded separately.

Automated preflight results: ESP32 build PASS; firmware host/contract PASS (six
generated payloads); isolated backend 223 tests PASS; Flutter analysis PASS and
84 tests PASS; map test 1 PASS; web freshness tests 5 PASS; final web typecheck and
production Webpack build PASS. Backend/web/mobile validation used copied current
sources in an ignored snapshot, with an isolated test database. This was not a
new validation of HEAD plus only the staged theme patch. No physical sensor,
broker, phone or new browser session was validated during this preflight.

The 48-file staged theme patch remains unchanged. New integration work and this
runbook remain unstaged. No commit, push, merge, flash, device-memory erase, live
FCM send, or modification of historical development/production records occurred.
