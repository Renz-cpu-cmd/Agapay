# One-time ESP32 Wi-Fi discovery diagnostic — October 13, 2026

> **Update 2026-11-13.** Network names, access-point hardware addresses and LAN
> addresses in this record are replaced with role placeholders such as `<router>`.
> The firmware no longer compiles in any network identity, and no longer prints names,
> raw name bytes or BSSIDs. It now logs match results, lengths and near-match classes,
> for example "DIFFERS ONLY BY TRAILING WHITESPACE", which still diagnoses the root
> cause below. Optional access-point pinning moved to two settings in the ignored
> `secrets.h` (see `include/secrets.example.h`). The log lines quoted below show the
> October format.

Status: firmware build and host checks passed; the physical scan has not yet
been run by this agent. No upload, reset, flash/NVS erase or credential change
was performed. FastAPI, Mosquitto, ML and dashboard code were not changed.

## Findings

The local configured SSID is `<router>` and MQTT host is `<laptop-lan-ip>`.
The supplied physical log shows successful STA initialization followed by
reason 201 and `WL_NO_SSID_AVAIL`. It does not establish a password failure,
radio defect or firmware initialization defect.

The existing firmware initializes station mode once in the core-0 network task,
does not force a channel/BSSID, and has no explicit disconnect/reset on its
10-second retry path. MQTT is gated on Wi-Fi and is not responsible for Wi-Fi
discovery. No definite initialization defect was identified.

Installed Arduino-ESP32 is **2.0.17**. Its `WiFi.begin(ssid,password)` enables
STA, applies station configuration, initializes DHCP and requests connection.
It explicitly disconnects if the station configuration differs; the unchanged
configuration path has no explicit disconnect call. However, while waiting for
an IP, another `begin` reapplies configuration and its DHCP helper stops/restarts
the DHCP client. Thus a slow association/IP-acquisition attempt can overlap the
existing timed retry. This is a potential interaction, not an established cause
of the supplied 201 results. Retry timing/automatic reconnection were left
unchanged so discovery can be observed independently first.

