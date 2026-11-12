"""Transactional intent creation; bounded worker operates outside ingestion."""
from datetime import timedelta
from dataclasses import replace
import logging
import re

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (Alert, AlertTransition, NotificationDevice,
                        NotificationDelivery, NotificationEvent, User, utc_now)
from app.services.alert_classifier import SEVERITY_ORDER
from app.governance_models import AlertAuthority, CitywideDispatch, NotificationAudience
from app.services.alert_governance import audience_allows, capture_recipient, station_subscriptions
from app.services.notification_provider import NotificationProvider, PushMessage, PushTarget, SendOutcome
from app.operations_models import AccountPreference
from app.services.delivery_evidence import reviewed_condition,begin_attempt,lock_control
from app.delivery_models import DeliveryAttempt
from app.services.notification_provider import ProviderResult
from app.services.station_lifecycle import capture_gate,delivery_allowed
from app.services.station_security import utc

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def eligible_devices():
    return (select(NotificationDevice)
            .join(User, User.id == NotificationDevice.user_id)
            .outerjoin(AccountPreference,AccountPreference.user_id==User.id)
            .where(NotificationDevice.enabled.is_(True), User.is_active.is_(True), User.role == "resident",
                   or_(AccountPreference.user_id.is_(None),AccountPreference.notifications_enabled.is_(True)),
                   NotificationDevice.provider_token.is_not(None),
                   NotificationDevice.provider_token != "",
                   NotificationDevice.token_hash.is_not(None),
                   NotificationDevice.token_hash != ""))


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
    areas, subscriptions = station_subscriptions(db, transition.station_id)
    db.add(NotificationAudience(event_id=event.id, station_id=transition.station_id, area_ids=areas))
    if not capture_gate(db,event,transition.station_id):
        return  # Durable suppressed intent; leaving maintenance cannot replay it.
    by_user = {}
    for subscription in subscriptions:
        by_user.setdefault(subscription.user_id, subscription)
    if by_user:
        for device in db.scalars(eligible_devices().where(NotificationDevice.user_id.in_(list(by_user)))):
            capture_recipient(db, event, device, by_user[device.user_id])


def message_for(transition: AlertTransition) -> PushMessage:
    severity = transition.new_severity
    body = ("The configured EVACUATE sensor threshold was crossed. Prepare to evacuate and follow official local authority instructions."
            if severity == "EVACUATE" else
            "Flood sensor level has increased. Check the AGAPAY community alert and local authority guidance.")
    return PushMessage(
        title=f"AGAPAY {severity}-level sensor alert", body=body,
        data={"type": "SENSOR_ESCALATION", "alert_id": str(transition.alert_id),
              "severity": severity, "station_id": transition.station_id, "status": "ACTIVE"},
    )


