"""Isolated EXERCISE_TEST notifications (Stage A: manual, administrator-initiated).

Isolation boundaries:
- Disabled by default; refused in production (also rejected by Settings validation).
- Only an active administrator can create sessions, allowlist devices and request sends.
- Recipients come ONLY from the session's explicit allowlist. A device qualifies only if
  it is enabled, has a token, its owner is an active account, and the owner opted in for
  this exact registration revision. Subscriptions, areas, stations and citywide audiences
  are never consulted.
- Records live in exercise_* tables; nothing here touches operational alerts, the
  resident notification outbox, advisories or SOS.
- Every condition is revalidated by the worker immediately before sending. One attempt
  only; an ambiguous outcome is recorded as UNKNOWN and is never automatically resent.
"""
import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.config import get_settings
from app.exercise_models import (EXERCISE_TYPE, ExerciseConsent, ExerciseDelivery,  # noqa: F401
                                 ExerciseRecipient, ExerciseSensorDelivery, ExerciseSensorTrigger,
                                 ExerciseSession, ExerciseStationArm)
from app.models import NotificationDevice, User, utc_now
from app.services.notification_provider import PushMessage, PushTarget, SendOutcome
from app.services.station_security import utc

EXERCISE_TITLE = "AGAPAY TEST ALERT — NOT A REAL EMERGENCY"
EXERCISE_BODY = ("EXERCISE ONLY. This is an AGAPAY system test, not a flood warning, evacuation "
                 "instruction or official advisory. No action is required.")
MAX_RECIPIENTS = 5


def exercise_message(session_id, delivery_id):
    return PushMessage(title=EXERCISE_TITLE, body=EXERCISE_BODY,
                       data={"type": EXERCISE_TYPE, "exercise": "true",
                             "session_id": session_id, "delivery_id": delivery_id})


def availability_problem(settings=None):
    settings = settings or get_settings()
    if settings.environment == "production":
        return "prohibited_in_production"
    if not settings.exercise_notifications_enabled:
        return "exercise_notifications_disabled"
    return None


def require_available():
    problem = availability_problem()
    if problem:
        raise HTTPException(403, "Exercise test notifications are unavailable: " + problem.replace("_", " "))


def _audit(db, actor, action, subject, reason, details):
    from app.services.alert_governance import record
    record(db, actor, action, subject, reason, {"message_type": EXERCISE_TYPE, **details})


def session_problem(db, session, now=None):
    now = now or utc_now()
    if session is None:
        return "session_not_found"
    if session.terminated_at is not None:
        return "session_terminated"
    if utc(session.expires_at) <= now:
        return "session_expired"
    creator = db.get(User, session.created_by)
    if creator is None or not creator.is_active or creator.role != "admin":
        return "session_creator_not_authorized"
    return None


def device_problem(db, device_id, revision=None):
    device = db.get(NotificationDevice, device_id, populate_existing=True)
    if device is None:
        return "device_not_found", None
    owner = db.get(User, device.user_id)
    if not device.enabled or not device.provider_token or not device.token_hash:
        return "device_not_enabled", device
    if owner is None or not owner.is_active:
        return "device_owner_inactive", device
    if revision is not None and device.revision != revision:
        return "device_registration_changed", device
    consent = db.get(ExerciseConsent, device_id, populate_existing=True)
    if (consent is None or consent.revoked_at is not None or consent.user_id != device.user_id
            or consent.device_revision != device.revision):
        return "device_owner_not_opted_in", device
    return None, device


def recipient_problem(db, session, device_id, now=None):
    problem = availability_problem() or session_problem(db, session, now)
    if problem:
        return problem
    recipient = db.get(ExerciseRecipient, (session.id, device_id), populate_existing=True)
    if recipient is None or recipient.revoked_at is not None:
        return "device_not_allowlisted"
    problem, _ = device_problem(db, device_id, recipient.device_revision)
    return problem


# --- Resident opt-in --------------------------------------------------------------------

