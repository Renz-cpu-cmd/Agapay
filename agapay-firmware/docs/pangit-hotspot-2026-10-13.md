# AGAPAY pangit hotspot switch — October 13, 2026

The requested hotspot connection is uploaded and running. No passwords are
included in this report. The verified cardboard-demo firmware profile is preserved.

## Observed connection

| Component | Verified result |
| --- | --- |
| Laptop Wi-Fi | pangit, quality100%, DHCP<broker-lan-ip> |
| ESP32 Wi-Fi | pangit, WPA2-PSK, channel11, approximately -48 dBm |
| Current hotspot BSSID | 1E:2F:4C:96:D9:6D |
| ESP32 DHCP | 10.224.134.252 |
| ESP32 MQTT | state0, connected to<broker-lan-ip>:1883 |
| Backend MQTT | same broker at127.0.0.1:1884, authenticated existing backend-demo account |
| Rain counter after normal reset | persisted148; boot baseline148 |
| Actual device ACK | backend acknowledged count148 for the new boot |
| Local outputs | BENCH DISTANCE profile, same GPIOs and LOW-trigger buzzer |
| API/dashboard | responding; physical rainfall panel Connected and forecast updating |

The earlier Android BSSID in the one-time diagnostic differs from the hotspot's
current BSSID. That historical BSSID is not used to pin pangit association.
The actual SSID match and normal configured SSID/password association succeeded.

The rain journal was at132 before the network change, then loaded148 from
onboard NVS after upload. No synthetic rain tips or sensor packets were generated.
The retained counter increased during the interval without backend connectivity;
individual physical tips in that interval were not independently observed here.

## Exact scope

- Updated only locally ignored `agapay-firmware/include/secrets.h` Wi-Fi SSID,
  supplied Wi-Fi password and MQTT_HOST address. MQTT credentials are unchanged.
- Changed ignored `data/live_rain/broker/mosquitto.conf` listening endpoints to
  the new hotspot LAN IP1883 and loopback1884. Existing password/ACL files and
  authenticated-account permissions are unchanged. The unrelated stock loopback
  broker on1883 was left running.
- Restarted the existing isolated demo API with its own original AGAPAY settings
  and account credentials retained only in memory; changed its MQTT endpoint to
  loopback1884. Same demo DB, rain journal, sessions, models and disabled
  notification provider. No API, dashboard or broker application code changed.
- Added ignored migration helpers and read-only database/config backups under
  `data/live_rain/network_switch`. Wi-Fi profile XML is not written by the helper;
  Windows saves the requested profile normally. No credentials were printed,
  guessed, reused across accounts, rotated or written to these migration files.
- Installed psutil7.2.2 in the existing `.venv-ml` environment for same-service
  configuration preservation and endpoint diagnostics. No requirements file changed.
- Built and normally uploaded `esp32-cardboard-demo` throughCOM9. No erase-flash
  command, partition-layout change, NVS reset or rainfall-calibration change.

## Verification and evidence

The hotspot firmware build passed: RAM45,848/327,680 bytes;
flash784,969/1,310,720 bytes. Migration helpers passed py_compile.
The read-only laptop MQTT check received CONNACK Success and Rain-ACK SUBACK QoS1.
Established sockets separately confirmed the real device at10.224.134.252
and API atloopback1884 on the same managed broker.

One normal reset captured actual pangit connection, association, DHCP, MQTT
acceptance and the device's real backend ACK together in
`data/live_rain/pangit-hotspot-startup-20261013.log`. The final heartbeat reported
Wi-Fi3, MQTT1, state0. COM9 was released after the capture.

Dashboard observation at08:48 AM PHT: physical rain gauge Connected, current-hour
rain25.200 mm, fresh measured sensor depth61.4 cm, and historical-context
demonstration forecast updates. These are observed counts/calculated values;
physical calibration remains a separate task.

Normal future upload, from the project root after closing any COM9 monitor:

```powershell
& .\agapay-backend\.venv-ml\Scripts\python.exe -m platformio run -d agapay-firmware -e esp32-cardboard-demo -t upload --upload-port COM9
```

For an intentional later API restart, use the existing startup script with
`-BrokerHost 127.0.0.1 -BrokerPort 1884`; enter the same backend account's
credentials locally when prompted. Do not run a second API while port8000 is occupied.
Keep the laptop and hotspot on for MQTT/API/dashboard operation. Recheck laptop
DHCP before another network change; the ESP32 broker address is locally configured.

The native Wi-Fi helper follows Microsoft's documented
[WlanSetProfile](https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/nf-wlanapi-wlansetprofile)
and [WlanConnect](https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/nf-wlanapi-wlanconnect)
APIs because this machine's netsh wlan commands were unavailable.
