"""Firebase Admin HTTP v1 adapter; never log SDK exceptions or credentials."""
import re
from uuid import uuid4

import firebase_admin
from firebase_admin import credentials, exceptions, messaging, _http_client
from google.auth.transport.requests import AuthorizedSession

from app.config import Settings
from app.services.notification_provider import PushMessage, PushTarget, SendOutcome


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
            # Admin SDK 7.6.0 has no public per-send retry option. Its default retries
            # POSTs after read errors/500/503, which can duplicate accepted pushes.
            # Isolate this pinned, tested private seam; all serialization/auth/send
            # still uses the official SDK. No transport or 401 replay is permitted.
            service = messaging._get_messaging_service(self._app)
            session = AuthorizedSession(
                google_credential, refresh_timeout=15, max_refresh_attempts=0,
            )
            client = _http_client.JsonHttpClient(session=session, retries=False, timeout=15)
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
        except (messaging.QuotaExceededError, exceptions.UnavailableError) as error:
            # Only an explicit provider rejection is retryable. A synthesized
            # SDK exception without an HTTP response may follow acceptance.
            response = error.http_response
            if response is not None and response.status_code in (429, 503):
                return SendOutcome.RETRYABLE_REJECTION
            return SendOutcome.UNKNOWN
        except Exception:
            # Includes timeout, transport, internal error, and unexpected errors.
            # Do not retain exception text: it can contain tokens/credential paths.
            return SendOutcome.UNKNOWN
