from datetime import timedelta
import json
import pytest
from sqlalchemy import select
from app.database import SessionLocal
from app.models import NotificationDelivery,utc_now
from app.delivery_models import DeliveryAttempt,DeliveryControl,DeliveryReceipt,DeliveryReview
from app.services.notification_provider import SendOutcome,ProviderResult
from app.services.notification_service import process_pending
from test_accounts import reset_accounts,staff
from test_alerts import station
from test_notifications import prepare,register,resident,TOKEN


class ControlledProvider:
    mode='fcm'
    def __init__(self,outcome=SendOutcome.ACCEPTED):self.messages=[];self.outcome=outcome
    def send(self,*args,**kwargs):return self.send_with_evidence(*args,**kwargs).outcome
    def send_with_evidence(self,target,message,**kwargs):
        self.messages.append(message);return ProviderResult(self.outcome,'projects/synthetic-test/messages/123' if self.outcome==SendOutcome.ACCEPTED else None)


def own(client,access):return client.get('/api/notification-deliveries',headers=access).json()['items'][0]
def consent(client,access,enabled=True):
    current=client.get('/api/notification-deliveries/consent',headers=access).json()
    result=client.post('/api/notification-deliveries/consent',headers=access,json={'enabled':enabled,'expected_version':current['version']})
    assert result.status_code==200,result.text
    return result.json()
def receipt(provider,stage='RECEIVED'):
    data=provider.messages[0].data
    return dict(delivery_id=int(data['delivery_id']),attempt_no=int(data['attempt_no']),receipt_token=data['receipt_token'],stage=stage,reported_at=utc_now().isoformat())


def test_queued_provider_acceptance_and_user_acknowledgement_never_infer_phone_receipt(client,station):
    access,_=prepare(client,station);queued=own(client,access)
    assert queued['state']=='PENDING' and not queued['provider_accepted'] and queued['receipt_stages']==[]
    provider=ControlledProvider();assert process_pending(provider)==1
    assert 'receipt_token' not in provider.messages[0].data # Collection defaults off.
    sent=own(client,access)
    assert sent['provider_accepted'] and sent['state']=='SENT' and sent['receipt_stages']==[]
    assert 'provider_reference' not in sent['attempts'][0]
    result=client.post(f"/api/notification-deliveries/{sent['id']}/acknowledge",headers=access,json={'expected_version':sent['version'],'confirmed':True})
    assert result.status_code==200,result.text
    assert [r['stage'] for r in result.json()['receipt_stages']]==['ACKNOWLEDGED']
    assert not result.json()['can_acknowledge']
    assert process_pending(provider)==0


def test_consented_callbacks_are_scoped_idempotent_private_and_independent(client,station):
    access,_=prepare(client,station);consent(client,access)
    provider=ControlledProvider(SendOutcome.UNKNOWN);process_pending(provider)
    payload=receipt(provider,'OPENED')
    result=client.post('/api/notification-receipts',json=payload);assert result.status_code==200,result.text
    current=own(client,access)
    assert current['state']=='UNKNOWN' and not current['provider_accepted']
    assert [r['stage'] for r in current['receipt_stages']]==['OPENED']
    assert client.post('/api/notification-receipts',json={**payload,'reported_at':'2000-01-01T00:00:00Z'}).status_code==200
    assert own(client,access)['version']==current['version']
    assert client.post('/api/notification-receipts',json={**payload,'receipt_token':'x'*43}).status_code==404
    assert client.post('/api/notification-receipts',json={**payload,'attempt_no':99}).status_code==404
    assert client.post('/api/notification-receipts',json={**payload,'stage':'ACKNOWLEDGED'}).status_code==422
    assert client.post('/api/notification-receipts',json={**payload,'latitude':1}).status_code==422
    other=resident(client,'other@example.com')
    assert client.get(f"/api/notification-deliveries/{current['id']}",headers=other).status_code==404
    console=client.get('/api/notification-deliveries',headers=staff(client)).text
    assert payload['receipt_token'] not in console and TOKEN not in console
    with SessionLocal() as db:
        attempt=db.get(DeliveryAttempt,(payload['delivery_id'],1));assert attempt.receipt_hash!=payload['receipt_token']
    assert process_pending(provider)==0


