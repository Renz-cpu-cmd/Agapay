# AGAPAY demo restart commands

Use Windows PowerShell under the same Asus Windows account on this laptop.
Connect the laptop to the phone's2.4 GHz pangit hotspot first. Keep the hotspot
and laptop awake throughout the demo. Keep the ESP32 on its USB power bank.

Closing Codex/browser does not necessarily stop the existing background services.
After a laptop reboot, start the following services in order. The guarded commands
reuse a listening service rather than launching duplicates. Leave the three service
terminals open. No database reset, retraining or firmware upload is needed when
the laptop's hotspot IP is unchanged.

## 1. Common project folder and preflight

Run in the first PowerShell window:

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
& .\agapay-backend\.venv-ml\Scripts\python.exe .\data\live_rain\demo_preflight.py
& .\agapay-backend\start-live-rain-demo.ps1 -BrokerHost 127.0.0.1 -BrokerPort 1884 -CheckOnly
```

Expect PASS. The verified laptop IPv4 is<broker-lan-ip>. The first check compares
the current Wi-Fi address with the firmware address and verifies existing demo
files and any occupied ports. It never prints passwords or starts servers.
The second check imports the encrypted backend-demo login and verifies model and
dataset provenance without starting another backend or modifying data.

If a script is blocked by your machine's execution policy, do not globally disable
security. The same commands can be run in an already approved PowerShell session.

## 2. Window1 — authenticated MQTT broker

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
if (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 1884 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host 'Demo broker is already running.'
} else {
    & 'C:\Program Files\mosquitto\mosquitto.exe' -c '.\data\live_rain\broker\mosquitto.conf' -v
}
```

ESP32 uses laptop LAN1883. FastAPI uses loopback1884 on this same broker.
Do not use the unrelated stock loopback1883 broker. Existing ACL/password files
remain in place; anonymous access stays disabled.

## 3. Window2 — isolated FastAPI and forecast model

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
if (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host 'Demo backend is already running.'
} else {
    & .\agapay-backend\start-live-rain-demo.ps1 -BrokerHost 127.0.0.1 -BrokerPort 1884
}
```

The existing MQTT login is saved under
`data/live_rain/broker/backend-demo.credential.xml`, encrypted by Windows for this
same Windows account/computer. It is ignored by Git and is not plaintext. Do not
share it. No credential was rotated or guessed. `-PromptCredential` remains
available for intentionally supplying the existing backend-demo broker login;
this is separate from your dashboard password.

The script retains `demo-api.sqlite3` and `rain-events.sqlite3`, launches from the
backend directory so its verified model paths resolve, and keeps notifications
disabled. Do not run a simulator, worker or database initialization command.

## 4. Window3 — dashboard on3011

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
if (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 3011 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host 'Demo dashboard is already running.'
} else {
    Set-Location '.\agapay-web'
    $env:AGAPAY_API_URL = 'http://127.0.0.1:8000'
    $env:AGAPAY_WEB_ORIGIN = 'http://127.0.0.1:3011'
    npm run dev -- --webpack --hostname 127.0.0.1 --port 3011
}
```

Wait until Next reports ready. Use127.0.0.1 consistently; the configured origin
check does not accept an alternate localhost origin for login/forecastPOST.

## 5. Open and verify

Use another PowerShell tab, or the first window if its broker was already running:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health'
Start-Process 'http://127.0.0.1:3011/stations/STATION_001'
```

Expect statusok/databaseconnected. Sign in with the previously created demo
administrator if necessary; email`demo-admin@example.com`, using your existing
password. No new account is required.

The station page should become LIVE, Rainfall Activity Connected, and forecasts
should start automatically for a new local setup. Existing saved settings and an
explicit Stop are respected. Startup scans may take about a minute after the
ESP32 is powered; once connected, water telemetry arrives about every2 seconds.
The Google Maps demo quota was reached earlier; this station page avoids the map.

Do a short dry-cardboard movement/LED/buzzer rehearsal before presenting. The
projection is a historical-rainfall/controlled-basin demonstration; calibration
and real-world flood forecast validation remain pending.

## Only if the laptop's DHCP IPv4 changed

Connect to pangit first. If the preflight still reports a different Wi-Fi address,
stop the demo broker in its own terminal withCtrl+C. Do not stop unrelated brokers.
Connect the ESP32 to the laptop's USB port; verify it appears asCOM9. Then run:

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
& .\agapay-backend\.venv-ml\Scripts\python.exe .\data\live_rain\prepare_demo_ip.py
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio device list
# Run the upload only after confirming COM9 and closing any COM9 monitor:
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -e esp32-cardboard-demo -t upload --upload-port COM9
```

The IP helper backs up the previous broker configuration and changes only its
LAN listener and the local firmware MQTT_HOST. It does not upload automatically,
change credentials, GPIOs, calibration, schemas or NVS. The ordinary upload keeps
NVS; do not runerase-flash. Return the ESP32 to the power bank, then repeat steps1–5.

## Closing

To stop foreground services that you started in these terminals, pressCtrl+C in
the dashboard, backend and broker windows. Power the ESP32 off last, once the
latest real rain event has been received. Existing background services from this
session may remain after closing this chat; the startup checks will recognize
them on your next attempt. A laptop shutdown stops them normally.

Restart preparation verification onOctober13: network/port preflight passed;
Windows-encrypted credential export/import roundtrip passed; `-CheckOnly` loaded
the model and checked dataset provenance successfully. The normal live services
were left running during this preparation.
