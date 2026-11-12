"""Synthetic privacy cases/retention. Never selects deployment data or sends messages."""
from datetime import timedelta
import json
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select, update
from app.database import SessionLocal
from app.models import User, SosRequest, utc_now
from app.privacy_models import PrivacyCase, PrivacyEvent, PrivacyHold
from app.privacy_schemas import CaseDecision
from app.services import privacy
from app.services.privacy_governance import POLICY, POLICY_HASH, approved_record
from test_accounts import account, headers, reset_accounts, staff, sign_in, PASSWORD


def owner(client, email='privacy@example.com'):
    response = client.post('/api/auth/register', json=account(email)); assert response.status_code==201, response.text
    return headers(sign_in(client, email))


def request(client, access, kind='access'):
    return client.post('/api/privacy/cases', headers=access, json=dict(kind=kind, current_password=PASSWORD))


def closed(db, user_id, *, days=8, status='RESOLVED'):
    row=SosRequest(user_id=user_id, request_id=str(uuid4()), payload_hash='a'*64, resident_name='PRIVATE NAME',
        phone='+639123456789', barangay='PRIVATE AREA', location='PRIVATE EXACT ADDRESS', message='PRIVATE GPS narrative',
        latitude=15.97, longitude=120.57, location_source='gps', accuracy_m=2, location_recorded_at=utc_now()-timedelta(days=days),
        status=status, resolved_at=utc_now()-timedelta(days=days) if status=='RESOLVED' else None)
    db.add(row); db.commit(); return row


def test_notice_is_honest_and_secret_free_without_organizational_approval(client):
    response=client.get('/api/privacy/notice'); assert response.status_code==200
    assert response.json()['deployment']['status']=='unapproved_development'
    assert response.headers['cache-control']=='no-store'
    assert response.json()['policy']['approval'].startswith('unreviewed')


def test_owner_export_is_scoped_paginated_step_up_and_never_returns_credentials(client):
    one=owner(client); two=owner(client,'other-privacy@example.com')
    uid=client.get('/api/auth/me',headers=one).json()['id']; foreign=client.get('/api/auth/me',headers=two).json()['id']
    with SessionLocal() as db: closed(db,uid); closed(db,uid); closed(db,foreign)
    assert client.post('/api/privacy/export',headers=one,json={'current_password':'wrong'}).status_code==403
    page=client.post('/api/privacy/export?limit=1',headers=one,json={'current_password':PASSWORD})
    assert page.status_code==200, page.text
    assert len(page.json()['sos'])==1 and page.json()['next_after']
    assert page.json()['sos'][0]['user_id']==uid
    assert all(word not in page.text for word in ('password_hash','provider_token','token_hash','secret_ciphertext'))
    after=page.json()['next_after']
    last=client.post(f'/api/privacy/export?limit=1&after={after}',headers=one,json={'current_password':PASSWORD})
    assert len(last.json()['sos'])==1 and last.json()['next_after'] is None
    assert client.post('/api/privacy/export',json={'current_password':PASSWORD}).status_code==401


def test_cases_require_password_and_cannot_cross_owner_or_staff_scope(client):
    one=owner(client);two=owner(client,'other-privacy@example.com')
    first=request(client,one); assert first.status_code==202
    assert request(client,one).json()['id']==first.json()['id']
    assert client.get('/api/privacy/cases',headers=two).json()==[]
    assert client.get('/api/privacy/admin/cases',headers=one).status_code==403
    assert client.get('/api/privacy/admin/cases',headers=staff(client,'officer')).status_code==403
    assert request(client,one,'correction').json()['kind']=='correction'


def test_case_cas_does_not_retry_or_silently_overwrite_a_second_editor(client):
    access=owner(client); case=request(client,access).json(); admin=staff(client)
    url='/api/privacy/admin/cases/'+case['id']
    body=dict(expected_version=1,state='IN_REVIEW',decision_code='identity_review',evidence_sha256='a'*64)
    assert client.patch(url,headers=admin,json=body).status_code==200
    stale=client.patch(url,headers=admin,json=body)
    assert stale.status_code==409 and stale.json()['detail']['code']=='refresh_required'
    with SessionLocal() as db:
        assert db.get(PrivacyCase,case['id']).version==2
        assert len(db.scalars(select(PrivacyEvent).where(PrivacyEvent.action=='case_decided')).all())==1


