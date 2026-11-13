"""Serialized decisions inside the station ingestion lock; never commit or send."""
from sqlalchemy import inspect, select
from app.governance_models import HazardDecision, HazardPolicy, HazardRecovery
from app.governance_schemas import PolicyRules
from app.models import Telemetry
from app.services.alert_classifier import SEVERITY_ORDER, classify_depth
from app.services.station_security import utc


# User-authorized prototype defaults, not physical flood validation. Every
# decision records version 0 until an explicit station policy is approved.
PROVISIONAL_RULES = dict(advisory_hysteresis_cm=2, warning_hysteresis_cm=2,
    evacuate_hysteresis_cm=2, recovery_samples=3, recovery_seconds=10,
    max_sample_gap_seconds=15, max_change_cm_per_second=10)


def decide(db, station, telemetry, previous):
    policy = db.get(HazardPolicy, station.station_id)
    recovery = db.get(HazardRecovery, station.station_id)
    observation = classify_depth(station, telemetry.water_depth_cm) if telemetry.sensor_quality == "valid" else None
    desired, reason, review = previous, "unchanged", False

    def reset():
        nonlocal recovery
        if recovery is not None:
            if inspect(recovery).pending:
                db.expunge(recovery)
            else:
                db.delete(recovery)
            recovery = None

    if observation is None:
        reset()
        reason = "invalid_sample_no_recovery"
    else:
        rules = PolicyRules(**(policy.rules if policy else PROVISIONAL_RULES))
        policy_version = policy.version if policy else 0
        prior = db.scalar(select(Telemetry).where(
            Telemetry.station_id == station.station_id, Telemetry.id != telemetry.id,
            Telemetry.eligible_for_current.is_(True), Telemetry.sensor_quality == "valid",
            Telemetry.water_depth_cm.is_not(None),
        ).order_by(Telemetry.recorded_at.desc(), Telemetry.id.desc()).limit(1))
        implausible = telemetry.water_depth_cm < 0 or telemetry.water_depth_cm > station.sensor_height_cm
        if rules and prior:
            elapsed = (utc(telemetry.recorded_at) - utc(prior.recorded_at)).total_seconds()
            implausible |= elapsed <= 0 or abs(telemetry.water_depth_cm - prior.water_depth_cm) / max(elapsed, .001) > rules.max_change_cm_per_second
        if SEVERITY_ORDER[observation] > SEVERITY_ORDER[previous]:
            # No smoothing/plausibility gate may suppress a potentially critical rise.
            reset()
            desired = observation
            reason = "immediate_escalation_review" if implausible else "immediate_escalation"
            review = implausible
        elif SEVERITY_ORDER[observation] >= SEVERITY_ORDER[previous]:
            reset()
            review = implausible
            reason = "implausible_sample_review" if implausible else "unchanged"
        elif station.status=='maintenance':
            reset()
            reason,review='maintenance_recovery_held',implausible
        elif implausible:
            reset()
            reason, review = "implausible_recovery_held", True
        else:
            # Check every crossed exit boundary, so EVACUATE -> NORMAL cannot
            # skip the advisory hysteresis band and chatter back immediately.
            exits = [("EVACUATE", station.threshold_evacuate_cm - rules.evacuate_hysteresis_cm),
                     ("WARNING", station.threshold_warning_cm - rules.warning_hysteresis_cm),
                     ("ADVISORY", station.threshold_advisory_cm - rules.advisory_hysteresis_cm)]
            candidate = next((tier for tier, boundary in exits if telemetry.water_depth_cm >= boundary), "NORMAL")
            if SEVERITY_ORDER[candidate] >= SEVERITY_ORDER[previous]:
                reset()
                reason = "hysteresis_hold"
            else:
                at = utc(telemetry.recorded_at)
                same_boot = prior is not None and (prior.config_version, prior.boot_id) == (telemetry.config_version, telemetry.boot_id)
                continuing = recovery is not None and recovery.policy_version == policy_version and recovery.severity == candidate and same_boot and (at - utc(recovery.last_at)).total_seconds() <= rules.max_sample_gap_seconds
                if continuing:
                    recovery.count += 1
                    recovery.last_at = at
                else:
                    # Reuse the station-keyed row rather than deleting/inserting
                    # the same primary key during a single ORM flush.
                    if recovery is None:
                        recovery = HazardRecovery(station_id=station.station_id)
                        db.add(recovery)
                    recovery.policy_version, recovery.severity = policy_version, candidate
                    recovery.count, recovery.started_at, recovery.last_at = 1, at, at
                sustained = recovery.count >= rules.recovery_samples and (at - utc(recovery.started_at)).total_seconds() >= rules.recovery_seconds
                desired, reason = (candidate, "sustained_recovery") if sustained else (previous, "recovery_pending")
                if sustained:
                    reset()
    db.add(HazardDecision(telemetry_id=telemetry.id, station_id=station.station_id,
        policy_version=policy.version if policy else 0, observation_tier=observation,
        episode_tier=desired, reason=reason, review_required=review))
    return desired
