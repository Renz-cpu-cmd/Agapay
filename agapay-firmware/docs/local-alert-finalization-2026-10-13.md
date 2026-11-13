# AGAPAY local LEDs and buzzer — October 13, 2026

October 22 follow-up: firmware 0.3.0 uses the [F15/F16 v3 rainfall/configuration contract](../../agapay-docs/security/F15-F16/README.md). The current fallback is an explicitly unvalidated 150 cm bench geometry; historical 120 cm examples below remain archived context. No device was flashed or physically calibrated by this change.


## Finding

The original project bench sketch identifies the JSN-SR04T, a LOW-triggered
MH-FMD buzzer module, and these pins: TRIG5, ECHO18, rain4, buzzer25,
green26, yellow27, red14. The available saved project chats expose only their
recent turns; the complete older wiring discussion was not returned. Pin/model
details above come from the project's saved firmware, not a fresh wiring inspection.

The integrated firmware calculates depth as `120 - distance_cm` and uses
60/85/100 cm depth tiers. Accepted distances begin at 20 cm. Consequently red
requires a distance of exactly 20 cm with no range margin. Integer echo timing
is more restrictive: 1167 us produces approximately 20.01405 cm (99.98595 cm
depth, WARNING); 1166 us produces 19.9969 cm and is rejected. The old host test
used a synthetic exact-20 cm median and missed this real acquisition boundary.
The buzzer code already used the correct LOW-trigger polarity for the documented
module; it never received an automatic critical tier under those defaults.

## Explicit cardboard-demo correction

`esp32doit-devkit-v1` remains the default DEPTH firmware profile. The separate
`esp32-cardboard-demo` build starts with the original bench positions:

| Accepted sensor distance | Local bench output |
| --- | --- |
| Greater than 60 cm | Green; buzzer off |
| Greater than 35 through 60 cm | Yellow; buzzer off |
| Greater than 25 through 35 cm | Yellow; buzzer off |
| 20 through 25 cm | Red; GPIO25 LOW, buzzer on |

These positions are local cardboard demonstration zones, not calibrated flood
thresholds. The hardware's reliable range must still be physically checked.
The demo profile survives a reboot; its runtime mode overrides do not.
Invalid measurements retain the last valid local output; UNKNOWN at boot is
unlit with the buzzer off. Hold a flat target within a stable accepted range;
moving directly inside the 20 cm configured exclusion zone is not a valid red test.

No mounting-height/range/rainfall calibration, sensor GPIO, MQTT schema,
credentials, Wi-Fi country, backend alert threshold, model or NVS counter was
changed. Reported sensor depth still uses the original conversion. Thus bench
red at 25 cm corresponds to a reported 95 cm depth; the backend independently
classifies that as WARNING under its existing thresholds. Do not represent
the local bench red as a matching backend evacuation alert.

## Local diagnostic commands

Send each line over USB Serial at 115200 baud with a newline:

- `ALERT STATUS`: profile, last accepted distance, local tier and output GPIO
  readings, plus depth/bench thresholds and the default depth range-margin warning.
- `ALERT TEST`: manually invoked three-second GPIO test: green for one second,
  yellow for one second, then red+buzzer for one second. Returns to the latest
  valid sensor output; never changes measured depth, MQTT packets or rain counts.
- `ALERT STOP`: cancels the test and restores sensor outputs.
- `ALERT DEMO ON` / `ALERT DEMO OFF`: selects bench/depth local outputs for the
  current boot only. The build's profile resumes on reboot.

The test refuses to start at a critical local tier, cannot be extended by repeated
commands, and is immediately cancelled by a new critical sensor sample. Input is
bounded to 16 bytes per loop and a 47-character line; overflow/invalid bytes are
discarded. Tests do not wait or suspend sensor acquisition/rain persistence.
Reading the GPIO level does not prove that an LED emitted light or a buzzer sounded.

## Build and host verification