def test_retention_dry_run_preserves_data_then_applies_only_closed_unheld_records(client):
    access=owner(client); uid=client.get('/api/auth/me',headers=access).json()['id']
    with SessionLocal() as db:
        recent=closed(db,uid,days=1); old=closed(db,uid,days=8); older=closed(db,uid,days=40); active=closed(db,uid,days=40,status='ACTIVE')
        result=privacy.retain(db); assert result['mode']=='dry_run'
        db.expire_all(); assert db.get(SosRequest,old.id).latitude==15.97
        privacy.retain(db,apply=True); db.expire_all()
        assert db.get(SosRequest,old.id).latitude is None
        assert db.get(SosRequest,old.id).message==''
        assert db.get(SosRequest,older.id).phone=='' and db.get(SosRequest,older.id).resident_name=='Retained incident reference'
        assert db.get(SosRequest,active.id).latitude==15.97 and db.get(SosRequest,recent.id).latitude==15.97
        assert db.get(SosRequest,old.id).request_id==old.request_id # Exact reference/digest survives; cannot create another SOS.
        events=db.scalars(select(PrivacyEvent).where(PrivacyEvent.action=='retention_applied')).all()
        assert len(events)==1 and 'PRIVATE' not in json.dumps(events[0].details)


def test_hold_blocks_retention_and_erasure_until_explicit_release(client):
    access=owner(client);uid=client.get('/api/auth/me',headers=access).json()['id'];admin=staff(client)
    body=dict(expected_version=0,active=True,expires_at=(utc_now()+timedelta(days=2)).isoformat(),reason_code='legal_review',evidence_sha256='a'*64)
    url=f'/api/privacy/admin/holds/{uid}'
    assert client.patch(url,headers=admin,json=body).status_code==200
    assert client.patch(url,headers=admin,json=body).status_code==409
    with SessionLocal() as db:
        row=closed(db,uid,days=40)
        assert privacy.retain(db,apply=True)['counts']['held']==1
        db.refresh(row);assert row.latitude==15.97
    body.update(expected_version=1,active=False)
    assert client.patch(url,headers=admin,json=body).status_code==200
    with SessionLocal() as db:
        privacy.retain(db,apply=True);assert db.get(SosRequest,row.id).latitude is None


def test_erasure_requires_review_versions_no_open_sos_and_external_completion(client):
    access=owner(client); uid=client.get('/api/auth/me',headers=access).json()['id'];admin=staff(client)
    case=request(client,access,'erasure').json();url='/api/privacy/admin/cases/'+case['id']
    body=dict(expected_version=1,state='COMPLETED',decision_code='erasure_external_verified',evidence_sha256='a'*64)
    assert client.patch(url,headers=admin,json=body).status_code==409
    body.update(state='IN_REVIEW',decision_code='identity_review')
    assert client.patch(url,headers=admin,json=body).status_code==200
    with SessionLocal() as db: row=closed(db,uid,status='ACTIVE')
    erase=dict(current_password=PASSWORD,expected_version=2,expected_account_version=1)
    assert client.post(url+'/application-erasure',headers=admin,json=erase).status_code==409
    with SessionLocal() as db:
        db.execute(update(SosRequest).where(SosRequest.id==row.id).values(status='RESOLVED',resolved_at=utc_now()));db.commit()
    result=client.post(url+'/application-erasure',headers=admin,json=erase)
    assert result.status_code==200,result.text
    assert result.json()['state']=='AWAITING_EXTERNAL'
    assert client.get('/api/auth/me',headers=access).status_code==401
    with SessionLocal() as db:
        user=db.get(User,uid); item=db.get(SosRequest,row.id)
        assert not user.is_active and user.email.endswith('@privacy.invalid') and user.phone==''
        assert item.latitude is None and item.phone=='' and item.message==''
        from app.identity_models import MutationAudit
        audits=db.scalars(select(MutationAudit).where(MutationAudit.subject_id==str(uid),MutationAudit.subject_type=='account')).all()
        assert all(a.before=={} and a.after=={} for a in audits)
    assert client.patch(url,headers=admin,json=dict(expected_version=3,state='COMPLETED',decision_code='erasure_external_verified',evidence_sha256='b'*64)).status_code==200


