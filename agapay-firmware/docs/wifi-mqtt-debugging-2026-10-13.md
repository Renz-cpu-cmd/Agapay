# ESP32 Wi-Fi/MQTT debugging — October 13, 2026

Physical connectivity remains **UNVERIFIED** until COM9 and the LAN broker show
the actual device connected and a physical tip is durably acknowledged.

## Findings from this debugging session

- Laptop Wi-Fi is connected to `pangit`, 2.4 GHz/channel 11, WPA2-Personal;
  IPv4 `<broker-lan-ip>/24`, gateway `10.224.134.61`, Public firewall profile.
- Local `secrets.h` has that SSID/broker address, `<mqtt-username>`, and nonempty
  passwords. Passwords were never printed or changed. The Windows stored
  hotspot key could not be retrieved for a comparison; verify it on the phone.
- Before edits, `secrets.h` was dated 02:56:12 and `firmware.bin` 02:57:40
  on October 13 (Manila). This supports a build after the secret edit, but
  cannot prove which binary is on the device. Updated firmware logs its build time.
- Authenticated laptop probe using the firmware MQTT credentials returned
  `CONNACK=Success` and rain-ACK `SUBACK=Granted QoS 1`. It publishes no data.
  This verifies the current password against the running broker from the laptop.
- LAN broker PID 12636 was launched with this repository's
  `data/live_rain/broker/mosquitto.conf -v`; listener is `<broker-lan-ip>:1883`.
  A separate process also listens on loopback `127.0.0.1:1883`/`::1:1883`.
  Use the LAN address for the ESP32 and demo backend. PIDs/addresses are snapshots.
- Two enabled Public-profile inbound allow rules target Mosquitto. This does
  not prove a peer device traverses the firewall or phone client isolation.
- ACL allows ESP32 writes to STATION_001 telemetry/rain and reads of rain-ACK;
  backend reads telemetry/rain and writes ACK. Backend ACK is sent only after
  durable journal ingestion, with validation/deduplication already implemented.
- Installed platform: Espressif32 7.1.3; Arduino-ESP32 **2.0.17**;
  ArduinoJson 7.4.3; PubSubClient 2.8.0. Diagnostic event types and disconnect
  fields were checked against these installed framework sources and compiled.
- No physical Serial Monitor was opened, device reset/upload performed,
  password/broker/firewall configuration changed, or physical event generated.

## Root cause and ranked remaining hypotheses

The supplied Serial excerpt cannot establish the device's connection failure.
It shows that local sensors and the network report-consumption path ran.

1. **Wi-Fi association/authentication/DHCP failure.** Phone previously showed
   only the laptop. Check the exact phone SSID/password, device access/blocklist,
   connected-client limit and 2.4 GHz WPA2 settings. Firmware now logs `begin`,
   status, IP, RSSI and disconnect reason. An authentication reason is evidence
   to investigate credentials/security; it is not proof of a wrong password.
2. **Uploaded configuration differs from the current build.** Build timestamps
   reduce suspicion of an old local binary; upload identity is still unverified.
3. **Hotspot peer isolation or inbound path restrictions**, if Wi-Fi gets an IP
   but MQTT state is `-2`/`-4`. Laptop-local TCP/CONNACK tests cannot establish
   ESP32-to-laptop reachability. Match Serial IP/client ID to the LAN broker log.
4. **Intermittent resets or runtime task failure.** No brownout has been shown.
   Compare complete boot markers, new rain boot IDs and increasing uptime.
5. **Current broker credential/listener mismatch** is less likely because the
   laptop probe passed. Revisit if the board reports state `4`/`5`, or DHCP,
   broker configuration, credentials or uploaded build changed after this check.

Actual implementation issues corrected: a failed new-count rain publish could
repeat at every 10 ms task iteration; it now waits 500 ms for the same count.
New persisted tips still publish promptly. Failed ACK subscription writes retry
every 5 seconds. Rain-queue allocation failure is now checked before starting
the network task. None of these is claimed as the Wi-Fi root cause.

## Diagnostic behavior

- Wi-Fi starts immediately at task initialization; explicit `WiFi.begin` retries
  remain 10 seconds apart with uptime/elapsed interval shown. Framework automatic
  reconnection remains enabled as before and may generate events between those
  explicit attempts. Disconnect callbacks only record evidence under a short
  lock; Serial reporting is outside the callback, at most once per 10 seconds.
- Wi-Fi status changes are rate limited; connect/disconnect transitions and
  assigned IP/RSSI are reported. The network task reports health/uptime/minimum
  free stack **bytes** every 30 seconds (ESP-IDF uses bytes for this API).
- MQTT attempts remain 5 seconds apart and gated on Wi-Fi; only the network
  task owns MQTT. Existing 1-second MQTT socket timeout and 15-second keepalive
  remain. TCP connection latency is separate from MQTT's socket-response timeout.
