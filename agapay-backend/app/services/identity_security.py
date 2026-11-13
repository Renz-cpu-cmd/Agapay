"""Account recovery, invitations and RFC 6238 TOTP with durable one-use state."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta
from urllib.parse import quote, urlencode
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from app.account_schemas import RegisterRequest, UserRead
from app.config import get_settings
from app.identity_models import IdentityAction, IdentityMail, MfaCredential, MfaRecoveryCode
from app.models import User, utc_now
from app.services.accounts import commit_account, create_user, issue_session, lock_account, passwords, revoke_sessions, token_digest
from app.services.mutation_audit import record, snapshot
from app.services.station_security import utc

GENERIC_REQUEST='If an eligible account exists, a time-limited email will be sent. Check your inbox and spam folder.'


def cipher(settings=None):
    settings=settings or get_settings()
    try:return Fernet(settings.identity_encryption_key.get_secret_value().encode())
    except (ValueError,TypeError):raise HTTPException(503,'Identity protection is not configured') from None


def capabilities(settings=None):
    settings=settings or get_settings()
    from urllib.parse import urlsplit
    origin=urlsplit(settings.public_web_origin)
    valid_origin=bool(origin.hostname and origin.scheme in ('http','https') and origin.path in ('','/') and not (origin.username or origin.password or origin.query or origin.fragment))
    recovery=bool(settings.identity_mail_provider=='smtp' and settings.smtp_host and settings.smtp_sender and settings.smtp_username
                  and settings.smtp_password.get_secret_value() and settings.identity_encryption_key.get_secret_value() and valid_origin)
    return dict(recovery_available=recovery,invitations_available=recovery,
                mfa_available=bool(settings.identity_encryption_key.get_secret_value()),staff_mfa_required=settings.staff_mfa_required,
                google_available=False,method='verified email and authenticator TOTP',
                recovery_unavailable_reason='' if recovery else 'Email recovery is unavailable on this installation. Contact your AGAPAY operator.')


def require_mail():
    if not capabilities()['recovery_available']:raise HTTPException(503,'Email recovery is unavailable on this installation')


def expected_version(user, version):
    if user.version!=version:
        raise HTTPException(409,dict(message='This record changed. Refresh and manually review before saving again.',current=UserRead.model_validate(user).model_dump(mode='json')))


def new_action(db,purpose,user=None,*,email=None,payload=None,minutes=30,secret=None):
    token=secrets.token_urlsafe(32)
    action=IdentityAction(token_hash=token_digest(token),purpose=purpose,user_id=user.id if user else None,
        account_version=user.version if user else None,email=email or (user.email if user else None),payload=payload or {},
        secret_ciphertext=secret,expires_at=utc_now()+timedelta(minutes=minutes))
    db.add(action);db.flush()
    return action,token


def enqueue_mail(db,action,token):
    settings=get_settings()
    link=settings.public_web_origin.rstrip('/')+'/recover#'+urlencode({'token':token,'action':action.purpose})
    body=f'AGAPAY {action.purpose.replace("_"," ")}\n\nOpen {link}\n\nOr paste this one-use code in AGAPAY: {token}\nExpires: {utc(action.expires_at).isoformat()}\nIf you did not request this, ignore it. No change occurs until confirmation.'
    db.add(IdentityMail(action_hash=action.token_hash,recipient=action.email,body_ciphertext=cipher().encrypt(body.encode()).decode(),expires_at=action.expires_at))


def request_recovery(db,email,purpose):
    require_mail()
    user=db.scalar(select(User).where(User.email==email,User.is_active.is_(True)))
    if user:
        lock_account(db,user.id);db.refresh(user)
        if not user.is_active or user.email != email:
            db.rollback(); return {'message':GENERIC_REQUEST}
        db.execute(update(IdentityAction).where(IdentityAction.user_id==user.id,IdentityAction.purpose==purpose,IdentityAction.used_at.is_(None)).values(used_at=utc_now()))
        action,token=new_action(db,purpose,user)
        enqueue_mail(db,action,token)
        record(db,None,'account',user.id,'recovery_requested',purpose,after={'version':user.version})
        db.commit()
    return {'message':GENERIC_REQUEST}


def live_action(db,token,purposes):
    row=db.get(IdentityAction,token_digest(token),populate_existing=True)
    if not row or row.purpose not in purposes or row.used_at or utc(row.expires_at)<=utc_now() or row.attempts>=5:
        raise HTTPException(400,'The code is invalid, expired or already used. Request a new one.')
    return row


def consume(db,action):
    result=db.execute(update(IdentityAction).where(IdentityAction.token_hash==action.token_hash,IdentityAction.used_at.is_(None),IdentityAction.expires_at>utc_now()).values(used_at=utc_now()).execution_options(synchronize_session=False))
    if result.rowcount!=1:raise HTTPException(400,'The code was already used or expired.')


def complete_recovery(db,token,new_password):
    action=live_action(db,token,('password_reset','verify_email','invitation'))
    if action.purpose=='invitation':
        lock_account(db,action.payload['issuer_id'])
        action=live_action(db,token,('invitation',))
        issuer=db.get(User,action.payload['issuer_id'],populate_existing=True)
        if not issuer or not issuer.is_active or issuer.role!='admin' or issuer.version!=action.payload['issuer_version']:
            raise HTTPException(400,'The inviting administrator changed; request a reviewed new invitation')
        consume(db,action)
        if not new_password:raise HTTPException(422,'Choose a new password')
        fields=action.payload['profile']
        user=create_user(db,RegisterRequest(**fields,password=new_password),action.payload['role'],commit=False)
        user.email_verified_at=utc_now()
        record(db,None,'account',user.id,'invitation_accepted','Verified invitation email ownership',after={**snapshot(user),'email_verified':True})
    else:
        lock_account(db,action.user_id)
        action=live_action(db,token,('password_reset','verify_email'))
        user=db.get(User,action.user_id,populate_existing=True)
        if not user or not user.is_active or user.version!=action.account_version or user.email!=action.email:
            raise HTTPException(400,'Account changed; request a new code')
        if action.purpose=='password_reset' and not new_password:raise HTTPException(422,'Choose a new password')
        consume(db,action);before=snapshot(user)
        if action.purpose=='password_reset':
            user.password_hash=passwords.hash(new_password);revoke_sessions(db,user.id)
        user.email_verified_at=utc_now();user.version+=1
        # All prior actions are version-bound; password recovery never clears MFA.
        record(db,user,'account',user.id,action.purpose,'Verified email token consumed',before,{**snapshot(user),'password_changed':action.purpose=='password_reset','email_verified':True})
    commit_account(db)
    return {'message':'Completed. Sign in again. Existing MFA remains required.'}


def invite(db,actor,payload):
    require_mail()
    lock_account(db,actor.id)
    if db.scalar(select(User.id).where(User.email==str(payload.email))):raise HTTPException(409,'This email already has an account; review it before inviting')
    # Earlier invitations are invalidated without ever creating a privileged account at a caller-supplied password.
    db.execute(update(IdentityAction).where(IdentityAction.email==str(payload.email),IdentityAction.purpose=='invitation',IdentityAction.used_at.is_(None)).values(used_at=utc_now()))
    fields=payload.model_dump(exclude={'role','reason'},mode='json')
    action,token=new_action(db,'invitation',email=str(payload.email),payload={'profile':fields,'role':payload.role,'issuer_id':actor.id,'issuer_version':actor.version},minutes=1440)
    enqueue_mail(db,action,token)
    record(db,actor,'invitation',action.token_hash[:16],'invitation_created',payload.reason,after={'email':str(payload.email),'role':payload.role})
    commit_account(db)
    return {'message':'Invitation queued for verified email acceptance. No account session has been issued.','expires_at':action.expires_at}


def totp(secret,step,*,digits=6):
    """RFC 4226 dynamic truncation with RFC 6238's 30-second counter; tested against RFC vectors."""
    key=base64.b32decode(secret,casefold=True)
    value=hmac.new(key,struct.pack('>Q',step),'sha1').digest();offset=value[-1]&15
    number=struct.unpack('>I',value[offset:offset+4])[0]&0x7fffffff
    return str(number%(10**digits)).zfill(digits)


