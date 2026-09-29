"""Firebase Admin HTTP v1 adapter; never log SDK exceptions or credentials."""
import re
from uuid import uuid4

import firebase_admin
from firebase_admin import credentials, exceptions, messaging, _http_client
from google.auth.transport.requests import AuthorizedSession
from urllib3.util.retry import Retry

from app.config import Settings
from app.services.notification_provider import PushMessage, PushTarget, SendOutcome


class _NoReplayJsonHttpClient(_http_client.JsonHttpClient):
    def request(self, method, url, **kwargs):
        # Requests follows 307/308 with another POST unless redirects are disabled.
        if method.lower() == "post":
            kwargs["allow_redirects"] = False
        return super().request(method, url, **kwargs)


def _presend_retry_policy() -> Retry:
    # urllib3 treats ConnectTimeoutError (including NewConnectionError) as
    # connection errors assumed to occur before the request is sent. Read,
    # status, redirect and other failures may follow acceptance.
    return Retry(total=1, connect=1, read=False, redirect=0, status=0,
                 other=0, respect_retry_after_header=False)


class FirebaseNotificationProvider:
    mode = "fcm"
    allowed_keys = {"type", "alert_id", "severity", "station_id", "status"}

    def __init__(self, settings: Settings):
        self._app = None
        try:
            if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", settings.firebase_project_id):
                raise ValueError("Invalid project ID")
            credential = (
                credentials.Certificate(settings.firebase_credentials_path)
                if settings.firebase_credentials_path else credentials.ApplicationDefault()
            )
            # Resolve ADC now, so missing credentials fail before claiming outbox work.
            google_credential = credential.get_credential()
            self._app = firebase_admin.initialize_app(
                credential, {"projectId": settings.firebase_project_id, "httpTimeout": 15},
                name=f"agapay-push-{uuid4()}",
            )
            # Admin SDK 7.6.0 has no public per-send retry option. Its default
            # retries reads and 500/503 responses, which can duplicate a push.
            # Keep its official serialization/auth/send path, but permit one
            # retry only for a connection failure urllib3 classifies as occurring
            # before the request is sent. Never follow POST redirects.
            service = messaging._get_messaging_service(self._app)
            session = AuthorizedSession(
                google_credential, refresh_timeout=15, max_refresh_attempts=0,
            )
            client = _NoReplayJsonHttpClient(
                session=session, retries=_presend_retry_policy(), timeout=15,
            )
            service._client.close()
            service._client = client
        except Exception:
            if self._app is not None:
                try:
                    firebase_admin.delete_app(self._app)
                except Exception:
                    pass  # Cleanup must not expose an SDK/credential exception either.
            raise ValueError("FCM configuration unavailable or invalid; check project and credentials.") from None

    def send(self, target: PushTarget, message: PushMessage, *, delivery_key: str) -> SendOutcome:
        if (target.provider != "fcm" or not target.token
                or set(message.data) != self.allowed_keys
                or any(not isinstance(value, str) for value in message.data.values())
                or message.data.get("type") != "SENSOR_ESCALATION"):
            return SendOutcome.PERMANENT_REJECTION
        try:
            result = messaging.send(messaging.Message(
                token=target.token,
                notification=messaging.Notification(title=message.title, body=message.body),
                data=dict(message.data),
                android=messaging.AndroidConfig(priority="high"),
            ), app=self._app)
            return SendOutcome.ACCEPTED if result else SendOutcome.UNKNOWN
        except messaging.UnregisteredError:
            return SendOutcome.INVALID_TOKEN
        except (messaging.SenderIdMismatchError, messaging.ThirdPartyAuthError,
                exceptions.InvalidArgumentError, exceptions.PermissionDeniedError,
                exceptions.UnauthenticatedError):
            # InvalidArgument can mean a malformed payload, not an invalid token.
            return SendOutcome.PERMANENT_REJECTION
        except exceptions.FirebaseError as error:
            # SDK error types vary with the provider response body. Only a
            # confirmed 429/503 response can be retried by the bounded worker.
            # A transport error without a response may follow acceptance.
            response = error.http_response
            if response is not None and response.status_code in (429, 503):
                return SendOutcome.RETRYABLE_REJECTION
            return SendOutcome.UNKNOWN
        except Exception:
            # Includes timeout, transport, internal error, and unexpected errors.
            # Do not retain exception text: it can contain tokens/credential paths.
            return SendOutcome.UNKNOWN