def consent_state(db, user, device_id):
    """Owner-only read. Opted in only for this exact registration revision."""
    require_available()
    device = db.get(NotificationDevice, device_id)
    if device is None or device.user_id != user.id:
        raise HTTPException(404, "Notification device not found")
    consent = db.get(ExerciseConsent, device_id)
    opted_in = bool(consent and consent.revoked_at is None and consent.user_id == user.id
                    and consent.device_revision == device.revision and device.enabled)
    return dict(device_id=device_id, opted_in=opted_in, message_type=EXERCISE_TYPE)


def set_consent(db, user, device_id, enabled):
    require_available()
    device = db.get(NotificationDevice, device_id)
    if device is None or device.user_id != user.id:
        raise HTTPException(404, "Notification device not found")
    consent = db.get(ExerciseConsent, device_id)
    if enabled:
        if not device.enabled or not device.provider_token:
            raise HTTPException(409, "Register and enable this device before opting in")
        if consent is None:
            consent = ExerciseConsent(device_id=device_id, user_id=user.id, device_revision=device.revision)
            db.add(consent)
        consent.user_id, consent.device_revision, consent.consented_at, consent.revoked_at = (
            user.id, device.revision, utc_now(), None)
    elif consent is not None and consent.revoked_at is None:
        consent.revoked_at = utc_now()
    db.commit()
    return dict(device_id=device_id, opted_in=bool(enabled), message_type=EXERCISE_TYPE)


# --- Administrator session lifecycle ----------------------------------------------------

def lock_session(db, session_id):
    locked = db.execute(update(ExerciseSession).where(ExerciseSession.id == session_id)
                        .values(revision=ExerciseSession.revision + 1))
    if locked.rowcount != 1:
        raise HTTPException(404, "Exercise session not found")
    return db.get(ExerciseSession, session_id, populate_existing=True)


def create_session(db, admin, reason, duration_minutes, max_sends):
    require_available()
    limit = get_settings().exercise_session_max_minutes
    if not 1 <= duration_minutes <= limit:
        raise HTTPException(422, f"Exercise sessions must expire within {limit} minutes")
    session = ExerciseSession(created_by=admin.id, reason=reason, max_sends=max_sends,
                              expires_at=utc_now() + timedelta(minutes=duration_minutes))
    db.add(session)
    db.flush()
    _audit(db, admin, "exercise_session_created", f"exercise-session:{session.id}", reason,
           {"expires_at": session.expires_at.isoformat(), "max_sends": max_sends})
    db.commit()
    return session


def allowlist_device(db, admin, session_id, device_id, reason):
    require_available()
    session = lock_session(db, session_id)
    problem = session_problem(db, session)
    if problem:
        db.rollback()
        raise HTTPException(409, "Exercise session is not active: " + problem.replace("_", " "))
    problem, device = device_problem(db, device_id)
    if problem:
        db.rollback()
        raise HTTPException(409, "Device cannot be allowlisted: " + problem.replace("_", " "))
    active = db.scalar(select(func.count()).select_from(ExerciseRecipient).where(
        ExerciseRecipient.session_id == session_id, ExerciseRecipient.revoked_at.is_(None),
        ExerciseRecipient.device_id != device_id))
    if active >= MAX_RECIPIENTS:
        db.rollback()
        raise HTTPException(409, f"An exercise session may allowlist at most {MAX_RECIPIENTS} devices")
    row = db.get(ExerciseRecipient, (session_id, device_id))
    if row is None:
        row = ExerciseRecipient(session_id=session_id, device_id=device_id, device_revision=device.revision,
                                added_by=admin.id)
        db.add(row)
    row.device_revision, row.added_by, row.added_at, row.revoked_at = device.revision, admin.id, utc_now(), None
    _audit(db, admin, "exercise_device_allowlisted", f"exercise-session:{session_id}", reason,
           {"device_id": device_id, "device_revision": device.revision})
    db.commit()
    return row


def revoke_device(db, admin, session_id, device_id, reason):
    session = lock_session(db, session_id)
    row = db.get(ExerciseRecipient, (session.id, device_id))
    if row is None:
        db.rollback()
        raise HTTPException(404, "Device is not on this exercise allowlist")
    if row.revoked_at is None:
        row.revoked_at = utc_now()
    _audit(db, admin, "exercise_device_revoked", f"exercise-session:{session_id}", reason, {"device_id": device_id})
    db.commit()
    return row