def process_pending(provider: NotificationProvider, *, limit: int = 50, session_factory=SessionLocal, boundary=None) -> int:
    """Bounded batch with atomic claims, no DB transaction during send.

    PROCESSING rows are never reclaimed automatically: a crash after provider
    acceptance cannot safely be distinguished from a crash before sending.
    Inspect/reconcile those rows without blind resend.
    """
    if not 1 <= limit <= 100:
        raise ValueError("Batch limit must be between 1 and 100")
    from app.services import delivery_recovery as recovery

    def ready():
        # R2 P0: a delivery held by a recovery declaration is never claimable again.
        return (~reviewed_condition()) & recovery.not_held("operational", NotificationDelivery.id) & or_(
                   NotificationDelivery.state == "PENDING",
                   (NotificationDelivery.state == "FAILED") &
                   (NotificationDelivery.next_attempt_at <= utc_now()) &
                   (NotificationDelivery.attempts < MAX_ATTEMPTS))

    with session_factory() as db:
        from app.services.privacy_governance import require_released
        require_released(db)
        recovery.check_open(db)  # Fail closed: uninitialized, recovering, restored or copied database.
        ids = list(db.scalars(select(NotificationDelivery.id).where(ready())
                              .order_by(NotificationDelivery.id).limit(limit)))
    processed = 0
    for delivery_id in ids:
        with session_factory() as db:
            # Ticket (generation lock + claim sequence) and claim commit together; the
            # external ledger is written before the commit and before any provider call.
            ticket = recovery.take_ticket(db)
            claimed = db.execute(update(NotificationDelivery).where(
                NotificationDelivery.id == delivery_id, ready()).values(
                    state="PROCESSING", attempted_at=utc_now(), next_attempt_at=None,
                    attempts=NotificationDelivery.attempts + 1))
            if claimed.rowcount != 1:
                db.rollback()
                continue
            recovery.witness(ticket)
            db.commit()
            if boundary:boundary("claimed")
            delivery = db.get(NotificationDelivery, delivery_id)
            device = db.get(NotificationDevice, delivery.device_id)
            event = db.get(NotificationEvent, delivery.event_id)
            transition = db.get(AlertTransition, event.transition_id)
            from app.services import observability as obs
            import time
            delivery_started=time.perf_counter()
            obs.observe('notification.queue',max(0,(utc_now()-utc(delivery.created_at)).total_seconds()))
            episode = db.get(Alert, transition.alert_id)
            newer = db.scalar(select(AlertTransition.id).where(
                AlertTransition.alert_id == episode.id, AlertTransition.id > transition.id).limit(1))
            suppressed = (not delivery_allowed(db,event,transition.station_id) or not device_is_eligible(db, device) or not audience_allows(db, delivery, transition) or
                          device.revision != delivery.device_revision or newer is not None)
            control,attempt,receipt_secret=begin_attempt(db,delivery,device,provider.mode)
            suppressed=suppressed or utc_now()>=utc(control.expires_at) or control.review_status!="unreviewed"
            fenced = not recovery.still_open(db, ticket)  # Recovery declared after this claim.
            suppressed = suppressed or fenced
            target = PushTarget(device.provider, device.provider_token or "")
            message = message_for(transition)
            override = db.get(CitywideDispatch, event.id)
            if override is not None:
                control.expires_at=min(utc(control.expires_at),utc(override.expires_at))
                suppressed=suppressed or utc_now()>=utc(control.expires_at)
                authority = db.get(AlertAuthority, override.authority_id)
                message = replace(message,
                    body=f"Citywide sensor notification authorized by {authority.name if authority else override.authority_id}. " + message.body,
                    data={**message.data, "audience": "citywide", "authority_id": override.authority_id,
                          "expires_at": override.expires_at.isoformat()})
            data={**message.data,"delivery_id":str(delivery.id),"attempt_no":str(delivery.attempts),"expires_at":utc(control.expires_at).isoformat()}
            if receipt_secret:data['receipt_token']=receipt_secret
            message=replace(message,data=data)
            fingerprint = (device.token_hash or "none")[:12]
            db.commit() # Receipt capability/claim is durable before any provider call.
            if boundary:boundary('prepared')
        provider_reference=None
        if suppressed:
            outcome = SendOutcome.DISABLED
            category = "recovery_fenced" if fenced else "ineligible_or_superseded"
        else:
            try:
                send=getattr(provider,'send_with_evidence',provider.send)
                outcome = send(target, message, delivery_key=f"agapay-delivery-{delivery_id}")
                if isinstance(outcome,ProviderResult):
                    provider_reference=outcome.provider_reference if outcome.provider_reference and re.fullmatch(r'projects/[A-Za-z0-9_-]+/messages/[A-Za-z0-9%:_./-]{1,180}',outcome.provider_reference) else None
                    outcome=outcome.outcome
                if not isinstance(outcome, SendOutcome):
                    outcome = SendOutcome.UNKNOWN
            except Exception:
                # Exception strings/tracebacks may contain provider credentials.
                outcome = SendOutcome.UNKNOWN
            category = outcome.value
        if boundary:boundary('provider_returned')
        with session_factory() as db:
            delivery = db.get(NotificationDelivery, delivery_id)
            control=lock_control(db,delivery_id);control.version+=1
            attempt=db.get(DeliveryAttempt,(delivery_id,delivery.attempts))
            attempt.outcome=outcome.value;attempt.provider_reference=provider_reference;attempt.provider_reported_at=utc_now()
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
            if boundary:boundary("before_result_commit")
            db.commit()
            log.info("notification delivery=%s alert=%s severity=%s provider=%s token_fingerprint=%s state=%s result=%s",
                     delivery_id, message.data["alert_id"], message.data["severity"], delivery.provider_mode,
                     fingerprint, delivery.state, category)
            obs.observe('notification.delivery',time.perf_counter()-delivery_started,failed=delivery.state in ('FAILED','UNKNOWN'))
            obs.event('notification.completed',correlation_id=f'observation-{transition.telemetry_id}',sample_id=transition.telemetry_id,
                      transition_id=transition.id,event_id=event.id,delivery_id=delivery_id,state=delivery.state)
        from app.services import observability as obs
        obs.heartbeat('notifications',session_factory=session_factory)
        processed += 1
    return processed
