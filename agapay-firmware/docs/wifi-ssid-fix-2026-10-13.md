# ESP32 Upstairs connection fixed — October 13, 2026

## Established root cause

The known router **00:16:78:A2:55:F0** advertises `"Upstairs "`, including a
trailing ASCII space. Its actual SSID is **9 bytes**:

```text
55 70 73 74 61 69 72 73 20
```

The original local firmware configuration used `"Upstairs"`, **8 bytes**:

```text
55 70 73 74 61 69 72 73
```

All three real scans returned the same nine-byte name at the verified BSSID on
channel 11, around -60/-61 dBm during this capture, with driver status 0.
This is a spelling/byte mismatch, not a hidden SSID or channel 11 reception
failure. The original comparison correctly rejected those different strings.
The scan advertised authentication mode 4 (mixed WPA/WPA2), and the laptop's
association reports WPA2-Personal. No security setting was weakened.

The smallest root-cause correction was adding that one space in ignored local
`agapay-firmware/include/secrets.h`:

```cpp
constexpr char WIFI_SSID[] = "Upstairs "; // Trailing space is required.
```

Wi-Fi and MQTT passwords were not printed or changed. The SSID was corrected
explicitly from the known router's captured bytes, rather than automatically
adopting names returned by nearby APs.

## Authorization and executed work

The initial request said not to upload automatically. The user subsequently
directed full PC control and to do the work through a fix; the assistant stated
that this authorized normal COM9 upload and physical capture. Two tested
images were uploaded: the diagnostic image and then the confirmed SSID fix.
Only the identified COM9 monitor processes were closed. Deliberate normal EN
resets were used to capture startup; no full-flash erase, NVS erase or partition
change occurred. The normal upload rewrote application/boot image sectors.

The laptop had reverted to `pangit` at <broker-lan-ip>, while the ESP32 and broker
were configured for the Upstairs LAN. Its existing saved Windows profile was
verified to contain SSID hex `557073746169727320`. A documented Windows Wi-Fi
API connection restored that same saved profile and verified the known BSSID;
the laptop received **192.168.0.16**. Credentials/profile configuration were
not changed. The CLI availability check had rejected that profile, while the
native saved-profile connection succeeded.

The original LAN broker (PID 24952) and API (PID 39512, with its Python parent)
were already running; they were left unchanged. A duplicate broker launch
terminated on port-in-use and did not replace the existing broker. No broker
configuration/ACL/password change was made. The existing dashboard was started
at port **3011**, with process-local API/origin settings; no dashboard files were
edited. Process IDs are snapshots, not persistent identifiers.

Automatic approval review rejected a proposed check for password reuse between
the firmware account and `backend-demo`. It was not executed or bypassed. The
existing authenticated backend provided the required durable-ingestion/ACK
evidence, and a read-only ACK subscription used only the already-verified
ESP32 account and its authorized rain-ACK topic. No further credential action
was required.

## Firmware diagnostics and controlled connection

For the known Upstairs BSSID only, logs now report:

- Bounded SSID length, hex bytes and escaped printable representation.
- The raw 32-byte SSID field, including NUL padding, to distinguish a genuinely
  empty field from a malformed/nonzero tail.
- Configured SSID length/bytes and exact equality classification.
- Layer-2 association/authentication mode and DHCP GOT_IP/LOST_IP events.

Control characters, quotes, backslashes and non-ASCII bytes are escaped. No
password is included. Names of unrelated APs remain undisclosed; the exception
for actual SSID bytes is limited to the explicitly known Upstairs BSSID.