def terminate_session(db, admin, session_id, reason):
    session = lock_session(db, session_id)
    if session.terminated_at is None:
        session.terminated_at, session.terminated_by = utc_now(), admin.id
    _audit(db, admin, "exercise_session_terminated", f"exercise-session:{session_id}", reason, {})
    db.commit()
    return session


def request_send(db, admin, session_id, device_id, idempotency_key, reason, dry_run):
    """Validate and (unless dry-run) record ONE pending exercise delivery."""
    require_available()
    session = lock_session(db, session_id)
    existing = db.scalar(select(ExerciseDelivery).where(ExerciseDelivery.session_id == session_id,
                                                         ExerciseDelivery.idempotency_key == idempotency_key))
    if existing is not None:
        db.rollback()
        if existing.device_id != device_id:
            raise HTTPException(409, "Idempotency key already used for a different device")
        return existing, True
    problem = recipient_problem(db, session, device_id)
    if problem:
        db.rollback()
        raise HTTPException(409, "Exercise send refused: " + problem.replace("_", " "))
    if sends_used(db, session_id) >= session.max_sends:
        db.rollback()
        raise HTTPException(429, "Exercise session send limit reached")
    interval = get_settings().exercise_min_send_interval_seconds
    latest = latest_send(db, session_id, device_id)
    if latest is not None and (utc_now() - latest).total_seconds() < interval:
        db.rollback()
        raise HTTPException(429, f"Wait at least {interval} seconds between exercise sends to one device",
                            headers={"Retry-After": str(interval)})
    recipient = db.get(ExerciseRecipient, (session_id, device_id))
    if dry_run:
        _audit(db, admin, "exercise_send_dry_run", f"exercise-session:{session_id}", reason, {"device_id": device_id})
        db.commit()
        return None, False
    delivery = ExerciseDelivery(session_id=session_id, device_id=device_id, device_revision=recipient.device_revision,
                                requested_by=admin.id, idempotency_key=idempotency_key)
    db.add(delivery)
    db.flush()
    _audit(db, admin, "exercise_send_requested", f"exercise-session:{session_id}", reason,
           {"device_id": device_id, "delivery_id": delivery.id})
    db.commit()
    return delivery, False


# --- Shared rate-limit accounting (manual 0006 + sensor 0007 deliveries) ---------------

def sends_used(db, session_id):
    """Deliveries counted against the session cap. Suppressed sensor rows never sent."""
    manual = db.scalar(select(func.count()).select_from(ExerciseDelivery).where(ExerciseDelivery.session_id == session_id))
    sensor = db.scalar(select(func.count()).select_from(ExerciseSensorDelivery).where(
        ExerciseSensorDelivery.session_id == session_id, ExerciseSensorDelivery.state != "SUPPRESSED"))
    return manual + sensor


def latest_send(db, session_id, device_id):
    times = [db.scalar(select(func.max(ExerciseDelivery.created_at)).where(
                 ExerciseDelivery.session_id == session_id, ExerciseDelivery.device_id == device_id)),
             db.scalar(select(func.max(ExerciseSensorDelivery.created_at)).where(
                 ExerciseSensorDelivery.session_id == session_id, ExerciseSensorDelivery.device_id == device_id,
                 ExerciseSensorDelivery.state != "SUPPRESSED"))]
    times = [utc(t) for t in times if t is not None]
    return max(times) if times else None


# --- Worker (shared by manual and sensor-triggered exercise deliveries) -----------------

def _send_problem(db, provider, delivery, session):
    problem = recipient_problem(db, session, delivery.device_id)
    device = db.get(NotificationDevice, delivery.device_id, populate_existing=True)
    if problem is None and device.revision != delivery.device_revision:
        problem = "device_registration_changed"
    if problem is None and provider.mode == "disabled":
        problem = "provider_disabled"
    return problem, device


