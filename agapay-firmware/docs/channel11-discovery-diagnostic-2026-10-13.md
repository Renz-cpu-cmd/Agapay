# Channel 11 ESP32 discovery investigation — October 13, 2026

Firmware build and host tests passed. No physical scan, upload, reset, flash/NVS
erase, credential change, region change or broker/backend/dashboard/ML change
was performed by the agent. The actual cause remains unestablished.

## Findings

The supplied device scan detected five APs but neither intended SSID. This
demonstrates some Wi-Fi reception; the original log did not show the detected
AP channels, current country range or raw driver scan completion status. It
therefore cannot establish a channel 11 failure or target compatibility issue.
The laptop's signal percentage is evidence about its own receiver/location,
not the ESP32 antenna/receiver. A scan does not authenticate with the AP.

The reported target snapshots are:

| Known SSID | Expected BSSID | Reported channel/security |
| --- | --- | --- |
| <router> | <router-bssid> | 11, WPA2-Personal |
| <phone-hotspot> | <earlier-hotspot-bssid> | 11, WPA2-Personal |

BSSIDs are diagnostic references, not association settings. Hotspot BSSIDs may
change across sessions. A name match with a different BSSID is logged separately
from a BSSID match whose returned SSID is hidden/different. No unrelated name
is printed in either case. `same_AP=FOUND` requires both matches in one record.

## Installed API and task investigation

