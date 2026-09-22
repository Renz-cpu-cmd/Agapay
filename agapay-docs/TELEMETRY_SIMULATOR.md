# AGAPAY Virtual Monitoring Station

The virtual station exercises the current telemetry path before the physical
station is assembled:

`simulator -> POST /api/telemetry -> database -> monitoring snapshot -> web and mobile`

It uses the same fields planned for the device. Replacing the simulator later does
not require a new frontend contract.

## Start the system

Start FastAPI from `agapay-backend`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Start the web app from `agapay-web`:

```powershell
npm run dev
```

For Flutter, an Android emulator automatically uses `http://10.0.2.2:8000`.
Desktop and web Flutter targets use `http://127.0.0.1:8000`. A physical phone needs
the computer's LAN address through `--dart-define=AGAPAY_API_URL=http://ADDRESS:8000`.

The simulator can send readings without an account. Sign in to the web or mobile
app with a local account because monitoring reads are protected.

## Run a scenario

In another terminal, from `agapay-backend`:

```powershell
python simulator\simulate_http.py --scenario rising --count 20 --interval 2
```

Available scenarios:

| Scenario | Behavior |
|---|---|
| `normal` | Small valid changes below the advisory threshold |
| `rising` | Gradual rise across advisory, warning, and evacuation tiers |
| `flash-flood` | Faster late-stage rise through every tier |
| `recovery` | Falls from evacuation to normal |
| `sensor-fault` | Valid readings followed by invalid null measurements |
| `offline` | Sends valid readings and then stops |

Use `--loop` for a repeating feed and stop it with Ctrl+C. Use `--dry-run` to print
payloads without contacting the API:

```powershell
python simulator\simulate_http.py --scenario flash-flood --count 12 --interval 0 --dry-run
```

The default freshness limit is 30 seconds. After a finite `offline` run, the apps
keep the last flood severity visible while reporting the connection as offline.
The `sensor-fault` scenario exposes the latest invalid sample and keeps the last
valid severity; it never converts a missing measurement into zero or NORMAL.

## What to observe

- The web header changes to `SIMULATOR`, and dashboard values, charts, station
  details, map marker, alerts, analytics, and system health refresh automatically.
- Mobile Home displays `VIRTUAL STATION`; the map and alert details use the same
  reading, and View History lists recent received samples.
- Rainfall is per reporting interval. It is not a daily accumulation.
- Station status, connection freshness, sensor quality, and flood tier remain
  separate states.

The UCU irrigation coordinates are a planned map point. Confirm the exact mounting
location, sensor height, and thresholds during the physical site survey.

This validates telemetry collection and presentation. It does not provide trained
ML predictions, push notifications, or automatic emergency dispatch.
