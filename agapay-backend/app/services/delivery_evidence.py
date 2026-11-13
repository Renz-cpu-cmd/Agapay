"""No blind replay. Provider, app callback and resident acknowledgement are distinct."""
from datetime import timedelta
import hashlib,hmac,secrets
from fastapi import HTTPException
from sqlalchemy import exists,func,or_,select,update
from app.config import get_settings
from app.models import NotificationDelivery,NotificationDevice,NotificationEvent,AlertTransition,User,utc_now
from app.delivery_models import DeliveryControl,DeliveryAttempt,DeliveryReceipt,DeliveryReview,ReceiptConsent
from app.governance_models import NotificationAudience,NotificationRecipient,AuthorityGrant,AlertAuthority,CitywideDispatch
from app.services.station_security import utc
from app.services.mutation_audit import record


def insert_for(db,model,values):
    from sqlalchemy.dialects.sqlite import insert as si
    from sqlalchemy.dialects.postgresql import insert as pi
    statement=(si if db.bind.dialect.name=='sqlite' else pi)(model).values(**values)
    return statement


def ensure_control(db,delivery):
    expiry=utc(delivery.created_at)+timedelta(seconds=get_settings().notification_ttl_seconds)
    db.execute(insert_for(db,DeliveryControl,dict(delivery_id=delivery.id,version=0,expires_at=expiry,review_status='unreviewed')).on_conflict_do_nothing())
    return db.get(DeliveryControl,delivery.id,populate_existing=True)


def lock_control(db,delivery_id):
    db.execute(update(DeliveryControl).where(DeliveryControl.delivery_id==delivery_id).values(version=DeliveryControl.version))
    return db.get(DeliveryControl,delivery_id,populate_existing=True)


def reviewed_condition():
    return exists(select(DeliveryControl.delivery_id).where(DeliveryControl.delivery_id==NotificationDelivery.id,DeliveryControl.review_status!='unreviewed'))


def observe_resident_stage(stage,delivery,recorded_at):
    from app.services import observability as obs
    elapsed=(utc(recorded_at)-utc(delivery.created_at)).total_seconds()
    if elapsed>=0:
        obs.observe({'RECEIVED':'notification.app_received','OPENED':'notification.app_opened',
            'ACKNOWLEDGED':'notification.user_acknowledged'}[stage],elapsed)
    else:obs.event('notification.receipt.clock_unconfirmed',state='unknown')


def begin_attempt(db,delivery,device,provider_mode):
    control=ensure_control(db,delivery)
    consent=db.get(ReceiptConsent,delivery.user_id)
    secret=secrets.token_urlsafe(32) if provider_mode=='fcm' and consent and consent.enabled else None
    attempt=DeliveryAttempt(delivery_id=delivery.id,attempt_no=delivery.attempts,device_revision=device.revision,
        receipt_hash=hashlib.sha256((secret+':'+str(consent.version)+':'+device.installation_id).encode()).hexdigest() if secret else None,outcome='claimed')
    db.add(attempt);control.version+=1
    delivery.provider_mode=provider_mode if provider_mode in ('fcm','test','disabled') else 'custom'
    return control,attempt,secret


def consent_read(db,user):
    value=db.get(ReceiptConsent,user.id,populate_existing=True)
    return dict(enabled=bool(value and value.enabled),version=value.version if value else 0,
        notice='Optional app receipt/open evidence for requested sensor notifications; no location. Acknowledgement is always an explicit action. Provider acceptance does not prove phone display.')


def update_consent(db,user,payload):
    db.execute(insert_for(db,ReceiptConsent,dict(user_id=user.id,version=0,enabled=False)).on_conflict_do_nothing())
    changed=db.execute(update(ReceiptConsent).where(ReceiptConsent.user_id==user.id,ReceiptConsent.version==payload.expected_version)
        .values(enabled=payload.enabled,version=ReceiptConsent.version+1).execution_options(synchronize_session=False))
    if changed.rowcount!=1:
        db.rollback();raise HTTPException(409,dict(message='Receipt preference changed. Refresh and review manually.',current=consent_read(db,user)))
    record(db,user,'notification_receipt_consent',user.id,'receipt_consent_changed','Resident changed optional delivery evidence preference',
        after=dict(enabled=payload.enabled,version=payload.expected_version+1))
    db.commit();return consent_read(db,user)