- MQTT logs broker, configured-auth presence, client ID, CONNACK failure state,
  disconnect/retry, initialization/buffer failure and first telemetry write.
- ACK request logging says **request sent**, not broker authorization confirmed.
  PubSubClient does not expose SUBACK grants to this firmware. QoS 0 publish
  success confirms a write, not backend acceptance or topic ACL permission.
  The actual backend ACK and broker logs provide stronger evidence.
- Existing telemetry/rain fields, GPIO5/18 ultrasonic sensing, GPIO4 interrupt,
  provisional 0.70 mm/tip, lifetime NVS, sequence persistence, local output
  thresholds and sensor/network task separation are retained. Failed rain writes
  keep the cumulative counter; no flash/NVS erase is needed.

| MQTT state | Meaning / next evidence |
| --- | --- |
| -4 | MQTT broker-response timeout; check broker log and peer route |
| -3 | TCP connection lost; check disconnect/reset and broker log |
| -2 | TCP connect failed; cannot distinguish unreachable, refused, DNS or firewall from this code alone |
| -1 | Disconnected |
| 0 | MQTT CONNACK accepted; topic delivery still needs proof |
| 1 / 2 / 3 | Broker refused protocol / client ID / unavailable |
| 4 | Broker refused username/password |
| 5 | Broker refused connection authorization; separate from topic ACL |

