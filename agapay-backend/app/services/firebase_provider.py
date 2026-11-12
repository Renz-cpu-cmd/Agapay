"""Firebase Admin HTTP v1 adapter; never log SDK exceptions or credentials."""
import re
from uuid import uuid4
from datetime import datetime,timedelta,timezone

import firebase_admin
from firebase_admin import credentials, exceptions, messaging, _http_client
from google.auth.transport.requests import AuthorizedSession
from urllib3.util.retry import Retry

from app.config import Settings
from app.services.notification_provider import PushMessage, PushTarget, SendOutcome, ProviderResult


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

    def send(self,target:PushTarget,message:PushMessage,*,delivery_key:str)->SendOutcome:
        return self.send_with_evidence(target,message,delivery_key=delivery_key).outcome

    def send_with_evidence(self, target: PushTarget, message: PushMessage, *, delivery_key: str) -> ProviderResult:
        if isinstance(message.data, dict) and message.data.get("type") == "EXERCISE_TEST":
            return self._send_exercise(target, message, delivery_key)
        if (target.provider != "fcm" or not target.token
                or not self.allowed_keys.issubset(message.data)
                or not set(message.data).issubset(self.allowed_keys|{'delivery_id','attempt_no','receipt_token','expires_at','audience','authority_id'})
                or any(not isinstance(value, str) for value in message.data.values())
                or message.data.get("type") != "SENSOR_ESCALATION"):
            return ProviderResult(SendOutcome.PERMANENT_REJECTION)

        def build():
            now=datetime.now(timezone.utc)
            expires=datetime.fromisoformat(message.data['expires_at'].replace('Z','+00:00')) if message.data.get('expires_at') else now+timedelta(minutes=5)
            if expires.tzinfo is None or expires<=now:return ProviderResult(SendOutcome.DISABLED)
            ttl=min(timedelta(hours=1),expires-now)
            return messaging.Message(
                token=target.token,
                notification=messaging.Notification(title=message.title, body=message.body),
                data=dict(message.data),
                android=messaging.AndroidConfig(priority="high",ttl=ttl),
                apns=messaging.APNSConfig(headers={"apns-expiration":str(int(expires.timestamp()))}),
            )
        return self._dispatch(build)

    # EXERCISE_TEST: a separate, narrow branch. Only a delivery already claimed by the
    # audited exercise service, for a still-eligible allowlisted device, with exactly
    # the service-built content, reaches the SDK. Token target only: no topics,
    # conditions, subscriptions or citywide audiences. One SDK call per delivery here.
    exercise_session_factory = None
    exercise_ttl = timedelta(minutes=10)

    def _send_exercise(self, target: PushTarget, message: PushMessage, delivery_key: str) -> ProviderResult:
        from app.services.exercise_notifications import provider_send_problem
        sent = self.__dict__.setdefault("_exercise_sent", set())
        if target.provider != "fcm" or not target.token or message.data.get("delivery_id") in sent:
            return ProviderResult(SendOutcome.PERMANENT_REJECTION)
        try:
            category, _reason = provider_send_problem(message, target.token, delivery_key, self.exercise_session_factory)
        except Exception:
            return ProviderResult(SendOutcome.PERMANENT_REJECTION)  # Fail closed before any SDK call.
        if category == "disabled":
            return ProviderResult(SendOutcome.DISABLED)
        if category:
            return ProviderResult(SendOutcome.PERMANENT_REJECTION)
        sent.add(message.data["delivery_id"])
        expires = datetime.now(timezone.utc) + self.exercise_ttl
        return self._dispatch(lambda: messaging.Message(
            token=target.token,
            notification=messaging.Notification(title=message.title, body=message.body),
            data=dict(message.data),
            android=messaging.AndroidConfig(priority="high", ttl=self.exercise_ttl),
            apns=messaging.APNSConfig(headers={"apns-expiration": str(int(expires.timestamp()))}),
        ))

    def _dispatch(self, build) -> ProviderResult:
        try:
            built = build()
            if isinstance(built, ProviderResult):
                return built
            result = messaging.send(built, app=self._app)
            return ProviderResult(SendOutcome.ACCEPTED,result if isinstance(result,str) and re.fullmatch(r'projects/[A-Za-z0-9_-]+/messages/[A-Za-z0-9%:_./-]{1,180}',result) else None) if result else ProviderResult(SendOutcome.UNKNOWN)
        except messaging.UnregisteredError:
            return ProviderResult(SendOutcome.INVALID_TOKEN)
        except (messaging.SenderIdMismatchError, messaging.ThirdPartyAuthError,
                exceptions.InvalidArgumentError, exceptions.PermissionDeniedError,
                exceptions.UnauthenticatedError):
            # InvalidArgument can mean a malformed payload, not an invalid token.
            return ProviderResult(SendOutcome.PERMANENT_REJECTION)
        except exceptions.FirebaseError as error:
            # SDK error types vary with the provider response body. Only a
            # confirmed 429/503 response can be retried by the bounded worker.
            # A transport error without a response may follow acceptance.
            response = error.http_response
            if response is not None and response.status_code in (429, 503):
                return ProviderResult(SendOutcome.RETRYABLE_REJECTION)
            return ProviderResult(SendOutcome.UNKNOWN)
        except Exception:
            # Includes timeout, transport, internal error, and unexpected errors.
            # Do not retain exception text: it can contain tokens/credential paths.
            return ProviderResult(SendOutcome.UNKNOWN)