def capture_receipt(db,payload):
    attempt=db.get(DeliveryAttempt,(payload.delivery_id,payload.attempt_no))
    if not attempt or not attempt.receipt_hash:raise HTTPException(404,'Receipt capability unavailable')
    delivery=db.get(NotificationDelivery,payload.delivery_id)
    db.execute(update(ReceiptConsent).where(ReceiptConsent.user_id==delivery.user_id).values(version=ReceiptConsent.version))
    consent=db.get(ReceiptConsent,delivery.user_id,populate_existing=True)
    device=db.scalar(select(NotificationDevice).where(NotificationDevice.id==delivery.device_id).with_for_update().execution_options(populate_existing=True))
    user=db.get(User,delivery.user_id,populate_existing=True)
    if not device or device.user_id!=delivery.user_id or not device.enabled or not user or not user.is_active or user.role!='resident' or not consent or not consent.enabled:
        raise HTTPException(403,'Receipt permission withdrawn')
    supplied=hashlib.sha256((payload.receipt_token.get_secret_value()+':'+str(consent.version)+':'+device.installation_id).encode()).hexdigest()
    if not hmac.compare_digest(attempt.receipt_hash,supplied):raise HTTPException(404,'Receipt capability unavailable')
    control=lock_control(db,payload.delivery_id)
    if utc_now()>utc(attempt.started_at)+timedelta(days=get_settings().notification_receipt_days):raise HTTPException(410,'Receipt evidence window expired')
    # Repeated callbacks are idempotent. Never infer missing stages or alter send outcome.
    recorded_at=utc_now()
    values=dict(delivery_id=delivery.id,attempt_no=attempt.attempt_no,stage=payload.stage,basis='app_callback',reported_at=payload.reported_at,recorded_at=recorded_at)
    # RETURNING, not rowcount: PostgreSQL reports rowcount -1 (truthy) for this ORM-routed
    # INSERT ... ON CONFLICT, which bumped the version and metrics on every duplicate.
    inserted=db.execute(insert_for(db,DeliveryReceipt,values).on_conflict_do_nothing()
                        .returning(DeliveryReceipt.stage)).first() is not None
    if inserted:control.version+=1
    db.commit()
    if inserted:observe_resident_stage(payload.stage,delivery,recorded_at)
    return {'recorded':True,'stage':payload.stage,'evidence':'app_reported_callback; phone display is not independently verified'}


def delivery_query(db,user):
    query=(select(NotificationDelivery,NotificationEvent,AlertTransition,DeliveryControl)
        .join(NotificationEvent,NotificationEvent.id==NotificationDelivery.event_id)
        .join(AlertTransition,AlertTransition.id==NotificationEvent.transition_id)
        .outerjoin(DeliveryControl,DeliveryControl.delivery_id==NotificationDelivery.id))
    if user.role=='resident':return query.where(NotificationDelivery.user_id==user.id)
    if user.role=='admin':return query
    if user.role!='officer':raise HTTPException(403,'Delivery access unavailable')
    grants=list(db.scalars(select(AuthorityGrant).join(AlertAuthority,AlertAuthority.id==AuthorityGrant.authority_id)
        .where(AuthorityGrant.user_id==user.id,AuthorityGrant.active.is_(True),AlertAuthority.active.is_(True))))
    stations={value for grant in grants for value in grant.station_ids};areas={value for grant in grants for value in grant.area_ids}
    citywide={grant.authority_id for grant in grants if grant.citywide}
    allowed=or_(AlertTransition.station_id.in_(stations),exists(select(NotificationRecipient.delivery_id).where(
        NotificationRecipient.delivery_id==NotificationDelivery.id,NotificationRecipient.kind=='area',NotificationRecipient.target_id.in_(areas))),
        exists(select(CitywideDispatch.event_id).where(CitywideDispatch.event_id==NotificationDelivery.event_id,CitywideDispatch.authority_id.in_(citywide))))
    return query.where(allowed)


