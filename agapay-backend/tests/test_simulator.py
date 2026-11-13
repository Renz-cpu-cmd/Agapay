import argparse
import random
import httpx

from simulator.simulate_http import SCENARIOS, readings, scenario_reading
from simulator import simulate_http


def test_scenarios_cover_normal_flood_recovery_fault_and_offline_profiles():
    rng = random.Random(2026)
    normal = [scenario_reading("normal", i, 8, rng)[0] for i in range(8)]
    rising = [scenario_reading("rising", i, 8, rng)[0] for i in range(8)]
    flash = [scenario_reading("flash-flood", i, 8, rng)[0] for i in range(8)]
    recovery = [scenario_reading("recovery", i, 8, rng)[0] for i in range(8)]
    fault = [scenario_reading("sensor-fault", i, 8, rng) for i in range(8)]
    offline = [scenario_reading("offline", i, 8, rng)[0] for i in range(8)]

    assert max(normal) < 60
    assert rising[0] < 60 and rising[-1] >= 100
    assert flash[0] < 60 and flash[-1] >= 100
    assert recovery[0] >= 100 and recovery[-1] < 60
    assert fault[2][2] == "valid" and all(value[2] == "invalid" and value[0] is None for value in fault[3:])
    assert all(value is not None and value < 60 for value in offline)
    assert set(SCENARIOS) == {"normal", "rising", "flash-flood", "recovery", "sensor-fault", "offline"}


def test_generated_payloads_match_the_telemetry_contract():
    args = argparse.Namespace(
        station_id="STATION_001",
        scenario="rising",
        count=4,
        interval=2,
        loop=False,
        seed=2026,
        start_sequence=100,
    )
    payloads = list(readings(args))
    assert [payload["sequence_no"] for payload in payloads] == [100, 101, 102, 103]
    uptimes = [payload["device_uptime_ms"] for payload in payloads]
    assert uptimes == sorted(uptimes) and all(value >= 0 for value in uptimes)
    from app.schemas import TelemetryCreate
    for body in payloads:
        TelemetryCreate.model_validate(body)
    assert len({p["boot_id"] for p in payloads}) == 1
    assert all(p["measured_at"] is not None for p in payloads)
    assert all(payload["firmware_version"] == "0.2.0-simulator" for payload in payloads)


def simulator_args(**changes):
    return argparse.Namespace(url="http://127.0.0.1:8000", station_id="TEST_SIM", scenario="normal",
        count=2, interval=0, loop=False, dry_run=False, seed=2026, start_sequence=100, **changes)


def test_real_simulator_refuses_missing_token_without_contacting_server(monkeypatch, capsys):
    monkeypatch.delenv("AGAPAY_STATION_INGEST_TOKEN", raising=False)
    monkeypatch.setattr(simulate_http, "parse_args", simulator_args)
    monkeypatch.setattr(simulate_http.httpx, "Client", lambda **kw: (_ for _ in ()).throw(AssertionError("Must not connect")))
    assert simulate_http.main() == 2
    assert "AGAPAY_STATION_INGEST_TOKEN" in capsys.readouterr().err


def test_simulator_adds_station_authorization_without_logging_token(monkeypatch, capsys):
    token = "agi_" + "s" * 43
    seen = []
    def response(request):
        import json
        seen.append(request.headers["Authorization"])
        return httpx.Response(201, json=json.loads(request.content))
    actual_client = httpx.Client
    monkeypatch.setenv("AGAPAY_STATION_INGEST_TOKEN", token)
    monkeypatch.setattr(simulate_http, "parse_args", simulator_args)
    monkeypatch.setattr(simulate_http.httpx, "Client", lambda **kw: actual_client(transport=httpx.MockTransport(response), **kw))
    assert simulate_http.main() == 0
    assert seen == ["Bearer " + token] * 2
    captured = capsys.readouterr()
    assert token not in captured.out + captured.err