See the official [2.0.17 station implementation](https://github.com/espressif/arduino-esp32/blob/2.0.17/libraries/WiFi/src/WiFiSTA.cpp)
and [scan implementation](https://github.com/espressif/arduino-esp32/blob/2.0.17/libraries/WiFi/src/WiFiScan.cpp).
The DHCP helper was also inspected in the installed framework's WiFiGeneric.cpp.

## Implemented behavior

Immediately after `WiFi.mode(WIFI_STA)` succeeds and before the first
`WiFi.begin`, the network task performs one active, all-channel scan with hidden
AP records included. This ESP32 radio operates on 2.4 GHz. Scan waiting occurs
only on the network task (the framework's synchronous wait is up to 10 seconds);
the sensor task, rain ISR and durable counter updates continue independently.

The scan prints STA MAC, numeric scan result, elapsed time, total AP count,
every exact configured-SSID match's RSSI/channel/authentication/BSSID, and
presence of the previous SSID `<phone-hotspot>`. Other SSIDs are never printed. Hidden
records count toward the total; a record without a reported SSID cannot be
identified as <router>/<phone-hotspot> merely from its blank name.

Scan result memory is deleted afterward. A negative scan result also requests
driver scan stop and logs that return code before normal association resumes.
STA initialization failure logs a skipped scan, rather than claiming no APs.
A boot-local guard prevents another scan during retries/reconnection. The
first connection retry timer starts after discovery finishes.

No sensor GPIO, local alarm, rain persistence, calibration, sequence, MQTT
schema/ACK contract, credential or retry setting was changed.

## Expected output (illustrative values, not a device observation)

```text
[WIFI] STA initialization: OK
[WIFI SCAN] ESP32 STA MAC: AA:BB:CC:DD:EE:FF
[WIFI SCAN] Starting one-time 2.4 GHz scan before association; target=<router>
[WIFI SCAN] result=8 elapsed_ms=4200
[WIFI SCAN] Networks detected: 8 (includes hidden APs)
[WIFI SCAN] Target <router>: RSSI=-48 dBm channel=11 auth=3 (WPA2_PSK) BSSID=11:22:33:44:55:66
[WIFI SCAN] Target <router>: FOUND; <phone-hotspot>: NOT SEEN
[WIFI SCAN] Discovery finished; proceeding to normal connection attempts (no rescan)
[WIFI] Connecting to SSID: <router> ...
```

Multiple <router> APs produce multiple metadata lines, so an SSID shared by
several access points can be distinguished by BSSID. No detected AP is pinned
as the connection target; normal association still chooses the AP.

## Interpreting results

| Observation | What it establishes / next investigation |
| --- | --- |
| `result > 0`, <router> FOUND | ESP32 receives a target AP in this scan. Compare auth/channel/BSSID/RSSI; subsequent failure concerns association/security/AP admission, intermittent reception or connection logic. Scan visibility does not authenticate or prove DHCP/MQTT. |
| `result > 0`, <router> NOT SEEN | ESP32 discovered other APs, but no exact target SSID was reported. Check SSID spelling/case, hidden SSID, AP availability, band/channel and reception at the ESP32. A password does not determine whether its advertised SSID appears. |
| <phone-hotspot> FOUND, <router> NOT SEEN | ESP32 can discover the hotspot at that moment; investigate <router> advertising/visibility/reception. This does not prove hotspot authentication. |
| <router> FOUND, <phone-hotspot> NOT SEEN | Expected if the old hotspot is off or out of range; <phone-hotspot> absence does not block <router>. |
| `result=0` | Scan returned zero APs. Check ESP32 proximity/antenna/RF, power stability and known nearby enabled 2.4 GHz APs. It does not by itself prove damaged hardware. |
| `result=-2` | Arduino scan failed or timed out. Discovery is unknown, not zero networks. The wrapper does not expose the underlying scan-start error; `scan_stop` is a separate cleanup result. |
| `result=-1` | Framework reported a scan already running. Unexpected in this fresh one-time startup path; investigate another scan/driver state. Discovery is unknown; cleanup is requested. |
| STA initialization FAILED / scan SKIPPED | Investigate radio/driver initialization before interpreting AP visibility. Normal begin retries still follow. |
| Target FOUND then reason 201 | Initial discovery worked. Inspect security compatibility/AP filtering, changing AP availability and the timing of begin/disconnect events; do not call this proof of a dead radio or wrong password. |

Authentication mode 3 is WPA2-Personal (`WPA2_PSK`); mode 4 is mixed WPA/WPA2,
5 is enterprise, 6 is WPA3 and 7 mixed WPA2/WPA3. Numeric values are always
printed even for an unlisted mode. No security settings are weakened by this patch.

## Exact operator commands

Press **Ctrl+C in the existing COM9 monitor**, ensuring it returns to PowerShell
before upload. Then, from repository root:

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -t upload --upload-port COM9
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio device monitor --port COM9 --baud 115200 --filter time --filter log2file
```

Upload is operator-controlled. Use the normal upload only; never run erase or
change partitions. Verify the persisted rainfall counter remains its last
legitimate value (45 or later). Record startup once, including all WIFI SCAN
lines and the following association results. The scan occurs once per boot,
not once per monitor attachment. If startup was missed, record one deliberate
EN reset with the monitor open; do not repeatedly reconnect the monitor.

Build and host-test commands used:

```powershell
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware
& .\agapay-backend\.venv-ml\Scripts\python.exe .\agapay-firmware\tests\run_host_tests.py --cxx 'C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-backend/.venv-ml/Scripts/python.exe -m ziglang c++'
```

Both passed. Build: RAM **45,712 bytes**, flash **778,265 bytes**. Host checks
passed ordering (STA mode → scan → begin), exactly-once behavior, zero/failed/
running/skipped scans, target/previous SSID results, metadata, privacy, scan
cleanup, result indices beyond 255, and existing sensor/local-output/NVS/retry/
MQTT ACK tests. Six telemetry and two rain payloads still pass the existing
FastAPI contracts. These are software checks, not a physical RF result.

Files modified: `src/main.cpp`, `tests/host_stubs.h`,
`tests/firmware_host_test.cpp`, `tests/run_host_tests.py`.
File added: this report. Existing uncommitted work was preserved.