def test_governance_approval_is_not_invented_and_expires(tmp_path):
    path=tmp_path/'review.json'
    with pytest.raises(RuntimeError):approved_record(path)
    value={name:'Responsible organization actual contact' for name in ('organization','issuing_authority','operator_hours','support_contact',
        'fallback_contact','privacy_contact','incident_owner','backup_owner','database_owner','push_owner','maps_cost_owner')}
    value.update(status='approved',policy_sha256=POLICY_HASH,review_expires_at=(utc_now()+timedelta(days=1)).isoformat(),
        rpo_seconds=900,rto_seconds=14400,evidence={name:'a'*64 for name in ('privacy_review','pia_review','restore_drill','access_review','retention_exercise')})
    path.write_text(json.dumps(value),encoding='utf-8');assert approved_record(path)['status']=='approved'
    value['privacy_contact']='Pending';path.write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(RuntimeError):approved_record(path)


def test_access_review_rejects_a_changed_inventory_and_records_only_hashes(client):
    admin=staff(client)
    report=client.get('/api/privacy/admin/access-review',headers=admin).json()
    assert 'email' not in json.dumps(report) and 'password_hash' not in json.dumps(report)
    with SessionLocal() as db:
        item=db.scalar(select(User).where(User.role=='admin'));item.version+=1;db.commit()
    body=dict(current_password=PASSWORD,snapshot_sha256=report['sha256'],evidence_sha256='a'*64)
    assert client.post('/api/privacy/admin/access-review',headers=admin,json=body).status_code==409
    report=client.get('/api/privacy/admin/access-review',headers=admin).json();body['snapshot_sha256']=report['sha256']
    assert client.post('/api/privacy/admin/access-review',headers=admin,json=body).status_code==200
    with SessionLocal() as db:
        event=db.scalar(select(PrivacyEvent).where(PrivacyEvent.action=='access_reviewed'))
        assert set(event.details)=={'evidence_sha256'}


def test_holds_do_not_starve_unheld_records_at_the_retention_batch_limit(client):
    one=owner(client);two=owner(client,'unheld@example.com')
    uid=client.get('/api/auth/me',headers=one).json()['id'];other=client.get('/api/auth/me',headers=two).json()['id']
    with SessionLocal() as db:
        blocked=closed(db,uid,days=40);eligible=closed(db,other,days=40)
        db.add(PrivacyHold(user_id=uid,expires_at=utc_now()+timedelta(days=1),actor_id=uid,reason_code='legal_review',evidence_sha256='a'*64));db.commit()
        result=privacy.retain(db,apply=True,limit=1);db.expire_all()
        assert db.get(SosRequest,blocked.id).latitude==15.97
        assert db.get(SosRequest,eligible.id).latitude is None
        assert result['counts']['sos_location']==1


def test_uncertain_mail_does_not_starve_expired_action_cleanup(client):
    from app.identity_models import IdentityAction, IdentityMail
    access=owner(client);uid=client.get('/api/auth/me',headers=access).json()['id']
    expired=utc_now()-timedelta(days=30)
    with SessionLocal() as db:
        for token, state in (('a'*64,'UNKNOWN'),('b'*64,'SENDING'),('c'*64,'SENT')):
            db.add(IdentityAction(token_hash=token,purpose='password_reset',user_id=uid,account_version=1,expires_at=expired,payload={}))
            db.flush()
            db.add(IdentityMail(action_hash=token,recipient='synthetic@example.invalid',body_ciphertext='SYNTHETIC',state=state,expires_at=expired))
        db.commit()
        result=privacy.retain(db,apply=True,limit=1);db.expire_all()
        assert db.get(IdentityAction,'a'*64) is not None
        assert db.get(IdentityAction,'b'*64) is not None
        assert db.get(IdentityAction,'c'*64) is None
        assert result['counts']['identity_actions']==1
        assert result['counts']['uncertain_mail_held']==1 # Bounded count, not a total.