def _process_batch(model, provider, message_for, extra_problem, *, limit, session_factory):
    """Bounded batch. Claim atomically, revalidate everything, attempt once."""
    if session_factory is None:
        from app.database import SessionLocal as session_factory
    if not 1 <= limit <= 50:
        raise ValueError("Batch limit must be between 1 and 50")
    from app.services import delivery_recovery as recovery
    kind = _RECOVERY_KIND[model]
    unheld = recovery.not_held(kind, model.id)  # R2 P0: held exercise rows are never claimable again.
    with session_factory() as db:
        recovery.check_open(db)  # Same fail-closed generation gate as operational delivery.
        ids = list(db.scalars(select(model.id).where(model.state == "PENDING", unheld)
                              .order_by(model.created_at, model.id).limit(limit)))
    processed = 0
    for delivery_id in ids:
        with session_factory() as db:
            ticket = recovery.take_ticket(db)
            claimed = db.execute(update(model).where(model.id == delivery_id, model.state == "PENDING", unheld).values(
                state="PROCESSING", attempts=model.attempts + 1, attempted_at=utc_now()))
            if claimed.rowcount != 1:
                db.rollback()
                continue
            recovery.witness(ticket)
            db.commit()
            delivery = db.get(model, delivery_id)
            session = db.get(ExerciseSession, delivery.session_id, populate_existing=True)
            problem, device = _send_problem(db, provider, delivery, session)
            problem = problem or extra_problem(db, delivery)
            if problem is None and not recovery.still_open(db, ticket):
                problem = "recovery_fenced"
            if problem:
                delivery.state, delivery.outcome = "SUPPRESSED", problem[:40]
            else:
                try:
                    outcome = provider.send(PushTarget(device.provider, device.provider_token or ""),
                                            message_for(db, session, delivery),
                                            delivery_key="exercise:" + delivery.id)
                except Exception:
                    outcome = SendOutcome.UNKNOWN
                delivery.state = {SendOutcome.ACCEPTED: "SENT" if provider.mode == "fcm" else "TESTED",
                                  SendOutcome.TEST_ONLY: "TESTED", SendOutcome.UNKNOWN: "UNKNOWN",
                                  SendOutcome.DISABLED: "SUPPRESSED"}.get(outcome, "REJECTED")
                delivery.outcome = outcome.value
            delivery.completed_at = utc_now()
            db.commit()
            processed += 1
    return processed


_RECOVERY_KIND = {ExerciseDelivery: "exercise_manual", ExerciseSensorDelivery: "exercise_sensor"}


def process_pending(provider, *, limit=10, session_factory=None):
    """Manual (Stage A) exercise deliveries."""
    return _process_batch(ExerciseDelivery, provider, lambda db, s, d: exercise_message(s.id, d.id),
                          lambda db, d: None, limit=limit, session_factory=session_factory)


def process_sensor_pending(provider, *, limit=10, session_factory=None):
    """Sensor-triggered (Stage B) exercise deliveries; also stops when the station is disarmed."""
    def disarmed(db, delivery):
        trigger = db.get(ExerciseSensorTrigger, delivery.trigger_id)
        arm = db.get(ExerciseStationArm, (delivery.session_id, trigger.station_id), populate_existing=True)
        return "station_disarmed" if arm is None or arm.disarmed_at is not None else None

    def message(db, session, delivery):
        trigger = db.get(ExerciseSensorTrigger, delivery.trigger_id)
        return sensor_exercise_message(session.id, delivery.id, trigger.station_id, trigger.current_tier)
    return _process_batch(ExerciseSensorDelivery, provider, message, disarmed, limit=limit,
                          session_factory=session_factory)


# --- Real-provider gate --------------------------------------------------------------------

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MANUAL_KEYS = frozenset({"type", "exercise", "session_id", "delivery_id"})
SENSOR_KEYS = MANUAL_KEYS | {"trigger"}
_AVAILABILITY = {"prohibited_in_production", "exercise_notifications_disabled"}


