from types import SimpleNamespace
from unittest.mock import Mock

import firebase_admin
import pytest
from firebase_admin import credentials, exceptions, messaging
from google.auth.credentials import AnonymousCredentials
import requests

from app.config import Settings
from app.services.firebase_provider import FirebaseNotificationProvider
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
    assert service._client.session.get_adapter("https://").max_retries.total == 0
    assert service._client.session._max_refresh_attempts == 0
    assert service._client.session._refresh_timeout == 15


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
