"""Read-only laptop MQTT check using local secrets; never publishes sensor data."""
import ast
from pathlib import Path
import re
import socket
import sys
import time
import uuid

import paho.mqtt.client as mqtt


def main() -> int:
    source = (Path(__file__).resolve().parents[1] / "include/secrets.h").read_text()

    def value(name: str) -> str:
        match = re.search(r"constexpr\s+char\s+" + name + r'\[\]\s*=\s*("(?:[^"\\]|\\.)*")\s*;', source)
        if not match:
            raise ValueError("Unsupported secret declaration")
        return ast.literal_eval(match.group(1))

    host, user, password = value("MQTT_HOST"), value("MQTT_USERNAME"), value("MQTT_PASSWORD")
    port_match = re.search(r"constexpr\s+int\s+MQTT_PORT\s*=\s*(\d+)\s*;", source)
    if not port_match:
        raise ValueError("Unsupported port declaration")
    port = int(port_match.group(1))
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        print(f"[LAPTOP TCP] FAILED type={type(exc).__name__} errno={exc.errno} winerror={getattr(exc, 'winerror', None)}")
        return 1
    print(f"[LAPTOP TCP] Reachable {host}:{port}; testing MQTT authentication separately")
    connected, grants = [], []
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="agapay-debug-" + uuid.uuid4().hex[:12])
    client.connect_timeout = 3
    if user:
        client.username_pw_set(user, password)

    def on_connect(client, userdata, flags, reason_code, properties):
        connected.append(not reason_code.is_failure)
        print(f"[LAPTOP MQTT] CONNACK={reason_code}; username configured={bool(user)}")
        if not reason_code.is_failure:
            client.subscribe("agapay/stations/STATION_001/rain-ack", qos=1)

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        grants.append(bool(reason_codes) and all(not reason.is_failure for reason in reason_codes))
        print("[LAPTOP MQTT] Rain-ACK SUBACK=" + ", ".join(str(reason) for reason in reason_codes))

    client.on_connect, client.on_subscribe = on_connect, on_subscribe
    try:
        client.connect(host, port, keepalive=15)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            client.loop(timeout=0.2)
            if grants or (connected and not connected[0]):
                break
    except OSError as exc:
        print(f"[LAPTOP MQTT] Transport failed type={type(exc).__name__} errno={exc.errno}")
        return 1
    finally:
        client.disconnect()
    if not connected or not grants:
        print("[LAPTOP MQTT] No successful CONNACK/SUBACK pair before timeout")
        return 1
    print("Laptop check only: ESP32 Wi-Fi, topic delivery and backend ingestion still require device/broker logs.")
    return 0 if connected[0] and grants[0] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, SyntaxError):
        # Do not emit an exception/traceback containing a secret declaration.
        print("Could not read local MQTT configuration; check secrets.h declarations. No secrets printed.")
        sys.exit(1)