def read_rows(db,user,*,before_id=None,limit=30,state=None,delivery_id=None):
    query=delivery_query(db,user)
    if before_id:query=query.where(NotificationDelivery.id<before_id)
    if state:query=query.where(NotificationDelivery.state==state)
    if delivery_id:query=query.where(NotificationDelivery.id==delivery_id)
    rows=db.execute(query.order_by(NotificationDelivery.id.desc()).limit(limit).execution_options(populate_existing=True)).all()
    ids=[row[0].id for row in rows];attempts={};receipts={};reviews={}
    if ids:
        for value in db.scalars(select(DeliveryAttempt).where(DeliveryAttempt.delivery_id.in_(ids)).order_by(DeliveryAttempt.attempt_no)):
            attempts.setdefault(value.delivery_id,[]).append(value)
        for value in db.scalars(select(DeliveryReceipt).where(DeliveryReceipt.delivery_id.in_(ids))):receipts.setdefault(value.delivery_id,[]).append(value)
        for value in db.scalars(select(DeliveryReview).where(DeliveryReview.delivery_id.in_(ids)).order_by(DeliveryReview.id.desc()).limit(200)):
            reviews.setdefault(value.delivery_id,[]).append(value)
    items=[];now=utc_now()
    for delivery,event,transition,control in rows:
        stages=receipts.get(delivery.id,[]);trials=attempts.get(delivery.id,[])
        expiry=utc(control.expires_at) if control else utc(delivery.created_at)+timedelta(seconds=get_settings().notification_ttl_seconds)
        version=control.version if control else 0;review=control.review_status if control else 'unreviewed'
        accepted=delivery.provider_mode=='fcm' and (any(t.outcome=='accepted' for t in trials) or delivery.state=='SENT' and delivery.result_category=='accepted')
        item=dict(id=delivery.id,event_id=event.id,alert_id=transition.alert_id,station_id=transition.station_id,severity=transition.new_severity,
            state=delivery.state,provider=delivery.provider_mode,version=version,queued_at=utc(delivery.created_at).isoformat(),
            attempted_at=utc(delivery.attempted_at).isoformat() if delivery.attempted_at else None,expires_at=expiry.isoformat(),expired=now>=expiry,
            queue_age_seconds=max(0,(now-utc(delivery.created_at)).total_seconds()),review_status=review,
            review_required=delivery.state in ('PROCESSING','UNKNOWN') and review in ('unreviewed','followup_recorded'),
            provider_accepted=accepted,operator_attested_acceptance=review=='provider_accepted',conflicting_evidence=accepted and review=='not_accepted',
            receipt_stages=[dict(stage=r.stage,attempt_no=r.attempt_no,basis=r.basis,recorded_at=utc(r.recorded_at).isoformat(),
                reported_at=utc(r.reported_at).isoformat() if r.reported_at else None,client_time_verified=False) for r in stages],
            attempts=[dict(attempt_no=t.attempt_no,started_at=utc(t.started_at).isoformat(),outcome=t.outcome,
                provider_reported_at=utc(t.provider_reported_at).isoformat() if t.provider_reported_at else None,
                **({'provider_reference':t.provider_reference} if user.role!='resident' else {})) for t in trials],
            can_acknowledge=user.role=='resident' and bool(trials) and not any(r.stage=='ACKNOWLEDGED' for r in stages),
            notice='Provider acceptance, app callbacks and your acknowledgement are separate evidence. None confirms evacuation or guarantees phone display.')
        if user.role!='resident':
            item['reviews']=[dict(id=r.id,actor_id=r.actor_id,decision=r.decision,reason=r.reason,evidence_kind=r.evidence_kind,evidence_sha256=r.evidence_sha256,created_at=utc(r.created_at).isoformat()) for r in reviews.get(delivery.id,[])]
            item['can_reconcile']=user.role=='admin'
        items.append(item)
    return dict(items=items,next_before_id=items[-1]['id'] if len(items)==limit else None,checked_at=now.isoformat(),scope='own deliveries' if user.role=='resident' else 'authorized operational jurisdiction')


