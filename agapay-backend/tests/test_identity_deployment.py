"""Deployment and recovery boundaries, independent of any configured external service."""
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from app.config import Settings
from app.database import SessionLocal
from app.identity_models import MutationAudit
from app.models import User
from app.serve_production import preflight
from test_accounts import reset_accounts, staff, PASSWORD, sign_in
from test_identity_security import mail, request_code, newest_code
from app.services import identity_security as identity
from app.identity_admin import recover
from app.services.mutation_audit import redact


def test_audit_redaction_removes_secrets_even_inside_allowlisted_collections():
    result=redact({'password':'hidden','area_ids':[{'id':'reviewed-area','provider_token':'hidden',
        'installation':{'secret':'hidden','config_hash':'public-config'}}], 'role':'officer'})
    assert result=={'area_ids':[{'id':'reviewed-area','installation':{'config_hash':'public-config'}}],'role':'officer'}


def test_production_entry_requires_explicit_service_environment(monkeypatch):
    monkeypatch.delenv('AGAPAY_ENVIRONMENT',raising=False)
    with pytest.raises(RuntimeError,match='explicitly'):preflight()


def test_invalid_production_configuration_never_prints_input_secrets():
    secret='synthetic-mail-password-that-must-not-appear'
    with pytest.raises(ValidationError) as error:Settings(_env_file=None,environment='production',smtp_password=secret)
    assert secret not in str(error.value)


def test_required_staff_mfa_cannot_issue_an_ordinary_password_only_session(client,mail,monkeypatch):
    original=staff(client)
    code=request_code(client,'admin@example.com','verify_email')
    assert client.post('/api/auth/recovery/complete',json={'token':code}).status_code==200
    monkeypatch.setattr(mail,'staff_mfa_required',True)
    assert client.get('/api/auth/me',headers=original).status_code==401
    challenge=sign_in(client,'admin@example.com','web')
    assert challenge.status_code==202 and challenge.json()['mfa_enrollment_required']
    assert 'access_token' not in challenge.json()


def test_changed_inviter_cannot_leave_a_privileged_invitation_usable(client,mail):
    access=staff(client)
    body=dict(name='Invited staff',email='reviewed@example.com',phone='09123456789',barangay='Synthetic locality',role='admin',reason='Synthetic invitation authority review')
    assert client.post('/api/auth/invitations',headers=access,json=body).status_code==202
    code=newest_code()
    with SessionLocal() as db:
        db.scalar(select(User).where(User.role=='admin')).version+=1;db.commit()
    assert client.post('/api/auth/recovery/complete',json={'token':code,'password':PASSWORD}).status_code==400


def test_offline_recovery_requires_evidence_is_dry_run_by_default_and_is_audited(client,mail):
    staff(client)
    code=request_code(client,'admin@example.com','verify_email')
    client.post('/api/auth/recovery/complete',json={'token':code})
    fields=dict(email='admin@example.com',operator='Synthetic operator identity',reason='Reviewed loss of all staff factors',evidence='Synthetic reviewed identity evidence only')
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.role=='admin'));before=user.version
        assert recover(db,**fields)['apply'] is False and user.version==before
        assert recover(db,**fields,apply=True)['apply'] is True
        audit=db.scalar(select(MutationAudit).where(MutationAudit.action=='offline_mfa_recovery'))
        assert audit and audit.actor_label.startswith('Deployment operator:') and audit.after['credentials_revoked']
