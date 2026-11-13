"""Optional real broker test: private ephemeral listener and synthetic credentials.

Never reads/reloads an existing broker, uses demo ports, or publishes to a device.
"""
import json
from pathlib import Path
import shutil
import socket
import subprocess
import threading
from uuid import uuid4

import paho.mqtt.client as mqtt
import pytest

BROKER = shutil.which("mosquitto") or ("C:/Program Files/mosquitto/mosquitto.exe" if Path("C:/Program Files/mosquitto/mosquitto.exe").is_file() else None)
PASSWD = shutil.which("mosquitto_passwd") or ("C:/Program Files/mosquitto/mosquitto_passwd.exe" if Path("C:/Program Files/mosquitto/mosquitto_passwd.exe").is_file() else None)
pytestmark = pytest.mark.skipif(not BROKER or not PASSWD, reason="Optional broker ACL integration requires locally installed Mosquitto")


def test_station_broker_acl_rejects_anonymous_wrong_password_cross_station_and_spoofed_ack(tmp_path):
    password = "synthetic-" + uuid4().hex
    password_file = tmp_path / "passwords"
    for index, user in enumerate(("STATION_A", "STATION_B", "backend-ingest")):
        subprocess.run([PASSWD, "-b", *(["-c"] if index == 0 else []), str(password_file), user, password],
                       check=True, capture_output=True)
    acl = Path(__file__).parents[1] / "deploy/mosquitto/station-ingest.acl"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config = tmp_path / "broker.conf"
    config.write_text(f"listener {port} 127.0.0.1\nallow_anonymous false\npassword_file {password_file.as_posix()}\nacl_file {acl.as_posix()}\npersistence false\nmessage_size_limit 4096\n", encoding="utf-8")
    log = (tmp_path / "broker.log").open("w")
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}
    process = subprocess.Popen([BROKER, "-c", str(config)], stdout=log, stderr=log, **kwargs)
    clients = []
    try:
        ready = threading.Event()
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail("Isolated broker failed to start; inspect its test-only broker.log")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=.1): break
            except OSError:
                ready.wait(.05)
        else:
            pytest.fail("Isolated test broker did not become ready")

        def connect(user=None, secret=None, accepted=True):
            connected = threading.Event()
            outcome = []
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="acl-test-" + uuid4().hex)
            if user is not None: client.username_pw_set(user, secret)
            def on_connect(c, u, flags, reason, props):
                outcome.append(not reason.is_failure)
                connected.set()
            client.on_connect = on_connect
            client.connect("127.0.0.1", port)
            client.loop_start()
            clients.append(client)
            assert connected.wait(5) and outcome == [accepted]
            return client

        connect(accepted=False)
        connect("STATION_A", "wrong-test-password", accepted=False)
        backend, station = connect("backend-ingest", password), connect("STATION_A", password)
        backend_messages, device_messages = [], []
        backend_done, device_done = threading.Event(), threading.Event()
        backend.on_message = lambda c, u, m: (backend_messages.append((m.topic, m.payload)), backend_done.set() if m.payload == b"water-sentinel" else None)
        station.on_message = lambda c, u, m: (device_messages.append((m.topic, m.payload)), device_done.set() if m.payload == b"ack-sentinel" else None)

        def subscribe(client, topics):
            subscribed = threading.Event()
            client.on_subscribe = lambda *args: subscribed.set()
            client.subscribe(topics)
            assert subscribed.wait(5)

        subscribe(backend, [("agapay/stations/+/telemetry", 1), ("agapay/stations/+/rain", 1)])
        # A broker may grant this subscription while filtering reads at delivery.
        subscribe(station, [("agapay/stations/STATION_A/rain-ack", 1), ("agapay/stations/STATION_B/rain-ack", 1)])
        station.publish("agapay/stations/STATION_B/telemetry", b"cross-station", qos=1).wait_for_publish(5)
        station.publish("agapay/stations/STATION_A/rain-ack", b"spoofed-ack", qos=1).wait_for_publish(5)
        station.publish("agapay/stations/STATION_A/telemetry", b"water-sentinel", qos=1).wait_for_publish(5)
        assert backend_done.wait(5)
        backend.publish("agapay/stations/STATION_B/rain-ack", b"other-station-ack", qos=1).wait_for_publish(5)
        backend.publish("agapay/stations/STATION_A/telemetry", b"backend-forgery", qos=1).wait_for_publish(5)
        backend.publish("agapay/stations/STATION_A/rain-ack", b"ack-sentinel", qos=1).wait_for_publish(5)
        assert device_done.wait(5)
        backend_done.clear()
        station.publish("agapay/stations/STATION_A/telemetry", b"water-sentinel", qos=1).wait_for_publish(5)
        assert backend_done.wait(5)
        assert all(value == b"water-sentinel" for _, value in backend_messages)
        assert device_messages == [("agapay/stations/STATION_A/rain-ack", b"ack-sentinel")]
    finally:
        for client in clients:
            client.disconnect()
            client.loop_stop()
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()
