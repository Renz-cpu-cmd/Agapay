# AGAPAY Software-First Setup Day

Use Windows PowerShell unless a step specifically says to use Arduino IDE. Complete each checkpoint before moving on.

## Safety boundary for today

- Power the ESP32 only through its USB data cable.
- Do not connect the JSN-SR04T, rain gauge, buzzer, LEDs, CN3065, 18650 battery, MT3608, solar panel, pump, or water basin yet.
- A charge-only USB cable can power the board but cannot upload code. Use a known data cable.

## Part 1 — Install Arduino IDE and ESP32 support

1. Download and install the latest supported Arduino IDE 2 from `https://www.arduino.cc/en/software`.
2. Open Arduino IDE.
3. Select **File > Preferences**.
4. In **Additional Boards Manager URLs**, add this official stable ESP32 URL:

   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`

5. Click **OK**.
6. Select **Tools > Board > Boards Manager**.
7. Search for `esp32`.
8. Install **esp32 by Espressif Systems** using the latest stable release.
9. Restart Arduino IDE after installation.

Checkpoint: **Tools > Board** now contains an `esp32` section.

## Part 2 — Install the two required Arduino libraries

1. Select **Tools > Manage Libraries**.
2. Search for `ArduinoJson`.
3. Install **ArduinoJson by Benoit Blanchon**. This starter uses the ArduinoJson 7 API.
4. Search for `PubSubClient`.
5. Install **PubSubClient by Nick O'Leary**.

Checkpoint: change the Library Manager filter to **Installed** and confirm both names and authors.

## Part 3 — Connect the ESP32 and run Blink

1. Disconnect every component from the ESP32. Only the USB data cable should be attached.
2. Connect the ESP32 DevKit V1 to the laptop.
3. In Arduino IDE, select the COM port shown for the board.
4. Select **DOIT ESP32 DEVKIT V1** if that exact option exists. If it does not, select **ESP32 Dev Module**.
5. Open `agapay-firmware/examples/01_blink/01_blink.ino`.
6. Click **Verify**. Wait for compilation to finish.
7. Click **Upload**.
8. Open **Tools > Serial Monitor** and set the speed to **115200 baud**.

Expected result:

- The onboard blue LED switches on and off once per second.
- Serial Monitor alternates between `LED ON` and `LED OFF`.

If the onboard LED does not light but upload succeeds, the particular board may not have an LED on GPIO 2. With USB unplugged, connect the purchased green LED as follows, then reconnect USB:

`GPIO 2 -> 220-ohm resistor -> LED long leg (anode); LED short leg/flat side (cathode) -> GND`

Common upload fixes:

- No COM port: try a known data USB cable and another USB port first.
- Stuck on `Connecting...`: hold **BOOT**, start Upload, then release BOOT when writing begins.
- Wrong target: reselect the ESP32 board and COM port.
- Port busy: close Serial Monitor and any program using that COM port, then upload again.

Checkpoint: record the COM port, selected board, upload result, and a photo/video of the blinking LED.

## Part 4 — Verify ArduinoJson and PubSubClient

1. Open `agapay-firmware/examples/02_library_check/02_library_check.ino`.
2. Click **Verify**, then **Upload**.
3. Open Serial Monitor at **115200 baud**.

Expected output includes:

```json
{"station_id":"STATION_001","sequence_no":1,"water_depth_cm":42.7,"rainfall_mm":0.7,"sensor_quality":"valid","device_uptime_ms":0,"firmware_version":"0.1.0"}
```

The uptime value will be different. This proves that both required libraries compile and the agreed JSON can be generated.

## Part 5 — Prepare the two Git repositories

Create two empty repositories in the team's GitHub organization:

- `agapay-firmware`
- `agapay-backend`

Do not add a GitHub README, `.gitignore`, or license during remote creation because the provided folders already contain starter files.

Then run these commands in PowerShell. Replace `<YOUR-ORG>` with the actual GitHub organization name.

```powershell
cd C:\AGAPAY\AGAPAY_Day1_Starter\agapay-firmware
git init
git add .
git commit -m "chore: initialize AGAPAY firmware"
git branch -M main
git remote add origin https://github.com/<YOUR-ORG>/agapay-firmware.git
git push -u origin main
git switch -c develop
git push -u origin develop
```

```powershell
cd C:\AGAPAY\AGAPAY_Day1_Starter\agapay-backend
git init
git add .
git commit -m "chore: initialize AGAPAY backend"
git branch -M main
git remote add origin https://github.com/<YOUR-ORG>/agapay-backend.git
git push -u origin main
git switch -c develop
git push -u origin develop
```

If Git asks who you are, set your own name and GitHub email, then repeat the commit:

```powershell
git config --global user.name "YOUR NAME"
git config --global user.email "YOUR_GITHUB_EMAIL"
```

Checkpoint: both GitHub repositories show `main` and `develop`, and no file named `secrets.h` or `.env` is committed.

In each GitHub repository, open **Settings > Branches** and apply the execution-plan rules:

- `main`: require a pull request, require at least one approval, and block direct pushes.
- `develop`: require a pull request; feature branches merge here first.
- Use `feature/<role>/<description>`, such as `feature/backend/mqtt-subscriber`.

Set `develop` as the working/default branch only after both branches have been pushed successfully. Keep `main` as the stable release branch.

## Part 6 — Understand the MQTT telemetry contract

Device topic:

`agapay/stations/STATION_001/telemetry`

Backend subscription pattern:

`agapay/stations/+/telemetry`

Valid payload:

```json
{
  "station_id": "STATION_001",
  "sequence_no": 1000001,
  "water_depth_cm": 42.7,
  "rainfall_mm": 0.7,
  "sensor_quality": "valid",
  "device_uptime_ms": 15342,
  "firmware_version": "0.1.0"
}
```

Rules:

- `station_id` in the topic and payload must match.
- `sequence_no` identifies duplicates for one station.
- `water_depth_cm` is an absolute water depth in centimeters, not a percentage.
- `rainfall_mm` is the rain added since the previous telemetry publish. The confirmed rain gauge contributes `0.70 mm` per tip.
- When the ultrasonic measurement is invalid, send `water_depth_cm: null` and `sensor_quality: "invalid"`.
- The backend adds `recorded_at` in UTC; the ESP32 does not invent a clock time.
- Do not send `battery_pct` until a real battery-measurement circuit has been built and calibrated.
- Current ESP32 development messages use PubSubClient's QoS 0 publishing and are not retained. Repeated telemetry plus backend deduplication is used for this prototype stage.
- Public anonymous brokers may contain dummy data only. Deployment-style tests require an authenticated TLS broker.

The machine-readable rules are in `agapay-firmware/docs/mqtt-telemetry.schema.json`.

## Part 7 — Start FastAPI and the local development database

This Day-1 build defaults to SQLite so the team can prove API -> validation -> database today without installing a database server. The same SQLAlchemy models can be switched to PostgreSQL/Supabase with `AGAPAY_DATABASE_URL`; PostgreSQL remains the project target.

Check Python first:

```powershell
py --version
```

Use Python 3.11 or 3.12. If neither is installed, install Python from `https://www.python.org/downloads/windows/` and enable its PATH/launcher option.

