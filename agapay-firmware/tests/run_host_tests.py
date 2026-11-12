"""Run actual firmware with host fakes; validate its real ArduinoJson output.

Requires: a C++17 compiler (or `python -m pip install ziglang`), PlatformIO
libraries installed by `pio run`, and a Python with jsonschema + backend deps.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

firmware = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--cxx", default=os.environ.get("CXX", "c++"), help="Compiler command, e.g. 'python -m ziglang c++'")
parser.add_argument("--arduinojson", type=Path, help="Optional existing ArduinoJson src directory")
parser.add_argument("--bench-profile", action="store_true", help="Compile the explicit cardboard-demo boot profile")
parser.add_argument("--unprovisioned", action="store_true", help="Verify missing-token publication fails closed while sensing continues")
parser.add_argument("--release-profile", action="store_true", help="Compile release TLS policy against synthetic host identities")
args = parser.parse_args()
build = firmware / ".pio" / "host-tests"
stubs = build / "stubs"
(stubs / "freertos").mkdir(parents=True, exist_ok=True)
header = (firmware / "tests" / "host_stubs.h").as_posix()
(stubs / "transport_policy.h").write_text((firmware / "include/transport_policy.h").read_text(encoding="utf-8"),encoding="utf-8")
(stubs / "station_config.h").write_text((firmware / "include/prototype_config.h").read_text(encoding="utf-8"),encoding="utf-8")
(stubs / "prototype_config.h").write_text((firmware / "include" / "prototype_config.h").read_text(encoding="utf-8"),encoding="utf-8")
for journal_header in ("depth_journal.h", "depth_storage.h"):
    (stubs/journal_header).write_text((firmware/"include"/journal_header).read_text(),encoding="utf-8")
for name in ("LittleFS.h", "Arduino.h", "WiFi.h", "Preferences.h", "PubSubClient.h", "secrets.h", "ingest_secrets.h", "esp_timer.h", "esp_system.h", "esp_wifi.h",
             "WiFiClientSecure.h", "release_secrets.h", "transport_secrets.h", "freertos/FreeRTOS.h", "freertos/queue.h", "freertos/task.h"):
    (stubs / name).write_text(f'#include "{header}"\n', encoding="utf-8")
json_include = args.arduinojson or firmware / ".pio/libdeps/esp32doit-devkit-v1/ArduinoJson/src"
if not json_include.is_dir():
    raise SystemExit("Run python -m platformio run -d agapay-firmware first to install ArduinoJson.")
exe = build / ("firmware_host_test.exe" if os.name == "nt" else "firmware_host_test")
command = shlex.split(args.cxx) + ["-std=c++17", "-Wall", "-Wextra", "-Werror",
    "-DAGAPAY_RELEASE_BUILD="+ ("1" if args.release_profile else "0"),
    "-DAGAPAY_LOCAL_DEVELOPMENT="+("0" if args.release_profile else "1"),
    "-DAGAPAY_LOCAL_BENCH_ALERTS=" + ("1" if args.bench_profile else "0"),
    *(["-DAGAPAY_HOST_UNPROVISIONED=1"] if args.unprovisioned else []),
    "-I" + str(stubs), "-I" + str(json_include),
    str(firmware / "tests/firmware_host_test.cpp"), "-o", str(exe)]
with (build / "compiler.log").open("w") as log:
    compiled = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
if compiled.returncode:
    print((build / "compiler.log").read_text(errors="replace")[-8000:])
    raise SystemExit(compiled.returncode)
result = subprocess.run([str(exe)], capture_output=True, text=True)
print(result.stderr.strip())
if result.returncode:
    raise SystemExit(result.returncode)
if args.unprovisioned:
    raise SystemExit(0)

import jsonschema
sys.path.insert(0, str(firmware.parent / "agapay-backend"))
from app.schemas import TelemetryCreate
schema = json.loads((firmware / "docs/mqtt-telemetry.schema.json").read_text())
validator = jsonschema.Draft202012Validator(schema)
envelopes = [json.loads(line) for line in result.stdout.splitlines() if not line.startswith("RAIN ")]
rain_envelopes=[json.loads(line[5:]) for line in result.stdout.splitlines() if line.startswith("RAIN ")]
from app.station_schemas import MqttRainEnvelope, MqttTelemetryEnvelope
ingress_schema = json.loads((firmware / "docs/mqtt-ingress.schema.json").read_text())
# Resolve the two trusted local inner schemas in-memory; never fetch remote refs.
ingress_schema["oneOf"][0]["properties"]["telemetry"] = schema
ingress_schema["$defs"] = schema.get("$defs",{})
ingress_schema["oneOf"][1]["properties"]["rain"] = json.loads((firmware / "docs/rain-gauge-event.schema.json").read_text())
envelope_validator = jsonschema.Draft202012Validator(ingress_schema)
for envelope in envelopes + rain_envelopes: envelope_validator.validate(envelope)
for envelope in envelopes: MqttTelemetryEnvelope.model_validate(envelope)
for envelope in rain_envelopes: MqttRainEnvelope.model_validate(envelope)
payloads = [envelope['telemetry'] for envelope in envelopes]
rain_payloads = [envelope['rain'] for envelope in rain_envelopes]
assert len(payloads) == 6
last_sequence = 0
for payload in payloads:
    validator.validate(payload)
    TelemetryCreate.model_validate(payload)
    assert payload["schema_version"] == 3 and payload["config_version"] == 1
    assert payload["source_id"] == "TEST_STATION_001" and payload["boot_sequence"] == 5001
    assert payload["boot_id"] == "STATION_001-5001"
    assert payload["measured_at"].endswith("Z")
    assert payload["device_uptime_ms"] > 2**32  # esp_timer uptime survives millis wrap
    assert payload["sequence_no"] > last_sequence > -1
    last_sequence = payload["sequence_no"]
assert all(p['rainfall_mm'] is None and p['rainfall_interval'] is None for p in payloads)
assert all(len(p['applied_config_hash'])==64 for p in payloads)
assert {p["sensor_quality"] for p in payloads} == {"valid", "invalid"}
# Check both validators reject the historical/raw-distance payload shape.
bad = dict(payloads[0], distance_cm=77.3)
for validate in (validator.validate, TelemetryCreate.model_validate):
    try:
        validate(bad)
    except (jsonschema.ValidationError, ValueError):
        pass
    else:
        raise AssertionError("Contract accepted forbidden raw distance field")
(build / "generated-telemetry.json").write_text(json.dumps(payloads, indent=2) + "\n")
print("PASS: all 6 firmware-generated valid/invalid and zero/one/two-tip JSON payloads satisfy JSON Schema and FastAPI TelemetryCreate; legacy extra fields rejected")
from app.rain_schemas import RainCounterEvent
assert len(rain_payloads)==2
for payload in rain_payloads:RainCounterEvent.model_validate(payload)
assert rain_payloads[0]['rainfall_increment_mm']==0.7
assert rain_payloads[1]['rainfall_increment_mm']==0
print("PASS: actual firmware rain snapshots satisfy FastAPI contract; debounce, offline retention, NVS failure/recovery, ACK and reboot baselines tested")
print("PASS: authentication envelopes satisfy local JSON Schema and FastAPI; credentials stay out of Serial logs")