def provider_send_problem(message, target_token, delivery_key, session_factory=None):
    """Checked by a real provider immediately before an EXERCISE_TEST SDK call.

    Returns (None, None) when allowed, else ("disabled" | "rejected", reason). A send is
    allowed only for an audited delivery row this service has already claimed (PROCESSING,
    exactly one attempt) whose recipient is still eligible and whose content is exactly
    what this service builds. Direct provider calls with invented payloads are rejected.
    """
    problem = availability_problem()
    if problem:
        return "disabled", problem
    data = message.data
    if not isinstance(data, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in data.items()):
        return "rejected", "invalid_data"
    keys = frozenset(data)
    if (data.get("type") != EXERCISE_TYPE or data.get("exercise") != "true" or keys not in (MANUAL_KEYS, SENSOR_KEYS)
            or (keys == SENSOR_KEYS and data.get("trigger") != "sensor")):
        return "rejected", "invalid_payload_keys"
    if not _UUID.fullmatch(data["delivery_id"]) or not _UUID.fullmatch(data["session_id"]):
        return "rejected", "invalid_identifiers"
    if delivery_key != "exercise:" + data["delivery_id"] or message.title != EXERCISE_TITLE:
        return "rejected", "invalid_envelope"
    if session_factory is None:
        from app.database import SessionLocal as session_factory
    sensor = keys == SENSOR_KEYS
    with session_factory() as db:
        model = ExerciseSensorDelivery if sensor else ExerciseDelivery
        delivery = db.get(model, data["delivery_id"], populate_existing=True)
        if (delivery is None or delivery.session_id != data["session_id"] or delivery.state != "PROCESSING"
                or delivery.attempts != 1 or delivery.message_type != EXERCISE_TYPE):
            return "rejected", "no_claimed_exercise_delivery"
        from app.services import delivery_recovery as recovery
        held = db.scalar(select(func.count()).select_from(recovery.DeliveryHold).where(
            recovery.DeliveryHold.kind == ("exercise_sensor" if sensor else "exercise_manual"),
            recovery.DeliveryHold.delivery_id == delivery.id))
        try:
            recovery.check_open(db)
        except recovery.DeliveryFenced:
            held = True
        if held:
            return "rejected", "recovery_fenced"
        session = db.get(ExerciseSession, delivery.session_id, populate_existing=True)
        problem = recipient_problem(db, session, delivery.device_id)
        if problem:
            return ("disabled" if problem in _AVAILABILITY else "rejected"), problem
        device = db.get(NotificationDevice, delivery.device_id, populate_existing=True)
        if device.revision != delivery.device_revision or device.provider_token != target_token:
            return "rejected", "recipient_mismatch"
        if sensor:
            trigger = db.get(ExerciseSensorTrigger, delivery.trigger_id)
            arm = db.get(ExerciseStationArm, (delivery.session_id, trigger.station_id), populate_existing=True)
            if arm is None or arm.disarmed_at is not None:
                return "rejected", "station_disarmed"
            expected = sensor_exercise_message(session.id, delivery.id, trigger.station_id, trigger.current_tier)
        else:
            expected = exercise_message(session.id, delivery.id)
        if expected != message:
            return "rejected", "content_mismatch"
    return None, None


# --- Stage B: sensor-triggered exercise ---------------------------------------------------

TIER_RANK = {"NORMAL": 0, "ADVISORY": 1, "WARNING": 2, "EVACUATE": 3}
MAX_ARMED_STATIONS = 3
EXERCISE_DISPOSITIONS = ("current", "exercise_local_outputs")  # ordered, fresh, configuration-matched


def sensor_exercise_message(session_id, delivery_id, station_id, tier):
    body = (f"EXERCISE ONLY. AGAPAY test station {station_id} recorded an observed {tier}-level reading "
            "during an exercise. This is a system test, not a flood warning, evacuation instruction or "
            "official advisory. No action is required.")
    return PushMessage(title=EXERCISE_TITLE, body=body,
                       data={"type": EXERCISE_TYPE, "exercise": "true", "trigger": "sensor",
                             "session_id": session_id, "delivery_id": delivery_id})


