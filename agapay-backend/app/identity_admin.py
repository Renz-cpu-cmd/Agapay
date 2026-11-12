"""Offline, custody-controlled MFA recovery. Defaults to inspection; never resets a password or prints secrets."""
import argparse
from sqlalchemy import delete, select
from app.database import SessionLocal
from app.identity_models import MfaCredential, MfaRecoveryCode
from app.models import User
from app.services.accounts import lock_account, revoke_sessions
from app.services.mutation_audit import record, snapshot


def recover(db,*,email,operator,reason,evidence,apply=False):
    if min(len(operator.strip()),len(reason.strip()),len(evidence.strip()))<10:raise ValueError('Operator identity, recovery reason and reviewed identity evidence are required (10+ characters each)')
    if len(operator)>135 or len(reason)+len(evidence)>950:raise ValueError("Recovery audit fields exceed their storage bounds")
    user=db.scalar(select(User).where(User.email==email,User.role.in_(('admin','officer')),User.is_active.is_(True)))
    if not user:raise ValueError('Active staff account not found')
    if not user.email_verified_at:raise ValueError('Verify the staff contact through the email workflow before offline factor recovery')
    if apply:
        lock_account(db,user.id);db.refresh(user);before=snapshot(user)
        db.execute(delete(MfaCredential).where(MfaCredential.user_id==user.id))
        db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id))
        revoke_sessions(db,user.id);user.version+=1
        record(db,None,'account',user.id,'offline_mfa_recovery',reason+'; evidence: '+evidence,before,{**snapshot(user),'mfa_enabled':False,'credentials_revoked':True},actor_label='Deployment operator: '+operator)
        db.commit()
    return {'apply':apply,'account_id':user.id,'next_step':'Sign in using the unchanged password and verified contact, then enroll a new authenticator'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('email','operator','reason','evidence'):parser.add_argument('--'+field,required=True)
    parser.add_argument('--apply',action='store_true');args=vars(parser.parse_args())
    with SessionLocal() as db:print(recover(db,**args))
