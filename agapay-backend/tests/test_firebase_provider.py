from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
from threading import Thread
from time import sleep
from types import SimpleNamespace
from unittest.mock import Mock

import firebase_admin
import pytest
from firebase_admin import credentials, exceptions, messaging
from google.auth.credentials import AnonymousCredentials
import requests
from urllib3.connection import HTTPConnection
from urllib3.exceptions import NewConnectionError, ReadTimeoutError

from app.config import Settings
from app.services.firebase_provider import FirebaseNotificationProvider, _presend_retry_policy
from app.services.notification_provider import PushTarget, SendOutcome, configured_provider
from app.services.notification_service import message_for


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(credentials.ApplicationDefault, "get_credential", lambda _: AnonymousCredentials())
    value = configured_provider(Settings(notification_provider="fcm", firebase_project_id="agapay-test-project"))
    yield value
    firebase_admin.delete_app(value._app)


def payload():
    return message_for(SimpleNamespace(new_severity="EVACUATE", alert_id=12, station_id="STATION_TEST"))


def test_sdk_transport_bounded_and_no_automatic_replays(provider):
    service = messaging._get_messaging_service(provider._app)
    assert service._client.timeout == 15
    retry = service._client.session.get_adapter("https://").max_retries
    assert retry.total == retry.connect == 1
    assert retry.read is False
    assert retry.redirect == retry.status == retry.other == 0
    assert not retry.status_forcelist
    assert not retry.respect_retry_after_header
    assert "POST" not in retry.allowed_methods
    assert service._client.session._max_refresh_attempts == 0
    assert service._client.session._refresh_timeout == 15


def test_only_presend_connection_errors_can_retry():
    retry = _presend_retry_policy()
    after_connect = retry.increment(method="POST", error=NewConnectionError(None, "before send"))
    assert after_connect.total == after_connect.connect == 0
    with pytest.raises(ReadTimeoutError):
        retry.increment(method="POST", error=ReadTimeoutError(None, None, "after send"))
    assert not retry.is_retry("POST", 503, has_retry_after=True)
    assert not retry.is_retry("POST", 429, has_retry_after=True)