def _trusted_physical(db, telemetry_id):
    """Same registry/provenance evidence as R4 (services/incident_verification.py),
    without the operational configuration-review requirement: exercises may use
    prototype stations, but never untrusted or simulated sources."""
    from sqlalchemy import literal
    from app.services.incident_verification import recorded_evidence
    return bool(db.scalar(select(literal(True)).where(
        recorded_evidence(literal(telemetry_id), require_reviewed_configuration=False))))


def observed_tier(db, station, row, armed_at, now):
    """Tier of a committed sample if it is eligible exercise evidence, else None."""
    from math import isfinite
    from app.services.alert_classifier import classify_depth
    from app.services.telemetry_service import MAX_CURRENT_AGE_SECONDS
    measured = utc(row.measured_at) if row.measured_at else None
    if (row.disposition not in EXERCISE_DISPOSITIONS or row.sensor_quality != "valid"
            or row.water_depth_cm is None or not isfinite(row.water_depth_cm) or measured is None
            or measured <= utc(armed_at) or (now - measured).total_seconds() > MAX_CURRENT_AGE_SECONDS
            or not _trusted_physical(db, row.id)):
        return None
    return classify_depth(station, row.water_depth_cm)


def arm_station(db, admin, session_id, station_id, reason):
    from app.models import Station, StationIdentity, StationSourceRegistry, Telemetry
    from app.services.alert_classifier import classify_depth
    from app.services.telemetry_service import MAX_CURRENT_AGE_SECONDS
    require_available()
    session = lock_session(db, session_id)
    problem = session_problem(db, session)
    if problem:
        db.rollback()
        raise HTTPException(409, "Exercise session is not active: " + problem.replace("_", " "))
    station = db.scalar(select(Station).where(Station.station_id == station_id))
    identity = db.get(StationIdentity, station_id)
    registry = db.get(StationSourceRegistry, (station_id, identity.version)) if identity else None
    if (station is None or identity is None or identity.state != "commissioned" or registry is None
            or registry.source_class != "physical_device" or registry.stream != "operational"):
        db.rollback()
        raise HTTPException(409, "Only a commissioned, registry-verified physical station can be armed")
    armed = db.scalar(select(func.count()).select_from(ExerciseStationArm).where(
        ExerciseStationArm.session_id == session_id, ExerciseStationArm.disarmed_at.is_(None),
        ExerciseStationArm.station_id != station_id))
    if armed >= MAX_ARMED_STATIONS:
        db.rollback()
        raise HTTPException(409, f"An exercise session may arm at most {MAX_ARMED_STATIONS} stations")
    now = utc_now()
    cursor = db.scalar(select(func.max(Telemetry.id)).where(Telemetry.station_id == station_id)) or 0
    # Baseline: the latest fresh, valid, trusted observation already committed. An
    # already elevated reading is the starting point, never a new escalation.
    baseline, baseline_id = None, None
    for row in db.scalars(select(Telemetry).where(Telemetry.station_id == station_id)
                          .order_by(Telemetry.id.desc()).limit(20)):
        measured = utc(row.measured_at) if row.measured_at else None
        if (row.disposition in EXERCISE_DISPOSITIONS and row.sensor_quality == "valid"
                and row.water_depth_cm is not None and measured is not None
                and (now - measured).total_seconds() <= MAX_CURRENT_AGE_SECONDS and _trusted_physical(db, row.id)):
            baseline, baseline_id = classify_depth(station, row.water_depth_cm), row.id
            break
    arm = db.get(ExerciseStationArm, (session_id, station_id))
    if arm is None:
        arm = ExerciseStationArm(session_id=session_id, station_id=station_id, armed_by=admin.id)
        db.add(arm)
    (arm.armed_by, arm.armed_at, arm.baseline_tier, arm.baseline_telemetry_id, arm.previous_tier,
     arm.cursor_telemetry_id, arm.disarmed_at) = (admin.id, now, baseline, baseline_id, baseline, cursor, None)
    _audit(db, admin, "exercise_station_armed", f"exercise-session:{session_id}", reason,
           {"station_id": station_id, "baseline_tier": baseline, "cursor_telemetry_id": cursor})
    db.commit()
    return arm


