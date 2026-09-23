"""Transactional intent creation; bounded worker operates outside ingestion."""
from datetime import timedelta
import logging

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (Alert, AlertTransition, AuthSession, NotificationDevice,
                        NotificationDelivery, NotificationEvent, User, utc_now)
from app.services.alert_classifier import SEVERITY_ORDER
from app.services.notification_provider import NotificationProvider, PushMessage, PushTarget, SendOutcome

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def eligible_devices():
    return (select(NotificationDevice)
            .join(User, User.id == NotificationDevice.user_id)
            .join(AuthSession, AuthSession.token_hash == NotificationDevice.session_hash)
            .where(NotificationDevice.enabled.is_(True), User.is_active.is_(True), User.role == "resident",
                   AuthSession.user_id == User.id, AuthSession.expires_at > utc_now()))


def device_is_eligible(db: Session, device: NotificationDevice) -> bool:
    return db.scalar(eligible_devices().where(NotificationDevice.id == device.id)) is not None


def disable_device(device: NotificationDevice) -> None:
    device.enabled = False
    device.provider_token = None
    device.token_hash = None
    device.revision += 1


def enqueue_transition(db: Session, transition: AlertTransition) -> None:
    """Inside the alert transaction. Escalations only; no network/commit.

    Capture eligible recipients now. Newly registered devices never replay old
    alerts. Even zero-recipient escalations retain a durable event.
    """
    if SEVERITY_ORDER[transition.new_severity] <= SEVERITY_ORDER[transition.previous_severity]:
        return
    if db.scalar(select(NotificationEvent.id).where(NotificationEvent.transition_id == transition.id)):
        return
    event = NotificationEvent(transition_id=transition.id)
    db.add(event)
    db.flush()
    for device in db.scalars(eligible_devices()):
        db.add(NotificationDelivery(event_id=event.id, device_id=device.id,
                                   user_id=device.user_id, device_revision=device.revision))


def message_for(transition: AlertTransition) -> PushMessage:
    severity = transition.new_severity
    body = ("High flood risk detected. Prepare to evacuate and follow official local authority instructions."
            if severity == "EVACUATE" else
            "Flood sensor level has increased. Check the AGAPAY community alert and local authority guidance.")
    return PushMessage(
        title=f"AGAPAY {severity}-level sensor alert", body=body,
        data={"type": "SENSOR_ESCALATION", "alert_id": str(transition.alert_id),
              "severity": severity, "station_id": transition.station_id, "status": "ACTIVE"},
    )


def process_pending(provider: NotificationProvider, *, limit: int = 50, session_factory=SessionLocal) -> int:
    """Bounded batch with atomic claims, no DB transaction during send.

    PROCESSING rows are never reclaimed automatically: a crash after provider
    acceptance cannot safely be distinguished from a crash before sending.
    Inspect/reconcile those rows without blind resend.
    """
    if not 1 <= limit <= 100:
        raise ValueError("Batch limit must be between 1 and 100")

    def ready():
        return or_(NotificationDelivery.state == "PENDING",
                   (NotificationDelivery.state == "FAILED") &
                   (NotificationDelivery.next_attempt_at <= utc_now()) &
                   (NotificationDelivery.attempts < MAX_ATTEMPTS))

    with session_factory() as db:
        ids = list(db.scalars(select(NotificationDelivery.id).where(ready())
                              .order_by(NotificationDelivery.id).limit(limit)))
    processed = 0
    for delivery_id in ids:
        with session_factory() as db:
            claimed = db.execute(update(NotificationDelivery).where(
                NotificationDelivery.id == delivery_id, ready()).values(
                    state="PROCESSING", attempted_at=utc_now(), next_attempt_at=None,
                    attempts=NotificationDelivery.attempts + 1))
            db.commit()
            if claimed.rowcount != 1:
                continue
            delivery = db.get(NotificationDelivery, delivery_id)
            device = db.get(NotificationDevice, delivery.device_id)
            event = db.get(NotificationEvent, delivery.event_id)
            transition = db.get(AlertTransition, event.transition_id)
            episode = db.get(Alert, transition.alert_id)
            newer = db.scalar(select(AlertTransition.id).where(
                AlertTransition.alert_id == episode.id, AlertTransition.id > transition.id).limit(1))
            suppressed = (not device_is_eligible(db, device) or
                          device.revision != delivery.device_revision or newer is not None)
            target = PushTarget(device.provider, device.provider_token or "")
            message = message_for(transition)
            fingerprint = (device.token_hash or "none")[:12]
        if suppressed:
            outcome = SendOutcome.DISABLED
            category = "ineligible_or_superseded"
        else:
            try:
                outcome = provider.send(target, message, delivery_key=f"agapay-delivery-{delivery_id}")
                if not isinstance(outcome, SendOutcome):
                    outcome = SendOutcome.UNKNOWN
            except Exception:
                # Exception strings/tracebacks may contain provider credentials.
                outcome = SendOutcome.UNKNOWN
            category = outcome.value
        with session_factory() as db:
            delivery = db.get(NotificationDelivery, delivery_id)
            delivery.provider_mode = provider.mode if provider.mode in ("disabled", "test", "fcm") else "custom"
            delivery.result_category = category
            delivery.state = {
                SendOutcome.ACCEPTED: "SENT" if provider.mode == "fcm" else "TESTED",
                SendOutcome.RETRYABLE_REJECTION: "FAILED",
                SendOutcome.PERMANENT_REJECTION: "FAILED",
                SendOutcome.INVALID_TOKEN: "FAILED",
                SendOutcome.DISABLED: "SUPPRESSED",
                SendOutcome.TEST_ONLY: "TESTED",
                SendOutcome.UNKNOWN: "UNKNOWN",
            }[outcome]
            if outcome == SendOutcome.RETRYABLE_REJECTION and delivery.attempts < MAX_ATTEMPTS:
                delivery.next_attempt_at = utc_now() + timedelta(seconds=30 * 2 ** (delivery.attempts - 1))
            else:
                delivery.completed_at = utc_now()
            if outcome == SendOutcome.INVALID_TOKEN:
                # Atomic revision guard: a concurrent token refresh must survive
                # an invalid-token response for the old registration.
                db.execute(update(NotificationDevice).where(
                    NotificationDevice.id == delivery.device_id,
                    NotificationDevice.revision == delivery.device_revision,
                ).values(enabled=False, provider_token=None, token_hash=None,
                         revision=NotificationDevice.revision + 1))
            db.commit()
            log.info("notification delivery=%s alert=%s severity=%s provider=%s token_fingerprint=%s state=%s result=%s",
                     delivery_id, message.data["alert_id"], message.data["severity"], delivery.provider_mode,
                     fingerprint, delivery.state, category)
        processed += 1
    return processed
