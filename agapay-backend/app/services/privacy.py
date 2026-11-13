"""Owner-scoped rights, explicit review and bounded retention. Never sends mail/push."""
from datetime import timedelta
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import delete, func, select, update, or_, exists
from app.models import User, SosRequest, NotificationDevice, AuthSession, utc_now
from app.privacy_models import PrivacyCase, PrivacyEvent, PrivacyHold
from app.services.accounts import lock_account, verify_password, revoke_sessions, passwords
from app.services.station_security import utc
from app.services.privacy_governance import POLICY, POLICY_HASH


def evidence(db, actor, subject, action, **details):
    db.add(PrivacyEvent(actor_id=actor.id if actor else None, subject_id=str(subject), action=action, details=details))


def step_up(db, user, password):
    lock_account(db, user.id)
    db.refresh(user)
    if not user.is_active or not verify_password(password, user):
        raise HTTPException(403, 'Current password verification required')


def view(case):
    result = {key: getattr(case, key) for key in ('id', 'kind', 'version', 'state', 'decision_code', 'created_at', 'due_at', 'updated_at')}
    for key in ('created_at', 'due_at', 'updated_at'): result[key] = utc(result[key]).isoformat()
    return result


def create_case(db, user, kind):
    pending = db.scalar(select(PrivacyCase).where(PrivacyCase.user_id == user.id, PrivacyCase.kind == kind,
        PrivacyCase.state.not_in(('COMPLETED', 'REJECTED'))))
    if pending:
        return view(pending)
    case = PrivacyCase(user_id=user.id, kind=kind, due_at=utc_now() + timedelta(days=POLICY['case_response_target_days']))
    db.add(case); db.flush()
    evidence(db, user, case.id, 'case_requested', kind=kind, identity_basis='current_password', policy_sha256=POLICY_HASH)
    db.commit()
    return view(case)