def disarm_station(db, admin, session_id, station_id, reason):
    lock_session(db, session_id)
    arm = db.get(ExerciseStationArm, (session_id, station_id))
    if arm is None:
        db.rollback()
        raise HTTPException(404, "Station is not armed for this exercise session")
    if arm.disarmed_at is None:
        arm.disarmed_at = utc_now()
    _audit(db, admin, "exercise_station_disarmed", f"exercise-session:{session_id}", reason, {"station_id": station_id})
    db.commit()
    return arm


def scan_sensor_triggers(*, session_factory=None, batch=200):
    """Read-only against operational telemetry. Each armed station is processed under a
    row lock on its arm; uniqueness constraints make concurrent watchers idempotent."""
    from sqlalchemy.exc import IntegrityError
    if session_factory is None:
        from app.database import SessionLocal as session_factory
    if availability_problem():
        return 0
    with session_factory() as db:
        keys = list(db.execute(select(ExerciseStationArm.session_id, ExerciseStationArm.station_id)
                               .where(ExerciseStationArm.disarmed_at.is_(None))))
    created = 0
    for session_id, station_id in keys:
        with session_factory() as db:
            try:
                created += _scan_arm(db, session_id, station_id, batch)
                db.commit()
            except IntegrityError:
                db.rollback()  # Another watcher recorded the same trigger first.
    return created


def _scan_arm(db, session_id, station_id, batch):
    from app.models import Station, Telemetry
    locked = db.execute(update(ExerciseStationArm).where(
        ExerciseStationArm.session_id == session_id, ExerciseStationArm.station_id == station_id,
        ExerciseStationArm.disarmed_at.is_(None)).values(revision=ExerciseStationArm.revision + 1))
    if locked.rowcount != 1:
        return 0
    arm = db.get(ExerciseStationArm, (session_id, station_id), populate_existing=True)
    session = db.get(ExerciseSession, session_id, populate_existing=True)
    if availability_problem() or session_problem(db, session):
        return 0  # Terminated/expired sessions stop immediately; nothing is consumed.
    station = db.scalar(select(Station).where(Station.station_id == station_id))
    now, created = utc_now(), 0
    rows = db.scalars(select(Telemetry).where(Telemetry.station_id == station_id,
                                              Telemetry.id > arm.cursor_telemetry_id)
                      .order_by(Telemetry.id).limit(batch)).all()
    for row in rows:
        arm.cursor_telemetry_id = row.id
        tier = observed_tier(db, station, row, arm.armed_at, now)
        if tier is None:
            continue  # Stale, invalid, untrusted, replayed, out-of-order or pre-arming.
        previous, arm.previous_tier = arm.previous_tier, tier
        if previous is None or TIER_RANK[tier] <= TIER_RANK[previous]:
            continue  # Unknown baseline is established first; only increases trigger.
        if db.scalar(select(ExerciseSensorTrigger.id).where(
                ExerciseSensorTrigger.session_id == session_id, ExerciseSensorTrigger.station_id == station_id,
                ExerciseSensorTrigger.current_tier == tier)):
            continue  # Each tier at most once per station per session.
        _record_trigger(db, session, station_id, row, previous, tier, now)
        created += 1
    return created


