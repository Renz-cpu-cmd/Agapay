# Firmware credential review

A targeted scan of tracked source assignments found a plaintext Wi-Fi network name and password in `sketch_sep19a/sketch_sep19a.ino`, including the existing committed version. Values are intentionally not reproduced. The working sketch now includes the ignored `agapay-firmware/include/secrets.h`; useful historical logic remains intact.

Rotate the exposed Wi-Fi password. Removing it from the current tree does not remove it from Git history, remote copies, or clones. No history rewrite was performed. A history cleanup would need a separate coordinated decision.

`git check-ignore agapay-firmware/include/secrets.h` confirms the local credential file is ignored; it is not tracked. The committed template contains placeholders/empty optional authentication only. The final scan covered 314 tracked paths. Other assignment-pattern matches were synthetic backend/mobile test credentials or UI password-field labels, not additional identified live credentials. The scan excluded binary assets and did not print values. A pattern-based tracked-source scan is not an exhaustive forensic scan of every Git object, binary, or external service.

The canonical firmware preserves optional MQTT username/password configuration, but its existing `WiFiClient` transport is unencrypted and has no TLS certificate validation. Public anonymous brokers remain dummy-data development infrastructure only.