Codes follow the [PubSubClient 2.8 definitions](https://github.com/knolleary/pubsubclient/blob/v2.8/src/PubSubClient.h).
Wi-Fi reasons include 201 NO_AP_FOUND, 202 AUTH_FAIL, 203 ASSOC_FAIL,
15/204 handshake timeout, and 200 beacon timeout. Preserve unknown numeric codes.

## Exact operator commands, in order

1. In the **existing COM9 monitor terminal**, press **Ctrl+C** (the installed
   PlatformIO monitor's default exit shortcut). This is a keypress, not a
   command to type at a PowerShell prompt. Close the
   serial tab/app if necessary; do not kill every Python process. Confirm you
   have returned to the PowerShell prompt before uploading.

2. Rebuild from repository root using the existing Python environment:

   ```powershell
   Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
   & .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware
   ```

3. **Operator upload required to get the new diagnostics**; no upload was done
   by the agent. This uploads the normal application image, preserving NVS:

   ```powershell
   & .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -t upload --upload-port COM9
   ```

   Do not run erase/erase_flash or change the partition layout. Check the next
   boot reports `persisted_tips=45` or a later legitimate count, never force it
   back to 45. If upload reports the port is busy, close its actual owner.

4. Open a 115200 baud monitor and save its output:

   ```powershell
   & .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio device monitor --port COM9 --baud 115200 --filter time --filter log2file
   ```

   PlatformIO reports the log filename. Keep this single session open for 60–90
   seconds. Do not repeatedly reconnect it while investigating reset fragments;
   serial DTR/RTS actions can reset a development board. If startup markers were
   missed, record one deliberate EN/reset separately and then watch uninterrupted.

5. Verify Wi-Fi: `[NET] ... task=created`, `[NET] Network task started`,
   `[WIFI] STA initialization: OK`, connection attempt to `pangit`, then
   `[WIFI] Connected` and a nonzero IP/RSSI. The phone must list the ESP32 too.
   If no IP appears, use status/reason to fix association/security/phone settings
   before diagnosing MQTT. Do not change multiple settings at once.

6. Verify MQTT: require `[MQTT] Connected state=0`, actual device client ID
   `AGAPAY_STATION_001_...` in the **LAN broker** log with the ESP32 source IP,
   first telemetry write, backend `Stored MQTT telemetry STATION_001/...`, and
   a baseline `[RAIN ACK] backend acknowledged ...`. A laptop check is also
   available in a **second PowerShell terminal**:

   ```powershell
   Set-Location 'C:\Users\Asus\OneDrive\Documents\Agapay\Agapay'
   & .\agapay-backend\.venv-auth\Scripts\python.exe .\agapay-firmware\tools\check_mqtt_connection.py
   Get-NetTCPConnection -LocalPort 1883 | Select-Object LocalAddress,RemoteAddress,State,OwningProcess
   ```

   The script reads local secrets in memory, uses a unique laptop client ID,
   prints CONNACK/SUBACK, disconnects and publishes nothing. It does not prove
   device association or delivery. Keep the existing broker/backend running.

7. Inspect the **currently running LAN Mosquitto terminal** (already uses `-v`).
   It writes to its console; the existing config has no `log_dest file`.
   Match new connection/client/username, received PUBLISH rain/telemetry,
   backend ACK PUBLISH and delivery to the ESP32; inspect denied authentication
   or publish messages. Check the effective listener/config without changing it:

   ```powershell
   Get-Content .\data\live_rain\broker\mosquitto.conf
   Get-Content .\data\live_rain\broker\acl
   Get-CimInstance Win32_Process -Filter "name = 'mosquitto.exe'" | Select-Object ProcessId,ExecutablePath,CommandLine
   ```

   Do not show/copy `passwd` or `secrets.h`. Do not start a duplicate broker on
   the LAN address. If a saved log is needed, **only after** Ctrl+C in that LAN
   broker's terminal, restart the same config in that terminal with capture:

   ```powershell
   & 'C:\Program Files\mosquitto\mosquitto.exe' -c .\data\live_rain\broker\mosquitto.conf -v 2>&1 | Tee-Object -FilePath .\data\live_rain\broker\network-debug-20261013.log -Append
   ```

   Then in another terminal:

   ```powershell
   Get-Content .\data\live_rain\broker\network-debug-20261013.log -Tail 80 -Wait
   ```

   This brief deliberate interruption can also verify automatic reconnection.
   Expect continued local sensing, then MQTT reconnection/ACK subscription and
   cumulative recovery. Restart the current broker only; leave other services
   alone. Do not disable firewall/authentication to make the test pass.

8. First physical rain event: leave the Serial, LAN broker and FastAPI terminals
   visible. Open the authenticated [dashboard](http://127.0.0.1:3011/dashboard)
   and choose STATION_001/physical source per the existing live-rain runbook.
   Record baseline counter **C**; if still 45, C=45. Move the installed bucket
   through **exactly one mechanical tip** with its existing verified interface.
   No software publisher or command can substitute for that physical action.
   Expect local durable count C+1, rain publish C+1, broker delivery, backend
   `[RAIN ACK] ... count=C+1` (rate limited; allow the next heartbeat), and an
   accepted physical increment of **0.70 mm** in the dashboard/journal. A fresh
   post-boot session with baseline 45 should show count 46 and session 0.70 mm;
   existing session totals may differ, so compare the increment. Repeated
   snapshots/heartbeats must not add that tip again. Preserve all journals/NVS.

For reset investigation, repeated complete `[BOOT]` markers, changed rain
boot IDs and uptime restarting in one uninterrupted capture demonstrate actual
reboots. `esp_reset_reason=9` supports brownout; 4/6/7 suggest panic/watchdog.
`rst:0x1` fragments alone do not establish brownout or even distinct reboots.

## Verification commands

Observed final outcomes:

- PlatformIO build **passed**: RAM 45,712/327,680 bytes; flash
  776,309/1,310,720 bytes. The diagnostic image was built, not uploaded.
- Firmware host/contract checks **passed**, including sensor/depth filtering,
  independent local alerts, debounce, NVS failure/recovery/reboot, ACK,
  retry intervals/wrap, callback log rate limits, subscription failures and
  queue/task allocation failures. Six telemetry and two rain payloads passed
  existing validators.
- Backend MQTT/rain regression suite **11 passed**, two existing FastAPI/
  Starlette deprecation warnings, 65.06 seconds. A 45-second diagnostic stack
  dump showed the long continuous-coverage test committing its SQLite fixture;
  it subsequently completed successfully.
- Laptop TCP/CONNACK/rain-ACK SUBACK check **passed**, with no sensor publication.
- Focused `git diff --check` **passed**.

Initial restricted build/compiler-cache attempts hit permissions; successful
reruns used the installed tool/cache with approved access. The first restricted
backend test run was stopped. One premature overlapping retry failed on the
shared test database lock; after stopping only this task's original test
processes, the single final run passed. Live databases/services were untouched.

Files edited for this task: `src/main.cpp`, `tests/host_stubs.h`,
`tests/firmware_host_test.cpp`. Files added: `tools/check_mqtt_connection.py`
and this debugging report. Other pre-existing worktree changes were preserved.
`platformio.ini`, secret files, backend source/config, model, API and dashboard
were inspected or left as-is, with no changes for this patch.

```powershell
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware
& .\agapay-backend\.venv-ml\Scripts\python.exe .\agapay-firmware\tests\run_host_tests.py --cxx 'C:/Users/Asus/OneDrive/Documents/Agapay/Agapay/agapay-backend/.venv-ml/Scripts/python.exe -m ziglang c++'
Push-Location .\agapay-backend
& .\.venv-auth\Scripts\python.exe -m pytest tests/test_mqtt_subscriber.py tests/test_rain_gauge.py -q --basetemp .pytest_cache/network-debug-20261013 --tb=short
Pop-Location
```

Run backend tests singly; they share a disposable test database. Their fixture
disables real MQTT and uses `tests/agapay_test.db`, separate from live databases.
Host tests use fake GPIO/NVS/networking and validate six telemetry and two rain
JSON payloads against existing FastAPI contracts. They also exercise bounded
retries, event callbacks, authentication failure logs, subscription retry,
counter preservation and queue/task allocation failures.

Provide the uninterrupted device serial capture and matching LAN Mosquitto
lines before claiming physical integration complete. Do not share passwords.