def _record_trigger(db, session, station_id, row, previous, tier, now):
    from app.models import TelemetryProvenance
    provenance = db.get(TelemetryProvenance, row.id)
    recipients = db.scalars(select(ExerciseRecipient).where(
        ExerciseRecipient.session_id == session.id, ExerciseRecipient.revoked_at.is_(None))
        .order_by(ExerciseRecipient.added_at, ExerciseRecipient.device_id)).all()
    remaining = session.max_sends - sends_used(db, session.id)
    status = "NO_RECIPIENTS" if not recipients else "SEND_LIMIT" if remaining <= 0 else "DELIVERIES_CREATED"
    trigger = ExerciseSensorTrigger(
        session_id=session.id, station_id=station_id, telemetry_id=row.id,
        source_class=provenance.source_class, ingress_identity=provenance.ingress_identity,
        ingress_transport=provenance.ingress_transport, registry_version=provenance.registry_version,
        credential_id=provenance.credential_id, measured_at=row.measured_at, received_at=row.received_at,
        processed_at=now, water_depth_cm=row.water_depth_cm, previous_tier=previous, current_tier=tier, status=status)
    db.add(trigger)
    db.flush()
    if status != "DELIVERIES_CREATED":
        return trigger
    interval = get_settings().exercise_min_send_interval_seconds
    for recipient in recipients:
        problem = recipient_problem(db, session, recipient.device_id)
        latest = latest_send(db, session.id, recipient.device_id)
        if problem is None and remaining <= 0:
            problem = "session_send_limit"
        # Measure against the current clock: deliveries created earlier in this same scan
        # carry timestamps later than the scan's start time.
        if problem is None and latest is not None and (utc_now() - latest).total_seconds() < interval:
            problem = "rate_limited"
        db.add(ExerciseSensorDelivery(
            trigger_id=trigger.id, session_id=session.id, device_id=recipient.device_id,
            device_revision=recipient.device_revision, idempotency_key=f"{trigger.id}:{recipient.device_id}",
            state="SUPPRESSED" if problem else "PENDING", outcome=problem[:40] if problem else None,
            completed_at=now if problem else None))
        if problem is None:
            remaining -= 1
        db.flush()
    return trigger


def session_contract(db, session):
    recipients = db.scalars(select(ExerciseRecipient).where(ExerciseRecipient.session_id == session.id)
                            .order_by(ExerciseRecipient.added_at)).all()
    deliveries = db.scalars(select(ExerciseDelivery).where(ExerciseDelivery.session_id == session.id)
                            .order_by(ExerciseDelivery.created_at, ExerciseDelivery.id)).all()
    problem = session_problem(db, session)
    return {
        "id": session.id, "message_type": EXERCISE_TYPE, "title": EXERCISE_TITLE,
        "reason": session.reason, "created_at": utc(session.created_at), "expires_at": utc(session.expires_at),
        "terminated_at": utc(session.terminated_at) if session.terminated_at else None,
        "active": problem is None and availability_problem() is None, "state_reason": problem,
        "max_sends": session.max_sends, "revision": session.revision,
        "recipients": [{"device_id": r.device_id, "device_revision": r.device_revision,
                        "allowlisted": r.revoked_at is None} for r in recipients],
        "deliveries": [delivery_contract(d) for d in deliveries],
        "armed_stations": [{"station_id": a.station_id, "armed_at": utc(a.armed_at), "baseline_tier": a.baseline_tier,
                            "previous_tier": a.previous_tier, "armed": a.disarmed_at is None}
                           for a in db.scalars(select(ExerciseStationArm).where(ExerciseStationArm.session_id == session.id))],
        "sensor_triggers": [{"id": t.id, "station_id": t.station_id, "telemetry_id": t.telemetry_id,
                             "previous_tier": t.previous_tier, "current_tier": t.current_tier,
                             "measured_at": utc(t.measured_at), "status": t.status, "message_type": EXERCISE_TYPE}
                            for t in db.scalars(select(ExerciseSensorTrigger).where(
                                ExerciseSensorTrigger.session_id == session.id).order_by(ExerciseSensorTrigger.processed_at))],
        "sensor_deliveries": [{**delivery_contract(d, trigger="sensor"), "trigger_id": d.trigger_id}
                              for d in db.scalars(select(ExerciseSensorDelivery).where(
                                  ExerciseSensorDelivery.session_id == session.id).order_by(ExerciseSensorDelivery.created_at))],
    }


def delivery_contract(d, trigger=None):
    return {"id": d.id, "device_id": d.device_id, "message_type": d.message_type, "trigger": trigger or d.trigger_kind,
            "state": d.state, "outcome": d.outcome, "attempts": d.attempts,
            "created_at": utc(d.created_at), "completed_at": utc(d.completed_at) if d.completed_at else None}
