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
args = parser.parse_args()
build = firmware / ".pio" / "host-tests"
stubs = build / "stubs"
(stubs / "freertos").mkdir(parents=True, exist_ok=True)
header = (firmware / "tests" / "host_stubs.h").as_posix()
for name in ("Arduino.h", "WiFi.h", "Preferences.h", "PubSubClient.h", "secrets.h",
             "freertos/FreeRTOS.h", "freertos/queue.h", "freertos/task.h"):
    (stubs / name).write_text(f'#include "{header}"\n', encoding="utf-8")
json_include = args.arduinojson or firmware / ".pio/libdeps/esp32doit-devkit-v1/ArduinoJson/src"
if not json_include.is_dir():
    raise SystemExit("Run python -m platformio run -d agapay-firmware first to install ArduinoJson.")
exe = build / ("firmware_host_test.exe" if os.name == "nt" else "firmware_host_test")
command = shlex.split(args.cxx) + ["-std=c++17", "-Wall", "-Wextra", "-Werror",
    "-I" + str(stubs), "-I" + str(json_include),
    str(firmware / "tests/firmware_host_test.cpp"), "-o", str(exe)]
with (build / "compiler.log").open("w") as log:
    compiled = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
if compiled.returncode:
    print((build / "compiler.log").read_text(errors="replace")[-8000:])
    raise SystemExit(compiled.returncode)
result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
print(result.stderr.strip())

import jsonschema
sys.path.insert(0, str(firmware.parent / "agapay-backend"))
from app.schemas import TelemetryCreate
schema = json.loads((firmware / "docs/mqtt-telemetry.schema.json").read_text())
validator = jsonschema.Draft202012Validator(schema)
payloads = [json.loads(line) for line in result.stdout.splitlines()]
assert len(payloads) == 6
last_sequence = 0
for payload in payloads:
    validator.validate(payload)
    TelemetryCreate.model_validate(payload)
    assert payload["sequence_no"] > last_sequence > -1
    last_sequence = payload["sequence_no"]
assert {p["rainfall_mm"] for p in payloads} == {0, 0.7, 1.4}
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
