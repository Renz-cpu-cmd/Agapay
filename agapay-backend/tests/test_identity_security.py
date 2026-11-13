"""Synthetic identity transport and concurrency acceptance; no SMTP or external push."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import hmac
import time
from types import SimpleNamespace
from threading import Barrier
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, create_engine, text
from app.config import get_settings, Settings
from app.database import SessionLocal
from app.identity_models import IdentityAction, IdentityMail, MutationAudit, MfaCredential, MfaRecoveryCode
from app.models import User, AuthSession, NotificationDevice, utc_now
from app.services import identity_security as identity
from app.services.auth_abuse import AuthLimiter, request_ip
from app.identity_mail_worker import process_pending
from app.migrate_identity_security import migrate, require_schema
from test_accounts import account, headers, reset_accounts, staff, sign_in, PASSWORD
from test_notifications import resident, register, rows, TOKEN


@pytest.fixture
def mail(monkeypatch):
    settings=get_settings()
    for key,value in dict(identity_encryption_key=SecretStr(Fernet.generate_key().decode()),identity_mail_provider='smtp',
        smtp_host='smtp.synthetic.test',smtp_username='synthetic',smtp_password=SecretStr('synthetic-only-password'),
        smtp_sender='noreply@agapay.test',public_web_origin='https://agapay.test').items():monkeypatch.setattr(settings,key,value)
    return settings


def newest_code():
    with SessionLocal() as db:
        row=db.scalar(select(IdentityMail).order_by(IdentityMail.id.desc()))
        body=identity.cipher().decrypt(row.body_ciphertext.encode()).decode()
        return body.split('code in AGAPAY: ')[1].splitlines()[0]


def request_code(client,email='resident@example.com',purpose='password_reset'):
    response=client.post('/api/auth/recovery/request',json=dict(email=email,purpose=purpose))
    assert response.status_code==202,response.text
    return newest_code()


def test_recovery_is_unavailable_without_configuration_and_google_is_hidden(client):
    caps=client.get('/api/auth/capabilities').json()
    assert not caps['recovery_available'] and not caps['google_available']
    assert client.post('/api/auth/recovery/request',json={'email':'resident@example.com'}).status_code==503


def test_recovery_response_does_not_enumerate_accounts_or_expose_codes(client,mail):
    resident(client)
    one=client.post('/api/auth/recovery/request',json={'email':'resident@example.com'})
    two=client.post('/api/auth/recovery/request',json={'email':'unknown@example.com'})
    assert one.status_code==two.status_code==202 and one.json()==two.json()
    assert len(rows(IdentityMail))==1
    token=newest_code()
    assert token not in one.text and token not in rows(IdentityMail)[0].body_ciphertext


def test_password_recovery_single_use_revokes_sessions_and_push_and_never_auto_signs_in(client,mail):
    access=resident(client);register(client,access)
    code=request_code(client)
    result=client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD+'-new'})
    assert result.status_code==200 and 'access_token' not in result.json()
    assert client.get('/api/auth/me',headers=access).status_code==401
    assert all(not d.enabled and d.provider_token is None for d in rows(NotificationDevice))
    assert client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD+'-again'}).status_code==400
    assert sign_in(client,'resident@example.com',password=PASSWORD+'-new').status_code==200


@pytest.mark.parametrize('changed',['expired','account_version','superseded'])
def test_expired_or_changed_recovery_is_rejected(client,mail,changed):
    access=resident(client);code=request_code(client)
    with SessionLocal() as db:
        action=db.get(IdentityAction,identity.token_digest(code))
        if changed=='expired':action.expires_at=utc_now()-timedelta(seconds=1)
        if changed=='account_version':db.get(User,action.user_id).version+=1
        db.commit()
    if changed=='superseded':request_code(client)
    assert client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD+'-new'}).status_code==400
    assert client.get('/api/auth/me',headers=access).status_code==200


def test_verified_email_is_bound_to_current_contact_and_does_not_change_password(client,mail):
    access=resident(client);code=request_code(client,purpose='verify_email')
    assert client.post('/api/auth/recovery/complete',json={'token':code}).status_code==200
    data=client.get('/api/auth/me',headers=access).json()
    assert data['email_verified_at'] and data['version']==2
    assert sign_in(client,'resident@example.com').status_code==200


def test_invitation_is_verified_expiring_single_use_and_role_cannot_be_injected(client,mail):
    admin=staff(client)
    fields={key:value for key,value in account('invited@example.com').items() if key!='password'}
    assert client.post('/api/auth/invitations',headers=admin,json={**fields,'role':'officer','reason':'Synthetic reviewed staff invitation'}).status_code==202
    code=newest_code()
    with SessionLocal() as db:assert db.scalar(select(User).where(User.email=='invited@example.com')) is None
    assert client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD,'role':'admin'}).status_code==422
    assert client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD}).status_code==200
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='invited@example.com'))
        assert user.role=='officer' and user.email_verified_at
    assert client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD}).status_code==400


def test_shared_limit_survives_new_limiter_instances_and_separates_accounts(client):
    first,second=AuthLimiter(),AuthLimiter()
    first.hit('test-shared-identity',1)
    with pytest.raises(Exception) as error:second.hit('test-shared-identity',1)
    assert error.value.status_code==429
    second.hit('different-identity-same-office',1)


def test_signed_proxy_identity_requires_peer_key_timestamp_and_path(mail,monkeypatch):
    monkeypatch.setattr(mail,'auth_trusted_proxy_peers',['127.0.0.1/32'])
    monkeypatch.setattr(mail,'auth_proxy_key',SecretStr('synthetic-shared-proxy-key-at-least-32-characters'))
    timestamp=str(int(time.time()));address='198.51.100.5';path='/api/auth/login'
    signature=hmac.new(mail.auth_proxy_key.get_secret_value().encode(),f'{timestamp}\n{address}\nPOST\n{path}'.encode(),'sha256').hexdigest()
    request=SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'),method='POST',url=SimpleNamespace(path=path),headers={
        'x-forwarded-for':'1.2.3.4','x-agapay-client-ip':address,'x-agapay-client-time':timestamp,'x-agapay-client-signature':signature})
    assert request_ip(request)==address
    request.client.host='203.0.113.1';assert request_ip(request)=='203.0.113.1'
    request.client.host='127.0.0.1';request.url.path='/api/auth/setup';assert request_ip(request)=='127.0.0.1'
    request.url.path=path;request.headers['x-agapay-client-time']='1';assert request_ip(request)=='127.0.0.1'


@pytest.mark.parametrize('seconds,expected',[(59,'94287082'),(1111111109,'07081804'),(1111111111,'14050471'),(1234567890,'89005924'),(2000000000,'69279037'),(20000000000,'65353130')])
def test_totp_matches_official_rfc6238_sha1_vectors(seconds,expected):
    import base64
    assert identity.totp(base64.b32encode(b'12345678901234567890').decode(),seconds//30,digits=8)==expected


def enroll(client,mail):
    admin=staff(client)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.role=='admin'));user.email_verified_at=utc_now();db.commit()
    start=client.post('/api/auth/mfa/start',headers=admin,json={'current_password':PASSWORD})
    assert start.status_code==200,start.text
    data=start.json();code=identity.totp(data['secret'],int(time.time())//30)
    completed=client.post('/api/auth/mfa/verify',json={'challenge_token':data['challenge_token'],'code':code})
    assert completed.status_code==200,completed.text
    return admin,data,completed.json()


def test_mfa_enrollment_invalidates_old_sessions_and_recovery_codes_are_single_use(client,mail):
    old,setup,session=enroll(client,mail)
    assert client.get('/api/auth/me',headers=old).status_code==401
    access={'Authorization':'Bearer '+session['access_token']}
    assert client.get('/api/auth/security',headers=access).json()['mfa_enabled']
    challenge=sign_in(client,'admin@example.com','web')
    assert challenge.status_code==202 and 'access_token' not in challenge.json()
    payload={'challenge_token':challenge.json()['challenge_token'],'code':session['recovery_codes'][0]}
    verified=client.post('/api/auth/mfa/verify',json=payload)
    assert verified.status_code==200
    assert client.post('/api/auth/mfa/verify',json=payload).status_code==400
    again=sign_in(client,'admin@example.com','web').json()
    assert client.post('/api/auth/mfa/verify',json={**payload,'challenge_token':again['challenge_token']}).status_code==401
    raw=str([{'before':a.before,'after':a.after} for a in rows(MutationAudit)])
    for secret in [PASSWORD,TOKEN,setup['secret'],*session['recovery_codes']]:assert secret not in raw


def test_staff_password_recovery_preserves_mfa(client,mail):
    _,_,_=enroll(client,mail)
    code=request_code(client,'admin@example.com')
    assert client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD+'-changed'}).status_code==200
    assert sign_in(client,'admin@example.com','web',password=PASSWORD+'-changed').status_code==202
    with SessionLocal() as db:assert len(list(db.scalars(select(MfaCredential))))==1


def test_mfa_tries_are_durable_and_challenge_cannot_be_used_as_session(client,mail):
    _,_,_=enroll(client,mail)
    challenge=sign_in(client,'admin@example.com','web').json()['challenge_token']
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+challenge}).status_code==401
    for _ in range(5):assert client.post('/api/auth/mfa/verify',json={'challenge_token':challenge,'code':'WRONG-CODE'}).status_code==401
    assert client.post('/api/auth/mfa/verify',json={'challenge_token':challenge,'code':'WRONG-CODE'}).status_code==400


def test_mutations_require_version_reason_and_return_sanitized_current_on_conflict(client):
    admin=staff(client);access=resident(client)
    original=client.get('/api/auth/me',headers=access).json()
    assert client.patch('/api/auth/me',headers=access,json={'name':'No version'}).status_code==422
    saved=client.patch('/api/auth/me',headers=access,json={'expected_version':1,'name':'Newer name'})
    assert saved.status_code==200 and saved.json()['version']==2
    conflict=client.patch('/api/auth/me',headers=access,json={'expected_version':1,'name':'Stale name','password':PASSWORD+'-discard'})
    assert conflict.status_code==409 and conflict.json()['detail']['current']['name']=='Newer name'
    assert 'password' not in str(conflict.json())
    path=f'/api/users/{original["id"]}'
    assert client.patch(path,headers=admin,json={'expected_version':2,'role':'officer'}).status_code==422
    assert client.patch(path,headers=admin,json={'expected_version':2,'reason':'Reviewed role change','role':'officer'}).status_code==200
    audits=client.get('/api/auth/audit',headers=admin).json()
    assert any(a['action']=='account_admin_updated' and a['before']['role']=='resident' and a['after']['role']=='officer' for a in audits)


def test_two_editors_have_one_atomic_version_winner(client):
    access=resident(client);barrier=Barrier(2)
    def edit(name):
        barrier.wait();return client.patch('/api/auth/me',headers=access,json={'expected_version':1,'name':name})
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(edit,['Editor one','Editor two']))
    assert sorted(r.status_code for r in results)==[200,409]
    assert client.get('/api/auth/me',headers=access).json()['name']==next(r.json()['name'] for r in results if r.status_code==200)


def test_owned_session_revocation_is_private_and_deliberately_revokes_push(client):
    access=resident(client);register(client,access)
    other=resident(client,'other@example.com')
    listing=client.get('/api/auth/security',headers=access).json();session=listing['sessions'][0]
    assert 'token_hash' not in str(listing) and TOKEN not in str(listing)
    body={'session_id':session['id'],'reason':'Revoke my old signed-in installation'}
    assert client.post('/api/auth/security/revoke-session',headers=other,json=body).status_code==404
    assert client.post('/api/auth/security/revoke-session',headers=access,json=body).status_code==200
    assert client.get('/api/auth/me',headers=access).status_code==401
    assert not rows(NotificationDevice)[0].enabled


def test_mail_worker_never_replays_unknown_or_used_actions(client,mail):
    resident(client);request_code(client)
    calls=[]
    def ambiguous(recipient,body):calls.append(recipient);raise TimeoutError()
    assert process_pending(send=ambiguous)[0]['state']=='UNKNOWN'
    assert process_pending(send=ambiguous)==[] and len(calls)==1
    code=request_code(client)
    client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD+'-new'})
    assert process_pending(send=ambiguous)[0]['state']=='SUPPRESSED' and len(calls)==1


@pytest.mark.parametrize('changed',['deactivated','version','contact'])
def test_mail_worker_rechecks_current_account_before_disclosure(client,mail,changed):
    resident(client);request_code(client)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='resident@example.com'))
        if changed=='deactivated':user.is_active=False
        if changed=='version':user.version+=1
        if changed=='contact':user.email='changed@example.invalid'
        db.commit()
    assert process_pending(send=lambda *_:pytest.fail('Changed account must not disclose an old recovery link'))[0]['state']=='SUPPRESSED'


def test_application_erasure_serializes_with_identity_send_boundary(client,mail):
    from concurrent.futures import TimeoutError as FutureTimeout
    from threading import Event
    from app.privacy_models import PrivacyCase
    from app.services.privacy import erase_resident
    resident(client);request_code(client);staff(client)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='resident@example.com'))
        case=PrivacyCase(user_id=user.id,kind='erasure',state='IN_REVIEW',due_at=utc_now()+timedelta(days=15))
        db.add(case);db.commit();case_id=case.id
    sending=Event();release=Event();erasing=Event();calls=[]
    def controlled_send(*args):
        calls.append('synthetic send boundary');sending.set()
        assert release.wait(5)
    def erase():
        with SessionLocal() as db:
            actor=db.scalar(select(User).where(User.role=='admin'))
            erasing.set()
            return erase_resident(db,actor,db.get(PrivacyCase,case_id),1,1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        delivery=pool.submit(process_pending,send=controlled_send)
        try:
            assert sending.wait(5)
            deletion=pool.submit(erase);assert erasing.wait(5)
            with pytest.raises(FutureTimeout):deletion.result(timeout=0.2)
        finally:release.set()
        assert delivery.result(timeout=10)[0]['state']=='SENT'
        assert deletion.result(timeout=10)['state']=='AWAITING_EXTERNAL'
    assert calls==['synthetic send boundary']
    assert process_pending(send=lambda *_:pytest.fail('No recovery mail after erasure'))==[]


def test_identity_migration_preserves_accounts_sessions_and_backfills_nonsecret_ids(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'old.db'))
    with engine.begin() as db:
        db.execute(text('CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT)'))
        db.execute(text('CREATE TABLE auth_sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER)'))
        db.execute(text("INSERT INTO users VALUES(7,'Preserved')"));db.execute(text("INSERT INTO auth_sessions VALUES('synthetic-hash',7)"))
    with pytest.raises(RuntimeError):require_schema(engine)
    assert migrate(engine)['columns']
    migrate(engine,apply=True);assert migrate(engine,apply=True)=={'columns':[],'tables':[]}
    with engine.connect() as db:
        assert db.execute(text('SELECT version FROM users WHERE id=7')).scalar()==1
        assert len(db.execute(text('SELECT public_id FROM auth_sessions')).scalar())==36


def test_production_defaults_are_rejected():
    with pytest.raises(ValidationError):Settings(environment='production')


def test_two_recovery_consumers_cannot_change_password_twice(client,mail):
    resident(client);code=request_code(client);barrier=Barrier(2)
    def recover(suffix):
        barrier.wait();return client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD+suffix})
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(recover,['-one','-two']))
    assert sorted(r.status_code for r in results)==[200,400]


def test_expired_invitation_does_not_create_a_staff_account(client,mail):
    admin=staff(client);fields={key:value for key,value in account('expired-invite@example.com').items() if key!='password'}
    client.post('/api/auth/invitations',headers=admin,json={**fields,'role':'officer','reason':'Synthetic invitation expiry acceptance'})
    code=newest_code()
    with SessionLocal() as db:
        db.get(IdentityAction,identity.token_digest(code)).expires_at=utc_now()-timedelta(seconds=1);db.commit()
    assert client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD}).status_code==400
    with SessionLocal() as db:assert db.scalar(select(User).where(User.email==fields['email'])) is None


def test_expired_mfa_and_replayed_totp_are_rejected(client,mail):
    _,setup,_=enroll(client,mail)
    challenge=sign_in(client,'admin@example.com','web').json()['challenge_token']
    old_code=identity.totp(setup['secret'],int(time.time())//30)
    assert client.post('/api/auth/mfa/verify',json={'challenge_token':challenge,'code':old_code}).status_code==401
    with SessionLocal() as db:
        db.get(IdentityAction,identity.token_digest(challenge)).expires_at=utc_now()-timedelta(seconds=1);db.commit()
    assert client.post('/api/auth/mfa/verify',json={'challenge_token':challenge,'code':old_code}).status_code==400


def test_office_successes_do_not_share_a_global_login_quota(client,monkeypatch):
    # Isolate quota accounting from password-cost testing; real password verification is covered above.
    import app.routers.auth as auth_router
    monkeypatch.setattr(auth_router,'verify_password',lambda password,user:user is not None)
    with SessionLocal() as db:
        db.add_all([User(name=f'Office {i}',email=f'office{i}@example.com',password_hash='synthetic-limiter-only',role='resident',phone='09123456789',barangay='Synthetic office') for i in range(301)])
        db.commit()
    for i in range(301):assert sign_in(client,f'office{i}@example.com').status_code==200


def test_explicit_complete_production_configuration_is_accepted():
    settings=Settings(_env_file=None,environment='production',deployment_confirmed=True,local_admin_setup_enabled=False,
        seed_demo_data=False,prediction_preview_enabled=False,staff_mfa_required=True,
        identity_encryption_key=Fernet.generate_key().decode(),public_web_origin='https://agapay.test',public_api_origin='https://api.agapay.test',
        identity_mail_provider='smtp',smtp_host='smtp.test',smtp_username='synthetic',smtp_password='synthetic',
        smtp_sender='noreply@agapay.test',database_url='postgresql+psycopg://synthetic:synthetic@database.agapay.test/agapay?sslmode=verify-full&sslrootcert=/synthetic/ca.pem')
    assert settings.staff_mfa_required and not settings.local_admin_setup_enabled


def test_audit_api_has_no_mutation_operation_and_orm_audit_is_append_only(client):
    admin=staff(client)
    assert client.patch('/api/auth/audit',headers=admin,json={'before':{}}).status_code==405
    with SessionLocal() as db:
        row=db.scalar(select(MutationAudit));row.reason='Attempted rewrite'
        with pytest.raises(ValueError,match='append-only'):db.commit()
        db.rollback()


def test_account_body_budget_rejects_oversized_and_unframed_requests(client):
    assert client.post('/api/auth/login',content=b'x'*16385).status_code==413
    assert client.post('/api/auth/recovery/request',content=iter([b'x'*9000,b'y'*9000])).status_code==413
