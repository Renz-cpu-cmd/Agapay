import argparse
import random

from simulator.simulate_http import SCENARIOS, readings, scenario_reading


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
    assert [payload["device_uptime_ms"] for payload in payloads] == [0, 2000, 4000, 6000]
    assert all(payload["firmware_version"] == "0.2.0-simulator" for payload in payloads)
