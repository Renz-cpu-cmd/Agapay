"""Read COM9 without toggling reset; optional bounded local-output command.

No synthetic sensor readings, MQTT publications, rainfall tips or NVS writes.
Close other Serial Monitors before use. pyserial is included with PlatformIO.
"""
import argparse
from pathlib import Path
import sys
import time

import serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM9")
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--command", choices=("ALERT STATUS", "ALERT TEST", "ALERT STOP", "ALERT DEMO ON", "ALERT DEMO OFF"))
    parser.add_argument("--command-delay", type=float, default=2)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120 or not 0 <= args.command_delay < args.seconds:
        parser.error("seconds must be 1-120; command-delay must be within the monitoring interval")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    port = serial.Serial(port=None, baudrate=115200, timeout=.2)
    port.dtr = False
    port.rts = False
    log = None
    try:
        if args.log:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            log = args.log.open("w", encoding="utf-8")
        port.port = args.port
        port.open()
        port.reset_input_buffer()
        start = time.monotonic()
        sent = False
        while time.monotonic() - start < args.seconds:
            if args.command and not sent and time.monotonic() - start >= args.command_delay:
                port.write((args.command + "\n").encode("ascii"))
                sent = True
                print("[MONITOR] sent " + args.command, flush=True)
            line = port.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if log:
                log.write(line + "\n")
                log.flush()
            if any(tag in line for tag in ("[LOCAL", "[CALIBRATION", "[SENSOR]", "[NET]", "[RAIN ACK]")):
                print(line, flush=True)
    finally:
        port.close()
        if log:
            log.close()


if __name__ == "__main__":
    main()