def detail(db,user,identity):
    result=read_rows(db,user,delivery_id=identity,limit=1)['items']
    if not result:raise HTTPException(404,'Delivery not found in your scope')
    return result[0]


def acknowledge(db,user,identity,payload):
    if user.role!='resident':raise HTTPException(403,'Resident acknowledgement required')
    delivery=db.get(NotificationDelivery,identity)
    if not delivery or delivery.user_id!=user.id:raise HTTPException(404,'Delivery not found')
    ensure_control(db,delivery);control=lock_control(db,identity)
    latest=db.scalar(select(DeliveryAttempt).where(DeliveryAttempt.delivery_id==identity).order_by(DeliveryAttempt.attempt_no.desc()).limit(1))
    if not latest:raise HTTPException(409,'No attempted notification to acknowledge')
    existing=db.get(DeliveryReceipt,(identity,latest.attempt_no,'ACKNOWLEDGED'))
    if existing:return detail(db,user,identity)
    changed=db.execute(update(DeliveryControl).where(DeliveryControl.delivery_id==identity,DeliveryControl.version==payload.expected_version)
        .values(version=DeliveryControl.version+1).execution_options(synchronize_session=False))
    if changed.rowcount!=1:
        db.rollback();raise HTTPException(409,dict(message='Delivery evidence changed. Refresh and review before acknowledging.',current=detail(db,user,identity)))
    recorded_at=utc_now()
    db.add(DeliveryReceipt(delivery_id=identity,attempt_no=latest.attempt_no,stage='ACKNOWLEDGED',basis='resident_action',recorded_at=recorded_at))
    db.commit();observe_resident_stage('ACKNOWLEDGED',delivery,recorded_at)
    return detail(db,user,identity)


def reconcile(db,user,identity,payload):
    if user.role!='admin':raise HTTPException(403,'Administrator reconciliation required')
    allowed=db.execute(update(User).where(User.id==user.id,User.role=='admin',User.is_active.is_(True)).values(version=User.version))
    if allowed.rowcount!=1:raise HTTPException(403,'Administrator access changed')
    delivery=db.get(NotificationDelivery,identity)
    if not delivery:raise HTTPException(404,'Delivery not found')
    ensure_control(db,delivery);control=lock_control(db,identity)
    if delivery.state=='PROCESSING' and delivery.attempted_at and (utc_now()-utc(delivery.attempted_at)).total_seconds()<=get_settings().operations_queue_age_seconds:
        raise HTTPException(409,'Send may still be in progress. Wait and refresh; no automatic retry.')
    if payload.decision in ('provider_accepted','not_accepted') and payload.evidence_kind!='provider_record':raise HTTPException(422,'A provider record is required for an acceptance decision')
    if payload.decision=='followup_recorded' and payload.evidence_kind!='fallback_action':raise HTTPException(422,'Record the actual fallback action evidence')
    before=dict(review_status=control.review_status,version=control.version)
    changed=db.execute(update(DeliveryControl).where(DeliveryControl.delivery_id==identity,DeliveryControl.version==payload.expected_version)
        .values(review_status=payload.decision,reviewed_at=utc_now(),version=DeliveryControl.version+1).execution_options(synchronize_session=False))
    if changed.rowcount!=1:
        db.rollback();raise HTTPException(409,dict(message='Delivery evidence changed. Refresh and review manually; no resend occurred.',current=detail(db,user,identity)))
    db.add(DeliveryReview(delivery_id=identity,actor_id=user.id,expected_version=payload.expected_version,decision=payload.decision,
        evidence_kind=payload.evidence_kind,evidence_sha256=payload.evidence_sha256,reason=payload.reason))
    record(db,user,'notification_delivery',identity,'delivery_reconciled',payload.reason,before,
        dict(review_status=payload.decision,version=payload.expected_version+1,evidence_kind=payload.evidence_kind,evidence_sha256=payload.evidence_sha256))
    # Immutable transport result remains UNKNOWN/PROCESSING as originally observed.
    # This decision stops future automatic attempts; it never queues a resend.
    db.commit();return detail(db,user,identity)
