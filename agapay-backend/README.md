# AGAPAY Backend

Day-1 FastAPI and database foundation for AGAPAY.

## What is implemented

- FastAPI application and interactive OpenAPI documentation
- SQLAlchemy 2 database layer
- Automatically seeded `STATION_001` demo station
- Strict telemetry validation matching the MQTT contract
- Duplicate protection using `(station_id, sequence_no)`
- UTC receive timestamps
- Latest and historical telemetry endpoints
- HTTP simulated-sensor sender
- Optional MQTT subscriber scaffold

Only the `stations` and `telemetry` foundation is included today. Authentication, alerts, WebSockets, notifications, reports, and ML are later phases.

## Start on Windows

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

In a second activated PowerShell window:

```powershell
python simulator\simulate_http.py --count 10 --interval 1
```

## Useful endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | API and database health |
| GET | `/api/stations` | List registered stations |
| POST | `/api/stations` | Register a station |
| POST | `/api/telemetry` | Validate and store one reading |
| GET | `/api/telemetry/{station_id}/latest` | Latest reading |
| GET | `/api/telemetry/{station_id}?limit=20` | Recent history |

## Database progression

The default database is the temporary local file `agapay_dev.db`, which is excluded from Git. It proves the complete validation and persistence flow without requiring a database server on Day 1.

PostgreSQL/Supabase remains the AGAPAY target. After PostgreSQL is ready:

1. Install `requirements-postgres.txt`.
2. Change `AGAPAY_DATABASE_URL` in `.env`, for example:

   `AGAPAY_DATABASE_URL=postgresql+psycopg://agapay_user:password@localhost:5432/agapay`

3. Restart FastAPI.

Before deployment, add Alembic migrations and use a secret manager rather than committing credentials.

## Optional local MQTT subscriber

After a local/private broker is ready:

1. Install `requirements-mqtt.txt`.
2. Set `AGAPAY_MQTT_ENABLED=true` and the broker settings in `.env`.
3. Restart FastAPI.

The subscriber listens to `agapay/stations/+/telemetry`, checks that the topic station matches the payload, validates the same Pydantic model used by HTTP, and stores through the same service.

Do not send sensitive or real deployment data through a public anonymous broker.

## Run tests

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```