def claim_case(db, case, expected, **fields):
    result = db.execute(update(PrivacyCase).where(PrivacyCase.id == case.id, PrivacyCase.version == expected)
        .values(**fields, version=PrivacyCase.version + 1, updated_at=utc_now()).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback(); db.refresh(case)
        raise HTTPException(409, {'code': 'refresh_required', 'current': view(case)})
    db.refresh(case)


def case_for(db, user, identity, *, admin=False):
    item = db.get(PrivacyCase, identity)
    if not item or (not admin and item.user_id != user.id):
        raise HTTPException(404, 'Privacy case not found')
    return item


def held(db, user_id, now):
    hold = db.get(PrivacyHold, user_id, populate_existing=True)
    return bool(hold and hold.active and utc(hold.expires_at) > utc(now))


def scrub_incident_text(db, identity):
    from app.sos_response_models import SosResponseEvent
    from app.identity_models import MutationAudit
    db.execute(update(SosResponseEvent).where(SosResponseEvent.sos_id == identity).values(
        reason='Free text removed by privacy policy', details={}, resident_message='Historical activity details removed by privacy policy'))
    db.execute(update(MutationAudit).where(MutationAudit.subject_type == 'sos', MutationAudit.subject_id == str(identity))
        .values(reason='Free text removed by privacy policy', before={}, after={}))


def decide(db, actor, case, payload):
    lock_account(db, case.user_id)
    if case.state in ('COMPLETED', 'REJECTED'):
        raise HTTPException(409, 'Closed case; refresh and review its recorded decision')
    if payload.state == 'COMPLETED':
        required = {'access': 'access_delivered', 'correction': 'correction_reviewed', 'erasure': 'erasure_external_verified'}[case.kind]
        if payload.decision_code != required or held(db, case.user_id, utc_now()):
            raise HTTPException(409, 'Correct fulfilment evidence and release of holds required')
        if case.kind == 'erasure' and case.state != 'AWAITING_EXTERNAL':
            raise HTTPException(409, 'Application erasure and external/backup review must precede completion')
    claim_case(db, case, payload.expected_version, state=payload.state,
               decision_code=payload.decision_code, evidence_sha256=payload.evidence_sha256)
    evidence(db, actor, case.id, 'case_decided', state=payload.state, decision_code=payload.decision_code,
             evidence_sha256=payload.evidence_sha256, version=case.version)
    db.commit()
    return view(case)


def change_hold(db, actor, user_id, payload):
    if not db.get(User, user_id):
        raise HTTPException(404, 'Account not found')
    now = utc_now()
    if payload.expires_at.tzinfo is None or not now < utc(payload.expires_at) <= now + timedelta(days=365):
        raise HTTPException(422, 'Hold must have an aware future expiry within one year; review before renewal')
    lock_account(db, user_id)
    row = db.get(PrivacyHold, user_id, populate_existing=True)
    if (row.version if row else 0) != payload.expected_version:
        raise HTTPException(409, 'Hold changed; refresh and review manually')
    fields = dict(active=payload.active, expires_at=payload.expires_at, reason_code=payload.reason_code,
                  evidence_sha256=payload.evidence_sha256, actor_id=actor.id)
    if row:
        db.execute(update(PrivacyHold).where(PrivacyHold.user_id == user_id, PrivacyHold.version == payload.expected_version)
                   .values(**fields, version=PrivacyHold.version + 1))
    else:
        db.add(PrivacyHold(user_id=user_id, version=1, **fields))
    evidence(db, actor, user_id, 'hold_changed', active=payload.active, evidence_sha256=payload.evidence_sha256,
             reason_code=payload.reason_code, version=payload.expected_version + 1)
    db.commit()
    return {'version': payload.expected_version + 1, **fields}


def export_page(db, user, *, after=0, limit=50):
    """Bounded own-record copy. Secrets and other residents' records are never selected."""
    from app.account_schemas import UserRead
    from app.sos_schemas import SosRead
    from app.operations_models import AccountPreference
    from app.governance_models import ResidentSubscription
    rows = db.scalars(select(SosRequest).where(SosRequest.user_id == user.id, SosRequest.id > after)
        .order_by(SosRequest.id).limit(limit + 1)).all()
    preferences = db.get(AccountPreference, user.id)
    subscriptions = db.scalars(select(ResidentSubscription).where(ResidentSubscription.user_id == user.id).limit(100)).all()
    result = dict(format='agapay-own-records-v1', generated_at=utc_now(), account=UserRead.model_validate(user),
        sos=[SosRead.model_validate(row) for row in rows[:limit]],
        next_after=rows[limit-1].id if len(rows) > limit else None,
        scope='Account, current preferences/subscriptions and paginated own SOS. Additional retained audit/delivery evidence is reviewed through an access case.',
        preferences={key: getattr(preferences, key) for key in ('notifications_enabled','locale','resident_area_id','requested_language')} if preferences else None,
        subscriptions=[{key: getattr(row, key) for key in ('kind','target_id','enabled')} for row in subscriptions])
    evidence(db, user, user.id, 'own_export_read', after=after, returned=len(rows[:limit]))
    db.commit()
    return result


def erase_resident(db, actor, case, expected_version, expected_account_version):
    """Explicit reviewed application erasure; archival/external fulfilment stays pending."""
    from app.config import get_settings
    from app.services.privacy_governance import approved_record
    if get_settings().environment == 'production':
        try: approved_record(get_settings().service_governance_path)
        except RuntimeError: raise HTTPException(503, 'Current organizational privacy review required') from None
    from app.identity_models import IdentityAction, IdentityMail, MutationAudit, MfaCredential, MfaRecoveryCode
    from app.operations_models import AccountPreference
    from app.governance_models import ResidentSubscription
    from app.delivery_models import ReceiptConsent
    if case.kind != 'erasure' or case.state != 'IN_REVIEW':
        raise HTTPException(409, 'Erasure case must be explicitly reviewed first')
    lock_account(db, case.user_id)
    user = db.get(User, case.user_id, populate_existing=True)
    if user.role != 'resident' or not user.is_active or user.version != expected_account_version:
        raise HTTPException(409, 'Resident account changed or requires separate staff-record review')
    if held(db, user.id, utc_now()) or db.scalar(select(func.count()).select_from(SosRequest).where(
        SosRequest.user_id == user.id, SosRequest.status != 'RESOLVED')):
        raise HTTPException(409, 'Unresolved SOS or active hold requires review; no erasure applied')
    claim_case(db, case, expected_version, state='AWAITING_EXTERNAL', decision_code='external_review')
    replacement = 'erased-' + str(uuid4())
    result = db.execute(update(User).where(User.id == user.id, User.version == expected_account_version)
        .values(name='Erased resident', email=replacement+'@privacy.invalid', phone='', barangay='', is_active=False,
                password_hash=passwords.hash(str(uuid4())+str(uuid4())), email_verified_at=None,
                version=User.version+1, updated_at=utc_now()))
    if result.rowcount != 1:
        db.rollback(); raise HTTPException(409, 'Account changed; refresh and review')
    revoke_sessions(db, user.id)
    actions = select(IdentityAction.token_hash).where(IdentityAction.user_id == user.id)
    db.execute(delete(IdentityMail).where(IdentityMail.action_hash.in_(actions)))
    db.execute(delete(IdentityAction).where(IdentityAction.user_id == user.id))
    from app.exercise_models import ExerciseConsent
    for model in (AccountPreference, ResidentSubscription, ReceiptConsent, MfaRecoveryCode, MfaCredential, ExerciseConsent):
        db.execute(delete(model).where(model.user_id == user.id))
    changed = db.execute(update(SosRequest).where(SosRequest.user_id == user.id, SosRequest.status == 'RESOLVED')
        .values(resident_name='Erased resident', phone='', barangay='', location='[Removed under privacy case]', message='',
                latitude=None, longitude=None, accuracy_m=None, location_recorded_at=None, location_source='redacted',
                resolution_note=None, version=SosRequest.version+1)).rowcount
    for identity in db.scalars(select(SosRequest.id).where(SosRequest.user_id == user.id)):
        scrub_incident_text(db, identity)
    # Narrow, explicitly audited privacy exception: remove profile snapshots/actor labels,
    # preserving event identity/action/time. Ordinary ORM edits remain forbidden.
    audits = db.execute(update(MutationAudit).where(MutationAudit.subject_type == 'account', MutationAudit.subject_id == str(user.id))
        .values(before={}, after={}, reason='Personal fields removed under privacy case')).rowcount
    db.execute(update(MutationAudit).where(MutationAudit.actor_id == user.id).values(actor_label='Erased resident'))
    evidence(db, actor, case.id, 'application_erasure', sos_records=changed, audit_snapshots=audits,
             account_id=user.id, policy_sha256=POLICY_HASH, external_and_backups='pending')
    db.commit()
    return view(case)


def retain(db, *, apply=False, now=None, limit=100):
    """Offline bounded pass; account locks serialize holds, registrations and erasure."""
    if not 1 <= limit <= 500: raise ValueError('Retention batch must be 1..500')
    if apply:
        from app.config import get_settings
        from app.services.privacy_governance import approved_record
        if get_settings().environment == 'production': approved_record(get_settings().service_governance_path)
    now = utc(now or utc_now())
    cutoff = now - timedelta(days=POLICY['resolved_sos_location_days'])
    narrative = now - timedelta(days=POLICY['resolved_sos_narrative_days'])
    def hold_condition(column):
        return exists(select(PrivacyHold.user_id).where(PrivacyHold.user_id==column, PrivacyHold.active.is_(True), PrivacyHold.expires_at>now))
    blocked = db.scalars(select(SosRequest.id).where(SosRequest.status=='RESOLVED', SosRequest.resolved_at<=cutoff,
        hold_condition(SosRequest.user_id)).limit(limit)).all()
    candidates = db.scalars(select(SosRequest).where(~hold_condition(SosRequest.user_id), SosRequest.status == 'RESOLVED', SosRequest.resolved_at <= cutoff,
        or_(SosRequest.latitude.is_not(None), SosRequest.longitude.is_not(None), SosRequest.location != '[Removed by retention]'))
        .order_by(SosRequest.id).limit(limit)).all()
    counts = dict(sos_location=0, sos_narrative=0, held=len(blocked), conflicts=0, identity_actions=0, disabled_push_tokens=0, uncertain_mail_held=0)
    for item in candidates:
        if apply: lock_account(db, item.user_id)
        if held(db, item.user_id, now): counts['held'] += 1; continue
        fields = dict(latitude=None, longitude=None, accuracy_m=None, location_recorded_at=None,
                      location='[Removed by retention]', location_source='redacted', message='', resolution_note=None)
        # Free text may itself contain exact location, phone numbers or other details.
        if utc(item.resolved_at) <= narrative:
            fields.update(resident_name='Retained incident reference', phone='', barangay='', message='', resolution_note=None)
            counts['sos_narrative'] += 1
        counts['sos_location'] += 1
        if apply:
            result = db.execute(update(SosRequest).where(SosRequest.id == item.id, SosRequest.version == item.version,
                SosRequest.status == 'RESOLVED', SosRequest.resolved_at <= cutoff)
                .values(**fields, version=SosRequest.version+1).execution_options(synchronize_session=False))
            if result.rowcount != 1: counts['conflicts'] += 1
            else: scrub_incident_text(db, item.id)
    # Handle narrative expiry on records whose structured location was already removed.
    expired = db.scalars(select(SosRequest).where(~hold_condition(SosRequest.user_id), SosRequest.status == 'RESOLVED', SosRequest.resolved_at <= narrative,
        SosRequest.location == '[Removed by retention]', SosRequest.resident_name != 'Retained incident reference')
        .order_by(SosRequest.id).limit(limit)).all()
    for item in expired:
        if apply: lock_account(db, item.user_id)
        if held(db, item.user_id, now): counts['held'] += 1; continue
        counts['sos_narrative'] += 1
        if apply:
            db.execute(update(SosRequest).where(SosRequest.id == item.id, SosRequest.version == item.version, SosRequest.status == 'RESOLVED')
                .values(resident_name='Retained incident reference', phone='', barangay='', message='', resolution_note=None, version=SosRequest.version+1))
    from app.identity_models import IdentityAction, IdentityMail
    expired_action = IdentityAction.expires_at < now-timedelta(days=POLICY['expired_identity_action_days'])
    uncertain_mail = exists(select(IdentityMail.id).where(IdentityMail.action_hash==IdentityAction.token_hash,
        IdentityMail.state.in_(('UNKNOWN','SENDING'))))
    # Keep ambiguous send evidence, without letting it occupy every cleanup batch.
    uncertain = db.scalars(select(IdentityAction.token_hash).where(expired_action, uncertain_mail).limit(limit)).all()
    counts['uncertain_mail_held'] = len(uncertain)
    actions = db.scalars(select(IdentityAction).where(~hold_condition(IdentityAction.user_id), expired_action, ~uncertain_mail)
        .order_by(IdentityAction.token_hash).limit(limit)).all()
    for action in actions:
        if apply and action.user_id: lock_account(db, action.user_id)
        if action.user_id and held(db, action.user_id, now): counts['held'] += 1; continue
        if db.scalar(select(IdentityMail.id).where(IdentityMail.action_hash==action.token_hash, IdentityMail.state.in_(('UNKNOWN','SENDING'))).limit(1)):
            counts['uncertain_mail_held'] += 1; continue
        counts['identity_actions'] += 1
        if apply:
            db.execute(delete(IdentityMail).where(IdentityMail.action_hash==action.token_hash))
            db.execute(delete(IdentityAction).where(IdentityAction.token_hash==action.token_hash, expired_action)
                .execution_options(synchronize_session='fetch'))
    devices = db.scalars(select(NotificationDevice).where(~hold_condition(NotificationDevice.user_id), NotificationDevice.enabled.is_(False), NotificationDevice.provider_token.is_not(None),
        NotificationDevice.last_seen_at < now-timedelta(days=POLICY['disabled_push_token_days'])).order_by(NotificationDevice.id).limit(limit)).all()
    for device in devices:
        if apply: lock_account(db, device.user_id)
        if held(db, device.user_id, now): counts['held'] += 1; continue
        counts['disabled_push_tokens'] += 1
        if apply: db.execute(update(NotificationDevice).where(NotificationDevice.id==device.id, NotificationDevice.revision==device.revision,
            NotificationDevice.enabled.is_(False)).values(provider_token=None, token_hash=None, revision=NotificationDevice.revision+1))
    if apply:
        evidence(db, None, POLICY_HASH, 'retention_applied', counts=counts, cutoff=cutoff.isoformat(), limit=limit)
        db.commit()
    return dict(mode='applied' if apply else 'dry_run', policy=POLICY, policy_sha256=POLICY_HASH, counts=counts,
                bounded=True, further_passes_may_be_required=True)


def access_review(db):
    import hashlib, json
    from app.governance_models import AuthorityGrant
    from app.identity_models import MfaCredential
    accounts = db.scalars(select(User).where(User.role.in_(('admin','officer'))).order_by(User.id).limit(1001)).all()
    grants = db.scalars(select(AuthorityGrant).order_by(AuthorityGrant.user_id, AuthorityGrant.authority_id).limit(5001)).all()
    if len(accounts)>1000 or len(grants)>5000: raise HTTPException(409, 'Access inventory exceeds review budget; use a reviewed offline report')
    snapshot = dict(accounts=[dict(id=row.id, role=row.role, active=row.is_active, version=row.version,
        mfa_enabled=db.get(MfaCredential,row.id) is not None) for row in accounts],
        authority_grants=[dict(user_id=row.user_id,authority_id=row.authority_id,revision=row.revision,active=row.active,
            area_ids=row.area_ids,station_ids=row.station_ids,citywide=row.citywide) for row in grants])
    return dict(snapshot=snapshot,sha256=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest())