Installed Arduino-ESP32 is **2.0.17**, on PlatformIO Espressif32 7.1.3. The
[versioned scan implementation](https://github.com/espressif/arduino-esp32/blob/2.0.17/libraries/WiFi/src/WiFiScan.cpp)
accepts `scanNetworks(async, show_hidden, passive, max_ms_per_chan, channel)`.
Channel 0 requests all configured channels; channel 11 requests that channel.
The old call was synchronous from the application task but internally started
an asynchronous driver scan and waited up to 10 seconds for its completion.
The old active maximum dwell was 300 ms per channel.

The wrapper collects driver AP records through its SCAN_DONE handler and
returns a count without exposing the event's success/failure field. The new
diagnostic records that raw field through the existing event callback, under
the same short diagnostic mutex. Printing occurs in the network task. A bounded
100 ms wait accommodates the framework signaling completion before invoking
the application callback; absent callback evidence is labeled unknown. The
driver status 0 means success; nonzero means failure, not proof of who stopped
the scan. A failed/partial result cannot prove an AP is absent.

The [ESP-IDF Wi-Fi guide](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32/api-guides/wifi.html#esp32-wi-fi-scan)
distinguishes active probe scanning from passive beacon reception, and explains
that association can conflict with scanning. In this firmware, discovery runs
in the network task before the retry loop, first `WiFi.begin`, and MQTT setup.
No sensor/ISR/local-output code calls scan, scan-stop, disconnect or Wi-Fi mode
changes. The sensor task remains independent. No firmware task cancellation
was identified; runtime driver/scheduling behavior still requires physical logs.

`esp_wifi_get_country` reads the live driver country code, first channel, channel
count and policy; the upper channel is first + count - 1. This patch never calls
a country setter or expands a range. If the current range excludes channel 11,
the explicit scans are skipped and that finding is printed. If querying fails,
it prints the error and still asks the driver to scan; driver restrictions remain.
The actual board's country settings have not been observed by the agent.

## Exact changes

The once-per-boot sequence now performs:

1. Read/print STA MAC and current country range/policy/error.
2. **FULL** active scan: all channels, 300 ms maximum dwell per channel.
3. **CH11-ACTIVE** scan: channel 11, 600 ms maximum dwell.
4. **CH11-PASSIVE** scan: channel 11, 1000 ms beacon-listening dwell.
5. Release results after each stage and proceed to existing association/retries.

Both explicit channel scans include hidden AP records and use no SSID/BSSID
scan filters. The passive dwell provides a longer observation window even if
an AP does not answer active probes. Dwell settings remain within the installed
driver's documented 1500 ms per-channel limit. No AP/security/radio setting is
changed to force a result.

For every record, each stage prints anonymous AP index/channel/RSSI. Additional
authentication/BSSID metadata is printed only for a known SSID or known BSSID
match, using the known label rather than an unrelated returned name. Each stage
summarizes the number of APs reporting channel 11, missing result records, and
independent SSID/BSSID/same-record matches for both targets.

Errors retain their numeric scan/cleanup codes. If a scan fails, the diagnostic
requests scan stop and checks the framework scan state with bounded yielding
before advancing. `cleanup_requested=1` marks raw events that could result from
this deliberate cleanup; do not misattribute those to another task. If cleanup
state stays -1, subsequent scan results are inconclusive and the log preserves
that evidence. No repeated scans run during normal reconnection.

GPIO5/18 ultrasonic sensing, GPIO4 rain ISR, 0.70 mm/tip calibration, lifetime
NVS counter, sequence persistence, local LEDs/buzzer/thresholds, MQTT JSON/ACK
contracts and retry settings are retained. Network initialization lasts longer
for this one diagnostic sequence; local sensing and rain persistence continue.

Files edited for this task:

- `agapay-firmware/src/main.cpp`
- `agapay-firmware/tests/host_stubs.h`
- `agapay-firmware/tests/firmware_host_test.cpp`

File added: `agapay-firmware/docs/channel11-discovery-diagnostic-2026-10-13.md`.
The existing test runner and earlier reports were not edited for this task.

## Example output shape (illustrative, not board measurements)

```text
[WIFI SCAN] get_country=0 (ESP_OK)
[WIFI SCAN] country=CN start_channel=1 channel_count=13 last_channel=13 policy=0 (AUTO) channel11_in_range=1
[WIFI SCAN FULL] Starting mode=active channel=0 dwell_ms=300 before association
[WIFI SCAN FULL] result=5 elapsed_ms=... wifi_status_before=6 after=6
[WIFI SCAN FULL] completion_events=1 driver_status=0 (0=success; nonzero=failure) event_APs=5 scan_id=... cleanup_requested=0
[WIFI SCAN FULL] AP #1 channel=6 RSSI=-55 dBm
...
[WIFI SCAN FULL] Channel 11 APs visible=0 missing_records=0
[WIFI SCAN FULL] <router>: SSID=NOT SEEN BSSID=NOT SEEN same_AP=NOT SEEN
[WIFI SCAN FULL] <phone-hotspot>: SSID=NOT SEEN BSSID=NOT SEEN same_AP=NOT SEEN
[WIFI SCAN CH11-ACTIVE] Starting mode=active channel=11 dwell_ms=600 before association
...
[WIFI SCAN CH11-PASSIVE] Starting mode=passive channel=11 dwell_ms=1000 before association
...
[WIFI SCAN] Discovery finished; proceeding to normal connection attempts (no rescan)
```

## Decision guide after a complete physical capture

| Evidence | Interpretation |
| --- | --- |
| Country range excludes 11; explicit scans skipped | Regional configuration is a concrete lead. Preserve it and investigate how it was set; do not erase NVS or randomly override the country. |
| Target appears in explicit 11 scan but not full scan | The receiver can discover it on 11. Dwell/scan-mode/transient reception is a lead, not proof of a specific API bug. |
| Target appears only in passive scan | Beacon reception works; active-probe behavior/timing is a lead. Association/security/DHCP still need verification. |
| Other channel 11 APs appear but both known targets remain absent | Channel 11 discovery works at that moment. Investigate target visibility/advertising, BSSID changes, RF placement or AP-specific compatibility. |
| Known BSSID appears without its SSID | Check hidden/changed SSID. This is evidence of that radio's discovery despite no name match. |
| Known SSID appears with different BSSID | A same-named AP was seen, or the BSSID snapshot changed. It does not prove the particular Windows-observed radio was seen. |
| No 11 APs in either successful explicit scan, but other channels work and 11 is permitted | Channel-specific RF/driver/reception becomes a stronger lead. Position ESP32 close to a known enabled AP and repeat one controlled boot capture before concluding hardware failure. |
| Error, raw driver status nonzero, missing records or no completion evidence | Discovery may be failed/partial. Investigate driver/event state first; lack of target matches is inconclusive. |
| Target pair found, then connection still reports 201 | Discovery succeeded; investigate subsequent AP availability, connection filtering/compatibility and association timing. Scan visibility is not MQTT connectivity. |

## Verification and upload instructions

Executed successfully with the existing environments:

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware
& .\agapay-backend\.venv-ml\Scripts\python.exe .\agapay-firmware\tests\run_host_tests.py --cxx 'C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-backend/.venv-ml/Scripts/python.exe -m ziglang c++'
```

Final build passed: RAM **45,728/327,680 bytes**, flash **780,269/1,310,720 bytes**.
Firmware host checks passed full→channel-11 active→passive→association ordering,
scan dwell/channel arguments, once-per-boot behavior, anonymous logging, both
SSID/BSSID/pair checks (including hidden/mismatched/split records), country
range/error handling without changing settings, driver partial/missing events,
scan cleanup and all previous sensor/local-alert/debounce/NVS/reboot/retry/MQTT
ACK checks. Six telemetry and two rain snapshots pass existing JSON/FastAPI
contracts. Focused `git diff --check` passed. Physical RF results remain unknown.

To flash, first press **Ctrl+C in the current COM9 Serial Monitor** and ensure
the port is released. Then use these exact commands from repository root:

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -t upload --upload-port COM9
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio device monitor --port COM9 --baud 115200 --filter time --filter log2file
```

Use normal upload only; no erase/partition changes. Verify the persisted rain
count is its last legitimate value (45 or later), not reset. Capture all three
scan stages plus subsequent connection attempts in one uninterrupted session.
If startup was missed, record one deliberate EN reset with the monitor open;
the diagnostic runs once per boot rather than once per monitor attachment.
