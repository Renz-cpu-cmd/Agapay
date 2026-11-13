"""Allowlisted snapshots. Passwords, hashes, MFA seeds and bearer/provider tokens are excluded."""
from app.identity_models import MutationAudit

ACCOUNT_FIELDS = ('id', 'name', 'email', 'phone', 'barangay', 'role', 'is_active', 'version')
SAFE_KEYS = set(ACCOUNT_FIELDS) | {
    'state', 'status', 'revision', 'identity_version', 'station_name', 'latitude', 'longitude',
    'sensor_height_cm', 'threshold_advisory_cm', 'threshold_warning_cm', 'threshold_evacuate_cm',
    'device_id', 'coordinates_verified', 'reference_datum', 'calibration_note', 'source_class', 'stream',
    'validation_status', 'evidence', 'installation', 'config_hash', 'version', 'reason', 'actor_id',
    'audience','mfa_verified','mfa_enabled', 'email_verified', 'password_changed', 'credentials_revoked', 'session_id',
    'enabled', 'platform', 'provider', 'device_id', 'notifications_enabled', 'locale', 'resident_area_id',
    'requested_language', 'action', 'kind', 'target_id', 'area_ids', 'station_ids', 'citywide',
    'mounting_height_cm','minimum_distance_cm','maximum_distance_cm','uncertainty_cm','range_margin_cm',
    'thresholds','advisory_cm','warning_cm','critical_cm','rain_mm_per_tip','datum','sensor_range','fault_policy',
    'review_status','evidence_kind','evidence_sha256',
    'model_card_id',
    'authority_id', 'authority_class', 'name', 'active', 'identifier_scheme', 'area_class',
    'owner_id', 'owner_name', 'changed_at', 'latest_telemetry_id',
    'diagnostic_checked_at', 'operator_fault_code', 'recovery_activity', 'evidence_sha256', 'attestation_kind',
}


def redact(data):
    if not isinstance(data, dict):
        return {}
    def safe_value(value):
        if isinstance(value, dict):
            return redact(value)
        if isinstance(value, list):
            return [safe_value(item) for item in value]
        return value
    return {key: safe_value(value)
            for key, value in data.items() if key in SAFE_KEYS and not any(
                word in key.lower() for word in ('password_hash', 'token', 'secret', 'recovery_code'))}


def snapshot(user):
    return {key: getattr(user, key) for key in ACCOUNT_FIELDS}


def record(db, actor, subject_type, subject_id, action, reason, before=None, after=None, *, actor_label=None):
    db.add(MutationAudit(actor_id=actor.id if actor else None,
        actor_label=actor.name if actor else actor_label or 'identity service',
        subject_type=subject_type, subject_id=str(subject_id), action=action, reason=reason,
        before=redact(before or {}), after=redact(after or {})))