def totp_step(secret,code,last_step=-1):
    if not code.isdigit() or len(code)!=6:return None
    current=int(time.time())//30
    for step in (current,current-1,current+1):
        if step>last_step and hmac.compare_digest(totp(secret,step),code):return step
    return None


def verify_factor(db,user,code):
    credential=db.get(MfaCredential,user.id,populate_existing=True)
    if not credential:return False
    secret=cipher().decrypt(credential.secret_ciphertext.encode()).decode()
    step=totp_step(secret,code,credential.last_step)
    if step is not None:
        result=db.execute(update(MfaCredential).where(MfaCredential.user_id==user.id,MfaCredential.last_step<step).values(last_step=step))
        return result.rowcount==1
    digest=token_digest(code.strip().replace('-','').upper())
    changed=db.execute(update(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id,MfaRecoveryCode.code_hash==digest,MfaRecoveryCode.used_at.is_(None)).values(used_at=utc_now()))
    return changed.rowcount==1


def mfa_challenge(db,user,*,enrollment=False):
    secret=base64.b32encode(secrets.token_bytes(20)).decode() if enrollment else None
    action,token=new_action(db,'mfa_enroll' if enrollment else 'mfa_login',user,minutes=5,
        secret=cipher().encrypt(secret.encode()).decode() if secret else None)
    record(db,user,'account',user.id,'mfa_challenge_created','Password verified; restricted MFA challenge only',after={'mfa_enabled':not enrollment})
    db.commit()
    result={'challenge_token':token,'expires_at':action.expires_at,'mfa_enrollment_required':enrollment}
    if secret:
        result.update(secret=secret,otpauth_uri=f'otpauth://totp/{quote("AGAPAY:"+user.email,safe="")}?'+urlencode({'secret':secret,'issuer':'AGAPAY','algorithm':'SHA1','digits':6,'period':30}))
    return result