@contextmanager
def local_fcm(mode):
    """Exercise the real SDK/Requests path with fake tokens and no Firebase calls."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append(self.path)
            if mode == "reset":
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            if mode == "timeout":
                sleep(0.2)
            if mode == "redirect":
                self.send_response(307)
                self.send_header("Location", self.path)
                self.end_headers()
                return
            status = mode if isinstance(mode, int) else 200
            body = (json.dumps({"error": {"code": status, "message": "rejected",
                                          "status": "RESOURCE_EXHAUSTED" if status == 429 else "UNAVAILABLE"}})
                    if status != 200 else json.dumps({"name": "projects/test/messages/accepted"}))
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                if status == 429:
                    self.send_header("Retry-After", "1")
                self.end_headers()
                self.wfile.write(body.encode())
            except OSError:  # The timeout test closes its client connection first.
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/messages:send", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


@pytest.mark.parametrize("mode,expected", [
    (200, SendOutcome.ACCEPTED),
    (429, SendOutcome.RETRYABLE_REJECTION),
    (503, SendOutcome.RETRYABLE_REJECTION),
    ("timeout", SendOutcome.UNKNOWN),
    ("reset", SendOutcome.UNKNOWN),
    ("redirect", SendOutcome.UNKNOWN),
])
def test_real_sdk_http_path_never_replays_a_post(provider, monkeypatch, caplog, mode, expected):
    service = messaging._get_messaging_service(provider._app)
    with local_fcm(mode) as (url, received):
        monkeypatch.setattr(service, "_fcm_url", url)
        if mode == "timeout":
            monkeypatch.setattr(service._client, "_timeout", 0.05)
        result = provider.send(PushTarget("fcm", "secret-test-token"), payload(), delivery_key="one")
    assert result == expected
    assert len(received) == 1
    assert "secret-test-token" not in caplog.text


def test_pre_send_connection_failure_retries_without_duplicate_post(provider, monkeypatch):
    service = messaging._get_messaging_service(provider._app)
    connect = HTTPConnection._new_conn
    attempts = []

    def fail_first_connect(connection):
        attempts.append(1)
        if len(attempts) == 1:
            raise NewConnectionError(connection, "connection not established")
        return connect(connection)

    monkeypatch.setattr(HTTPConnection, "_new_conn", fail_first_connect)
    with local_fcm(200) as (url, received):
        monkeypatch.setattr(service, "_fcm_url", url)
        result = provider.send(PushTarget("fcm", "test-token"), payload(), delivery_key="one")
    assert result == SendOutcome.ACCEPTED
    assert len(attempts) == 2
    assert len(received) == 1


def test_acceptance_and_safe_payload(provider, monkeypatch):
    send = Mock(return_value="projects/test/messages/accepted")
    monkeypatch.setattr(messaging, "send", send)
    assert provider.send(PushTarget("fcm", "test-token"), payload(), delivery_key="one") == SendOutcome.ACCEPTED
    message = send.call_args.args[0]
    assert message.token == "test-token"
    assert set(message.data) == FirebaseNotificationProvider.allowed_keys
    assert all(isinstance(v, str) for v in message.data.values())
    assert message.notification.title == "AGAPAY EVACUATE-level sensor alert"
    assert "follow official local authority instructions" in message.notification.body
    assert "official evacuation order" not in message.notification.body.lower()
    assert send.call_count == 1


@pytest.mark.parametrize("error, expected", [
    (messaging.UnregisteredError("secret"), SendOutcome.INVALID_TOKEN),
    (messaging.SenderIdMismatchError("secret"), SendOutcome.PERMANENT_REJECTION),
    (messaging.ThirdPartyAuthError("secret"), SendOutcome.PERMANENT_REJECTION),
    (exceptions.InvalidArgumentError("secret"), SendOutcome.PERMANENT_REJECTION),
    (exceptions.PermissionDeniedError("secret"), SendOutcome.PERMANENT_REJECTION),
    (exceptions.UnauthenticatedError("secret"), SendOutcome.PERMANENT_REJECTION),
    (exceptions.DeadlineExceededError("secret"), SendOutcome.UNKNOWN),
    (exceptions.InternalError("secret"), SendOutcome.UNKNOWN),
    (exceptions.UnavailableError("secret"), SendOutcome.UNKNOWN),
    (requests.Timeout("secret"), SendOutcome.UNKNOWN),
    (RuntimeError("secret"), SendOutcome.UNKNOWN),
])
def test_outcomes_sanitize_errors(provider, monkeypatch, caplog, error, expected):
    send = Mock(side_effect=error)
    monkeypatch.setattr(messaging, "send", send)
    assert provider.send(PushTarget("fcm", "secret-token"), payload(), delivery_key="one") == expected
    assert send.call_count == 1
    assert "secret" not in caplog.text


@pytest.mark.parametrize("kind,status", [(messaging.QuotaExceededError, 429), (exceptions.UnavailableError, 503)])
def test_only_confirmed_rejections_retry(provider, monkeypatch, kind, status):
    response = requests.Response()
    response.status_code = status
    monkeypatch.setattr(messaging, "send", Mock(side_effect=kind("rejected", http_response=response)))
    assert provider.send(PushTarget("fcm", "test"), payload(), delivery_key="one") == SendOutcome.RETRYABLE_REJECTION


def test_extra_data_never_leaves_provider(provider, monkeypatch):
    send = Mock()
    monkeypatch.setattr(messaging, "send", send)
    message = payload()
    message.data["telemetry_id"] = "private"
    assert provider.send(PushTarget("fcm", "test"), message, delivery_key="one") == SendOutcome.PERMANENT_REJECTION
    send.assert_not_called()


@pytest.mark.parametrize("project", ["", "invalid project", "UPPERCASE"])
def test_invalid_project_fails_closed(project):
    with pytest.raises(ValueError, match="configuration unavailable or invalid"):
        configured_provider(Settings(notification_provider="fcm", firebase_project_id=project))


def test_invalid_explicit_credentials_do_not_fall_back(monkeypatch):
    adc = Mock()
    monkeypatch.setattr(credentials, "ApplicationDefault", adc)
    with pytest.raises(ValueError) as caught:
        configured_provider(Settings(notification_provider="fcm", firebase_project_id="agapay-test-project", firebase_credentials_path="private-missing-file.json"))
    assert "private-missing" not in str(caught.value)
    adc.assert_not_called()


def test_adc_failure_is_safe(monkeypatch):
    monkeypatch.setattr(credentials, "ApplicationDefault", Mock(side_effect=RuntimeError("secret credential")))
    with pytest.raises(ValueError) as caught:
        configured_provider(Settings(notification_provider="fcm", firebase_project_id="agapay-test-project"))
    assert "secret" not in str(caught.value)


def test_disabled_never_initializes_firebase(monkeypatch):
    init = Mock(side_effect=AssertionError("must not initialize"))
    monkeypatch.setattr(firebase_admin, "initialize_app", init)
    assert configured_provider(Settings(notification_provider="disabled")).mode == "disabled"
    init.assert_not_called()


def test_initialization_and_cleanup_errors_are_sanitized(monkeypatch):
    monkeypatch.setattr(credentials.ApplicationDefault, "get_credential", lambda _: AnonymousCredentials())
    monkeypatch.setattr(firebase_admin, "initialize_app", Mock(return_value=object()))
    monkeypatch.setattr(messaging, "_get_messaging_service", Mock(side_effect=RuntimeError("secret SDK error")))
    monkeypatch.setattr(firebase_admin, "delete_app", Mock(side_effect=RuntimeError("secret cleanup error")))
    with pytest.raises(ValueError) as caught:
        configured_provider(Settings(notification_provider="fcm", firebase_project_id="agapay-test-project"))
    assert "secret" not in str(caught.value)
