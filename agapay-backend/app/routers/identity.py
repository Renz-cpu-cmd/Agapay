from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.database import get_db
from app.identity_models import IdentityAction, MfaCredential, MutationAudit
from app.identity_schemas import RecoveryRequest, RecoveryComplete, InvitationRequest, MfaVerify, MfaStart, SessionRevoke, DeviceRevoke, RevokeRequest
from app.models import AuthSession, NotificationDevice, User, utc_now
from app.services.accounts import bearer, current_user, require_admin, lock_account, revoke_session, revoke_sessions, token_digest, verify_password
from app.services.auth_abuse import limiter, request_ip
from app.services import identity_security as identity
from app.services.mutation_audit import record
from app.services.station_security import utc

router=APIRouter(prefix='/api/auth',tags=['identity security'])


@router.get('/capabilities')
def capabilities():return identity.capabilities()


@router.post('/recovery/request',status_code=202)
def recovery_request(payload:RecoveryRequest,request:Request,db:Session=Depends(get_db)):
    limiter.hit('recovery-account:'+str(payload.email),3,3600)
    limiter.hit('recovery-client:'+request_ip(request)+':'+str(payload.email),6,3600)
    return identity.request_recovery(db,str(payload.email),payload.purpose)


@router.post('/recovery/complete')
def recovery_complete(payload:RecoveryComplete,request:Request,db:Session=Depends(get_db)):
    limiter.hit('recovery-consume:'+token_digest(payload.token),10)
    return identity.complete_recovery(db,payload.token,payload.password)


@router.post('/invitations',status_code=202)
def invite(payload:InvitationRequest,credentials:HTTPAuthorizationCredentials=Depends(bearer),admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    limiter.hit('invite-actor:'+str(admin.id),20,3600)
    lock_account(db,admin.id)
    actor=current_user(credentials,db)
    if actor.role!='admin':raise HTTPException(403,'Administrator access required')
    return identity.invite(db,actor,payload)


@router.post('/mfa/verify')
def mfa_verify(payload:MfaVerify,request:Request,db:Session=Depends(get_db)):
    return identity.complete_mfa(db,payload.challenge_token,payload.code)


@router.post('/mfa/start')
def mfa_start(payload:MfaStart,credentials:HTTPAuthorizationCredentials=Depends(bearer),user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.hit('mfa-start:'+str(user.id),5)
    lock_account(db,user.id);user=current_user(credentials,db)
    if user.role not in ('admin','officer'):raise HTTPException(403,'Staff authenticator setup only')
    if not verify_password(payload.current_password,user):raise HTTPException(400,'Current password is incorrect')
    if not user.email_verified_at:raise HTTPException(403,'Verify your email before enrolling or rotating a staff authenticator')
    if db.get(MfaCredential,user.id) and (not payload.code or not identity.verify_factor(db,user,payload.code)):
        db.commit();raise HTTPException(400,'A fresh existing authenticator or recovery code is required to rotate MFA')
    return identity.mfa_challenge(db,user,enrollment=True)


@router.get('/security')
def security(user:User=Depends(current_user),credentials:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    return dict(version=user.version,email_verified=user.email_verified_at is not None,
        mfa_enabled=db.get(MfaCredential,user.id) is not None,
        sessions=[dict(id=s.public_id,audience=s.audience,created_at=utc(s.created_at),expires_at=utc(s.expires_at),
                      current=s.token_hash==token_digest(credentials.credentials),mfa_verified=s.mfa_verified_at is not None)
                  for s in db.scalars(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.expires_at>utc_now()).order_by(AuthSession.created_at.desc()).limit(100))],
        devices=[dict(id=d.id,platform=d.platform,provider=d.provider,enabled=d.enabled,last_seen_at=d.last_seen_at)
                 for d in db.scalars(select(NotificationDevice).where(NotificationDevice.user_id==user.id).order_by(NotificationDevice.last_seen_at.desc()).limit(100))])


@router.post('/security/revoke-session')
def revoke_one(payload:SessionRevoke,user:User=Depends(current_user),credentials:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    lock_account(db,user.id);user=current_user(credentials,db)
    session=db.scalar(select(AuthSession).where(AuthSession.public_id==payload.session_id,AuthSession.user_id==user.id))
    if not session:raise HTTPException(404,'Owned session not found')
    revoke_session(db,session.token_hash)
    record(db,user,'account',user.id,'session_revoked',payload.reason,after={'session_id':session.public_id})
    db.commit();return {'message':'Session and its associated push authorization revoked'}


@router.post('/security/revoke-device')
def revoke_device(payload:DeviceRevoke,user:User=Depends(current_user),credentials:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    lock_account(db,user.id);user=current_user(credentials,db)
    device=db.get(NotificationDevice,payload.device_id,populate_existing=True)
    if not device or device.user_id!=user.id:raise HTTPException(404,'Owned device not found')
    from app.services.notification_service import disable_device
    if device.session_hash:revoke_session(db,device.session_hash)
    else:disable_device(device)
    record(db,user,'account',user.id,'push_device_revoked',payload.reason,after={'device_id':device.id,'enabled':False})
    db.commit();return {'message':'Device session and push authorization revoked; fresh sign-in is required'}


@router.post('/security/revoke-all')
def revoke_all(payload:RevokeRequest,user:User=Depends(current_user),credentials:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    lock_account(db,user.id);user=current_user(credentials,db)
    revoke_sessions(db,user.id)
    record(db,user,'account',user.id,'all_sessions_revoked',payload.reason,after={'credentials_revoked':True})
    db.commit();return {'message':'All sessions and push authorizations revoked. Sign in again.'}


@router.get('/audit',dependencies=[Depends(require_admin)])
def audit(subject_type:str|None=None,subject_id:str|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),db:Session=Depends(get_db)):
    query=select(MutationAudit)
    if subject_type:query=query.where(MutationAudit.subject_type==subject_type)
    if subject_id:query=query.where(MutationAudit.subject_id==subject_id)
    rows=db.scalars(query.order_by(MutationAudit.id.desc()).offset(offset).limit(limit))
    return [dict(id=r.id,actor_id=r.actor_id,actor_label=r.actor_label,subject_type=r.subject_type,subject_id=r.subject_id,
                 action=r.action,reason=r.reason,before=r.before,after=r.after,created_at=utc(r.created_at)) for r in rows]