def complete_mfa(db,token,code):
    action=live_action(db,token,('mfa_login','mfa_enroll'))
    from app.services.auth_abuse import limiter
    limiter.hit('mfa-account:'+str(action.user_id),15)
    lock_account(db,action.user_id)
    action=live_action(db,token,('mfa_login','mfa_enroll'))
    user=db.get(User,action.user_id,populate_existing=True)
    if not user or not user.is_active or user.role not in ('admin','officer') or user.version!=action.account_version:
        raise HTTPException(400,'Account changed; sign in again')
    recovery_codes=[]
    if action.purpose=='mfa_enroll':
        secret=cipher().decrypt(action.secret_ciphertext.encode()).decode()
        step=totp_step(secret,code)
        valid=step is not None
    else:valid=verify_factor(db,user,code)
    if not valid:
        action.attempts+=1
        record(db,user,'account',user.id,'mfa_verification_failed','Invalid authenticator or recovery code')
        db.commit()
        raise HTTPException(401,'Authenticator/recovery code is invalid or already used')
    consume(db,action)
    if action.purpose=='mfa_enroll':
        previous=db.get(MfaCredential,user.id)
        if previous:db.delete(previous);db.flush()
        db.add(MfaCredential(user_id=user.id,secret_ciphertext=action.secret_ciphertext,last_step=step))
        db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id))
        for _ in range(10):
            raw=secrets.token_hex(10).upper();recovery_codes.append(raw)
            db.add(MfaRecoveryCode(user_id=user.id,code_hash=token_digest(raw)))
        revoke_sessions(db,user.id);user.version+=1
        record(db,user,'account',user.id,'mfa_enrolled','Authenticator possession verified; prior sessions revoked',after={'mfa_enabled':True,'version':user.version})
    else:record(db,user,'account',user.id,'mfa_verified','Authenticator or single-use recovery factor verified')
    # issue_session commits token consumption, enrollment, audit and new session together.
    session=issue_session(db,user,audience='web',mfa_verified=True)
    result=session.model_dump(mode='json')
    if recovery_codes:result['recovery_codes']=recovery_codes
    return result
