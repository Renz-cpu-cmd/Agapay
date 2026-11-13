"""Bounded SMTP delivery. A claimed/ambiguous message is never automatically replayed."""
import argparse
import smtplib
import ssl
from email.message import EmailMessage
from sqlalchemy import select, update
from app.config import get_settings
from app.database import SessionLocal
from app.identity_models import IdentityAction, IdentityMail
from app.models import User, utc_now
from app.services.identity_security import cipher, require_mail


def smtp_send(recipient,body):
    settings=get_settings()
    message=EmailMessage();message['From']=settings.smtp_sender;message['To']=recipient
    message['Subject']='AGAPAY account security';message.set_content(body)
    connection=(smtplib.SMTP_SSL(settings.smtp_host,settings.smtp_port,timeout=10,context=ssl.create_default_context())
                if settings.smtp_tls_mode=='ssl' else smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=10))
    with connection as smtp:
        if settings.smtp_tls_mode=='starttls':smtp.starttls(context=ssl.create_default_context())
        smtp.login(settings.smtp_username,settings.smtp_password.get_secret_value())
        smtp.send_message(message)


def process_pending(*,limit=20,send=smtp_send,session_factory=SessionLocal):
    if not 1<=limit<=100:raise ValueError('Limit must be 1..100')
    with session_factory() as db:
        from app.services.privacy_governance import require_released
        require_released(db)
    require_mail()
    with session_factory() as db:
        ids=list(db.scalars(select(IdentityMail.id).where(IdentityMail.state=='PENDING').order_by(IdentityMail.id).limit(limit)))
    outcomes=[]
    for identity in ids:
        with session_factory() as db:
            claimed=db.execute(update(IdentityMail).where(IdentityMail.id==identity,IdentityMail.state=='PENDING').values(state='SENDING'))
            db.commit()
            if claimed.rowcount!=1:continue
            row=db.get(IdentityMail,identity)
            if row is None:continue # A reviewed erasure may have removed it after claim.
            action=db.get(IdentityAction,row.action_hash)
            if action is not None and action.user_id is not None:
                # Keep the account lock through the send boundary. Erasure either
                # wins before this recheck or waits for this recorded outcome.
                # The committed SENDING claim still prevents replay after a crash.
                from app.services.accounts import lock_account
                lock_account(db,action.user_id)
                row=db.get(IdentityMail,identity,populate_existing=True)
                if row is None:continue
                action=db.get(IdentityAction,row.action_hash,populate_existing=True)
            from app.services.station_security import utc
            suppressed=utc(row.expires_at)<=utc_now() or action is None or action.used_at is not None
            if action is not None and action.user_id is not None:
                user=db.get(User,action.user_id,populate_existing=True)
                suppressed=suppressed or user is None or not user.is_active or user.version!=action.account_version or user.email!=row.recipient
            recipient=row.recipient
            try:body=cipher().decrypt(row.body_ciphertext.encode()).decode() if not suppressed else ''
            except Exception:suppressed=True;body=''
            state='SUPPRESSED'
            if not suppressed:
                import time
                started=time.perf_counter()
                try:send(recipient,body);state='SENT'
                except Exception:state='UNKNOWN' # Includes uncertain acceptance; no blind replay.
                from app.services import observability as obs
                obs.observe('identity.delivery',time.perf_counter()-started,failed=state=='UNKNOWN')
            row.state=state;row.completed_at=utc_now();db.commit()
        outcomes.append({'id':identity,'state':state})
    return outcomes


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args();print(process_pending(limit=args.limit))