def test_token_rotation_preserves_installation_receipt_but_consent_withdrawal_and_logout_revoke(client,station):
    access,_=prepare(client,station);consent(client,access);provider=ControlledProvider();process_pending(provider);payload=receipt(provider)
    register(client,access,token=TOKEN+'-rotated')
    assert client.post('/api/notification-receipts',json=payload).status_code==200
    consent(client,access,False);assert client.post('/api/notification-receipts',json={**payload,'stage':'OPENED'}).status_code==403
    consent(client,access,True);assert client.post('/api/notification-receipts',json={**payload,'stage':'OPENED'}).status_code==404
    assert client.post('/api/auth/logout',headers=access).status_code==204
    assert client.post('/api/notification-receipts',json=payload).status_code==403


def test_expired_delivery_is_suppressed_before_any_provider_call(client,station):
    access,_=prepare(client,station)
    with SessionLocal() as db:
        row=db.scalar(select(DeliveryControl));row.expires_at=utc_now()-timedelta(seconds=1);db.commit()
    provider=ControlledProvider();assert process_pending(provider)==1 and not provider.messages
    assert own(client,access)['state']=='SUPPRESSED'


@pytest.mark.parametrize('stage,calls',[('claimed',0),('prepared',0),('provider_returned',1),('before_result_commit',1)])
def test_process_kill_at_every_send_boundary_never_reclaims_or_replays(client,station,stage,calls):
    access,_=prepare(client,station);consent(client,access);provider=ControlledProvider()
    class Crash(BaseException):pass
    def fail(at):
        if at==stage:raise Crash()
    with pytest.raises(Crash):process_pending(provider,boundary=fail)
    assert len(provider.messages)==calls
    assert own(client,access)['state']=='PROCESSING' and own(client,access)['review_required']
    assert process_pending(provider)==0 and len(provider.messages)==calls
    if calls:
        assert client.post('/api/notification-receipts',json=receipt(provider)).status_code==200
        assert own(client,access)['state']=='PROCESSING' # Callback is evidence, not a send-state rewrite.


def test_reconciliation_is_versioned_audited_and_never_resends_unknown(client,station):
    access,_=prepare(client,station);consent(client,access);provider=ControlledProvider(SendOutcome.UNKNOWN);process_pending(provider)
    admin=staff(client);item=own(client,access);decision=dict(expected_version=item['version'],decision='provider_accepted',evidence_kind='provider_record',evidence_sha256='a'*64,reason='Reviewed synthetic provider record')
    assert client.post('/api/notification-receipts',json=receipt(provider)).status_code==200
    path=f"/api/notification-deliveries/{item['id']}/reconcile"
    assert client.post(path,headers=admin,json=decision).status_code==409
    current=own(client,access);decision['expected_version']=current['version']
    assert client.post(path,headers=access,json=decision).status_code==403
    assert client.post(path,headers=admin,json={**decision,'evidence_kind':'recipient_contact'}).status_code==422
    result=client.post(path,headers=admin,json=decision);assert result.status_code==200,result.text
    assert result.json()['state']=='UNKNOWN' and result.json()['operator_attested_acceptance'] and not result.json()['provider_accepted']
    assert not result.json()['review_required']
    assert process_pending(provider)==0 and len(provider.messages)==1
    with SessionLocal() as db:
        assert db.scalar(select(DeliveryReview)).evidence_sha256=='a'*64
        assert db.scalar(select(NotificationDelivery)).state=='UNKNOWN'


def test_staff_scope_and_fresh_inflight_reconciliation_are_explicit(client,station):
    access,_=prepare(client,station);provider=ControlledProvider()
    def fail(at):
        if at=='prepared':raise SystemExit()
    with pytest.raises(SystemExit):process_pending(provider,boundary=fail)
    item=own(client,access);officer=staff(client,'officer')
    assert client.get('/api/notification-deliveries',headers=officer).json()['items']==[]
    admin=staff(client);assert client.get('/api/notification-deliveries',headers=admin).json()['items']
    body=dict(expected_version=item['version'],decision='closed_no_resend',evidence_kind='manual_review',evidence_sha256='b'*64,reason='Synthetic pending-send boundary review')
    assert client.post(f"/api/notification-deliveries/{item['id']}/reconcile",headers=admin,json=body).status_code==409