Open PowerShell in `agapay-backend`, then run:

```powershell
cd C:\AGAPAY\AGAPAY_Day1_Starter\agapay-backend
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

If `py -3.11` says that 3.11 is unavailable but `py --version` shows 3.12, use `py -3.12 -m venv .venv`.

Keep this PowerShell window open. Expected startup address:

`http://127.0.0.1:8000`

Open these in the browser:

- Health: `http://127.0.0.1:8000/health`
- Interactive API: `http://127.0.0.1:8000/docs`
- Stations: `http://127.0.0.1:8000/api/stations`

Checkpoint: `/health` returns `{"status":"ok","database":"connected"}` and `/api/stations` contains `STATION_001`.

## Part 8 — Send simulated sensor data

Open a second PowerShell window:

```powershell
cd C:\AGAPAY\AGAPAY_Day1_Starter\agapay-backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python simulator\simulate_http.py --count 10 --interval 1
```

The simulator sends ten readings. Rain increments are `0.00` or `0.70 mm`, matching the purchased rain-gauge specification.

Now open:

- Latest: `http://127.0.0.1:8000/api/telemetry/STATION_001/latest`
- History: `http://127.0.0.1:8000/api/telemetry/STATION_001?limit=20`

Checkpoint: the simulator reports HTTP `201`, latest returns one stored reading, and history returns ten readings.

Stop the server with **Ctrl+C** only after screenshots are captured.

## Part 9 — Save today's evidence

Create one dated folder in `agapay-docs`, then save:

- Arduino IDE version screenshot
- ESP32 board package screenshot
- ArduinoJson and PubSubClient installed screenshot
- Blink upload output and blinking-board photo/video
- Library-check JSON from Serial Monitor
- GitHub repository pages for `main` and `develop`
- FastAPI `/health` screenshot
- FastAPI `/docs` screenshot
- Simulator terminal output
- Latest/history telemetry screenshots

## Definition of done

- [ ] Latest Arduino IDE 2 installed
- [ ] Official stable ESP32 board package installed
- [ ] ESP32 board and COM port selected
- [ ] Blink uploaded and observed
- [ ] ArduinoJson library check passed
- [ ] PubSubClient library check passed
- [ ] `agapay-firmware` repository initialized and pushed
- [ ] `agapay-backend` repository initialized and pushed
- [ ] MQTT topic and JSON contract accepted by the team
- [ ] FastAPI server running
- [ ] Development database created
- [ ] Ten simulated readings stored
- [ ] Latest and history endpoints verified
- [ ] Evidence saved
