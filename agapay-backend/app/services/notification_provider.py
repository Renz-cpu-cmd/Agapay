"""Network boundary. No Firebase SDK, credentials, or real sends in this foundation."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from app.config import Settings


class SendOutcome(str, Enum):
    ACCEPTED = "accepted"
    RETRYABLE_REJECTION = "retryable_rejection"  # Confirmed NOT accepted.
    PERMANENT_REJECTION = "permanent_rejection"
    INVALID_TOKEN = "invalid_token"
    DISABLED = "disabled"
    TEST_ONLY = "test_only"
    UNKNOWN = "unknown"  # Timeout/crash may follow provider acceptance.


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    data: dict[str, str]


@dataclass(frozen=True)
class PushTarget:
    provider: str
    token: str = field(repr=False)


class NotificationProvider(Protocol):
    mode: str

    def send(self, target: PushTarget, message: PushMessage, *, delivery_key: str) -> SendOutcome:
        """Bound the network timeout. Never log secrets.

        ACCEPTED means provider acceptance, not device receipt. Retry only a
        rejection KNOWN not to have been accepted. The key is not an FCM
        exactly-once guarantee.
        """
        ...


class NoopNotificationProvider:
    mode = "disabled"

    def send(self, target: PushTarget, message: PushMessage, *, delivery_key: str) -> SendOutcome:
        return SendOutcome.DISABLED


class FakeNotificationProvider:
    """Test sink: no tokens retained and no real acceptance claimed."""
    mode = "test"

    def __init__(self):
        self.messages: dict[str, PushMessage] = {}

    def send(self, target: PushTarget, message: PushMessage, *, delivery_key: str) -> SendOutcome:
        self.messages.setdefault(delivery_key, message)
        return SendOutcome.TEST_ONLY


def configured_provider(settings: Settings) -> NotificationProvider:
    if settings.notification_provider != "disabled":
        raise ValueError("FCM adapter is not implemented; keep notification provider disabled.")
    return NoopNotificationProvider()