Both PlatformIO profiles compiled. RAM: 45,848/327,680 bytes. Flash: default
784,937/1,310,720 bytes; cardboard demo 784,973/1,310,720 bytes.
Both host profiles passed acquisition/filtering, the real pulse boundary
regression, unchanged depth during bench operation, all output GPIO tiers,
test restore/critical preemption, millis wrap, bounded input, Wi-Fi/MQTT gates,
rain persistence/ACK/reboot and six telemetry/two rain contract validations.
The Python monitor helper also passed `py_compile`.

From the project root, close any other COM9 monitor:

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -e esp32doit-devkit-v1 -e esp32-cardboard-demo
& .\agapay-backend\.venv-ml\Scripts\python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-backend/.venv-ml/Scripts/python.exe -m ziglang c++'
& .\agapay-backend\.venv-ml\Scripts\python.exe agapay-firmware/tests/run_host_tests.py --cxx 'C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-backend/.venv-ml/Scripts/python.exe -m ziglang c++' --bench-profile
```

Upload the explicit cardboard demo with the normal uploader (no erase-flash):

```powershell
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -e esp32-cardboard-demo -t upload --upload-port COM9
```

To return to the preserved depth profile, substitute `-e esp32doit-devkit-v1`.
Its 100 cm trigger still requires measured calibration to create reliable range
margin; this report does not invent a mounting height or flood threshold.

Monitor without deliberately toggling reset:

```powershell
& .\agapay-backend\.venv-ml\Scripts\python.exe agapay-firmware/tools/monitor_local_alerts.py --command 'ALERT STATUS' --seconds 15
& .\agapay-backend\.venv-ml\Scripts\python.exe agapay-firmware/tools/monitor_local_alerts.py --command 'ALERT TEST' --command-delay 7 --seconds 15
```

## Physical evidence so far

Before uploading, COM9 reported approximately 58.7 cm, 61.3 cm depth, tier2;
yellow was the intended output. The normal diagnostic upload succeeded and a
real device output test reported green (26=1), yellow (27=1), then red+buzzer
(14=1,25=0), followed by restoring yellow (14=0,25=1). Sensor acquisition and
MQTT state0 continued. The backend's new boot baseline remained132 with total132.
No synthetic tips or sensor packets were published.

The final `esp32-cardboard-demo` profile was subsequently uploaded normally on
COM9 with hashes verified. The live `ALERT STATUS` response confirmed
`mode=BENCH DISTANCE (demo only)`, distance61.74 cm, green26=1, red14=0,
buzzer25=1. Network health reported Wi-Fi3, MQTT1, state0. A repeated output
test reported red14=1/buzzer25=0 and restored green. The operator explicitly
confirmed: **Green, yellow, red and buzzer all worked**. This is physical
light/sound evidence for the output test; the separate automatic test is recorded below.

Logs are in the ignored `data/live_rain/local-alert-before-20261013.log` and
`local-alert-output-test-20261013.log`. Final demo logs are
`cardboard-alert-output-test-20261013.log`, `cardboard-alert-output-repeat-20261013.log`,
`cardboard-alert-final-status-20261013.log` and `cardboard-alert-automatic-test-20261013.log`.
The automatic physical target-position test then succeeded: an actual21.21 cm
reading (valid=1, reported depth98.79 cm, depth tier3) produced local bench tier4,
GPIO14=1 and GPIO25=0. Returning the target to61.79 cm restored local bench tier1,
GPIO26=1, GPIO14=0 and GPIO25=1. The operator replied 'it changed' to the requested
target-position test, matching these real sensor-driven transitions. This test
used no `ALERT TEST`, synthetic readings, MQTT injection or rainfall tips.
The final read-only backend check retained total132 and boot baseline132.
A reply of 'okay' alone was not counted as evidence of light/sound.

Files changed for this task: `src/main.cpp`, `platformio.ini`,
`tests/host_stubs.h`, `tests/firmware_host_test.cpp`, `tests/run_host_tests.py`,
`tools/monitor_local_alerts.py`, and this report. Earlier work remains preserved.