The installed [Arduino-ESP32 2.0.17 implementation](https://github.com/espressif/arduino-esp32/blob/2.0.17/libraries/WiFi/src/WiFiSTA.cpp)
supports `WiFi.begin(ssid,password,channel,bssid,true)` and sets the BSSID filter.
The controlled path uses channel **11**, the verified BSSID, and the configured
SSID/password. It is eligible only after a successful driver scan sees that
BSSID on channel 11 with an empty field or exactly matching configured SSID.
A nonempty mismatch latches a block for that boot; later empty records cannot
silently override it. No returned SSID is copied into connection credentials.

The controlled attempt gets **30 seconds** before another explicit begin call,
preventing the previous 10-second retry from restarting DHCP during that window.
Event callbacks only copy evidence under a short mutex; Serial work remains in
the network task. Association reports the link/auth mode; authentication success
is inferred from the successful link event, while failures use driver disconnect
reasons. There is no separate per-handshake callback exposed by this patch.

All ultrasonic/rain GPIOs, thresholds, local alerts, active-low buzzer behavior,
0.70 mm/tip, sensor/network independence, NVS lifetime counter, telemetry/rain
schemas and ACK/deduplication contracts are retained. No ML model, backend
source, dashboard source, API schema, firewall rule or Wi-Fi country setting
was changed.

## Physical verification after the final normal reset

Times are Manila time, October 13:

```text
06:15:21 [RAIN] ... persisted_tips=54 calibration=0.700 mm/tip
06:15:27 [WIFI SSID FULL] configured_length=9 bytes_equal=1 classification=EXACT MATCH
06:15:28 [WIFI SSID CH11-ACTIVE] ... classification=EXACT MATCH
06:15:29 [WIFI SSID CH11-PASSIVE] ... classification=EXACT MATCH
06:15:29 [WIFI ASSOC] Link established auth_mode=4 channel=11 BSSID=00:16:78:A2:55:F0
06:15:31 [WIFI DHCP] GOT_IP: 192.168.0.14
06:15:31 [WIFI] Connected
06:15:32 [MQTT] Connected state=0 (broker accepted CONNACK)
06:15:32 [RAIN ACK] backend acknowledged count=54 boot=B8F6D10D5020-8DBF61AB-EE51B68A
06:15:41 [MQTT] First telemetry publication written ...
06:15:51 [NET] alive ... wifi=3 mqtt=1 state=0 stack_free_bytes=3484
```

A read-only query of the existing rain journal confirmed that same physical
boot/source and `boot_start=54,last_count=54`, with fresh persisted reception.
The normal reboot did not add or lose a tip. The existing API health and
dashboard returned **HTTP 200**. Continued real rain heartbeat snapshots and
telemetry were observed. No synthetic physical packet or artificial rain tip
was generated. A new mechanical tip-to-dashboard test is still an operator
action; this result verifies actual device connectivity, durable baseline
ingestion and ACK, not rain-volume calibration or a new physical tip.

Evidence files (ignored local data, no passwords):

- `data/live_rain/ssid-bssid-physical-20261013.log` — original byte mismatch.
- `data/live_rain/ssid-corrected-physical-20261013.log` — corrected identity,
  successful association/DHCP, followed by the separate LAN-path problem.
- `data/live_rain/ssid-corrected-mqtt-20261013.log` — running MQTT publication.
- `data/live_rain/ssid-fixed-end-to-end-20261013.log` — final startup and ACK.

COM9 is released. ESP32, original broker/API and dashboard remain running.
Dashboard: **http://127.0.0.1:3011/dashboard**. Laptop Wi-Fi must remain on the
existing `Upstairs ` profile with its trailing space for this LAN setup.

## Files changed and software verification

Edited for this request:

- `agapay-firmware/src/main.cpp` — SSID bytes, identity guard, BSSID association
  and association/DHCP diagnostics.
- `agapay-firmware/tests/host_stubs.h` — Wi-Fi link/BSSID connection fakes.
- `agapay-firmware/tests/firmware_host_test.cpp` — identity/escaping/guard/grace
  tests and preserved sensor/NVS/MQTT regressions.
- `agapay-firmware/include/secrets.h` — **one trailing space in SSID only**;
  remains Git-ignored, with no password changes.

Added: this report. Earlier worktree changes were preserved. No commit/push.

Final build **passed**: RAM 45,768/327,680 bytes; flash 782,277/1,310,720 bytes.
Firmware host tests **passed**, including byte escaping, 32-byte bounds,
hidden/exact/different SSID behavior, blocking later blank overrides, the
verified channel/BSSID and unchanged password, 30-second grace, event callback
logging independence, DHCP/link outcomes, sensors/alarms/debounce/NVS/reboot/
rain ACK behavior. Six telemetry and two rain payloads pass existing JSON Schema
and FastAPI contracts. Focused diff checks passed. An initial privacy fixture
incorrectly prohibited the newly requested known-BSSID name output; its scope
was corrected and the final suite passed before upload.

## Exact commands if another upload is needed

The corrected firmware is **already uploaded and physically verified**. To
repeat later, close the current COM9 monitor with Ctrl+C, then:

```powershell
Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -t upload --upload-port COM9
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio device monitor --port COM9 --baud 115200 --filter time --filter log2file
```

Do not trim the trailing space or erase NVS. Check the persisted counter against
its last legitimate value (54 at this verification, possibly later thereafter).
