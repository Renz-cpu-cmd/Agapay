"""Deployment attestations are supplied by the responsible organization, never seeded."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

POLICY = {
    'version': 'development-privacy-v1', 'approval': 'unreviewed development defaults',
    'resolved_sos_location_days': 7, 'resolved_sos_narrative_days': 30,
    'disabled_push_token_days': 30, 'expired_identity_action_days': 14,
    'backup_retention_days': 30, 'audit_review_days': 365, 'privacy_case_review_days': 365,
    'case_response_target_days': 15, 'rpo_seconds': 900, 'rto_seconds': 14400,
}
POLICY_HASH = hashlib.sha256(json.dumps(POLICY, sort_keys=True).encode()).hexdigest()


def approved_record(path, *, now=None):
    """Structural gate; an evidence hash does not itself prove legal/organizational approval."""
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        now = now or datetime.now(timezone.utc)
        if value['status'] != 'approved' or value['policy_sha256'] != POLICY_HASH:
            raise ValueError()
        if datetime.fromisoformat(value['review_expires_at'].replace('Z', '+00:00')) <= now:
            raise ValueError()
        for name in ('privacy_review', 'pia_review', 'restore_drill', 'access_review', 'retention_exercise'):
            if not re.fullmatch('[a-f0-9]{64}', value['evidence'][name]):
                raise ValueError()
        for name in ('organization', 'issuing_authority', 'operator_hours', 'support_contact', 'fallback_contact',
                     'privacy_contact', 'incident_owner', 'backup_owner', 'database_owner', 'push_owner', 'maps_cost_owner'):
            item = value[name]
            if not isinstance(item, str) or len(item.strip()) < 3 or any(
                word in item.lower() for word in ('pending', 'replace', 'example', 'unassigned', '.invalid')):
                raise ValueError()
        if value['rpo_seconds'] != POLICY['rpo_seconds'] or value['rto_seconds'] != POLICY['rto_seconds']:
            raise ValueError()
        return value
    except (OSError, ValueError, KeyError, TypeError):
        raise RuntimeError('Reviewed privacy/service ownership and current exercise evidence are required') from None


def deployment_status(settings):
    try:
        value = approved_record(settings.service_governance_path)
        return dict(status='organization_attested', policy_sha256=POLICY_HASH,
                    organization=value['organization'], privacy_contact=value['privacy_contact'],
                    support_contact=value['support_contact'], operator_hours=value['operator_hours'])
    except RuntimeError:
        return dict(status='unapproved_development', policy_sha256=POLICY_HASH,
                    organization=None, privacy_contact=None, support_contact=None,
                    operator_hours='No operational response hours committed')


def require_released(db):
    from app.privacy_models import RecoveryFence
    fence = db.get(RecoveryFence, 1)
    if fence and fence.state != 'RELEASED':
        raise RuntimeError('Restored database is quarantined; reconcile privacy withdrawals and recovery evidence before activation')
