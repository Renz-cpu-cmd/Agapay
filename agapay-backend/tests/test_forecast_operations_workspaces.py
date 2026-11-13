"""Synthetic evidence only; no provider send, field approval or live restore."""
from datetime import timedelta
from uuid import uuid4
import json
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import NotificationDelivery, utc_now
from app.forecast_models import PublishedForecast
from app.identity_models import MutationAudit
from app.runtime_models import OperatorAlert, WorkerHeartbeat
from app.config import Settings
from app.services.forecast_registry import publish_station
from app.services.operations_health import diagnostics
from test_accounts import account, headers, reset_accounts, staff
from test_alerts import station
from test_notifications import prepare
from test_forecast_registry import setup, STATION, approve, deploy, observations


def test_forecast_workspace_is_staff_only_and_empty_is_not_a_forecast(client):
    path='/api/forecast-workspaces/STATION_001'
    assert client.get(path).status_code==401
    resident=headers(client.post('/api/auth/register',json=account()))
    assert client.get(path,headers=resident).status_code==403
    value=client.get(path,headers=staff(client,'officer')).json()
    assert value['model'] is None and value['products']==[] and value['total']==0
    assert value['publication_status']=='not_trained' and value['current_forecast_id'] is None


def test_workspace_retains_exact_publication_and_deployed_evaluation_after_revocation(client,setup):
    _,reviewer,identity,config_hash=setup
    assert approve(client,reviewer,identity).status_code==200
    assert deploy(client,reviewer,identity,config_hash).status_code==200
    observations(config_hash)
    with SessionLocal() as db:product_id=publish_station(db,STATION)
    path=f'/api/forecast-workspaces/{STATION}'
    response=client.get(path,headers=reviewer);assert response.status_code==200,response.text
    value=response.json();original=value['products'][0]['product']
    assert value['current_forecast_id']==product_id and value['products'][0]['current']
    assert value['deployment']['model_id']==identity and value['model']['state']=='approved'
    assert value['model']['version']==value['deployment']['model_review_version']==1
    evidence=client.get(f'/api/forecast-registry/{identity}/evidence',headers=reviewer)
    assert evidence.status_code==200,evidence.text
    assert evidence.json()['id']==identity and evidence.json()['card']['configuration_hash']==config_hash
    assert evidence.json()['decision_evaluation']['status']=='evaluated'
    assert approve(client,reviewer,identity,1,'revoked').status_code==200
    revoked=client.get(path,headers=reviewer).json()
    assert revoked['model']['state']=='revoked' and revoked['current_forecast_id'] is None
    assert not revoked['products'][0]['current'] and revoked['products'][0]['product']==original


def test_publication_history_is_bounded_and_stably_paged(client,setup):
    _,reviewer,identity,config_hash=setup
    approve(client,reviewer,identity);deploy(client,reviewer,identity,config_hash);observations(config_hash)
    with SessionLocal() as db:
        product_id=publish_station(db,STATION);original=db.get(PublishedForecast,product_id)
        for _ in range(2):
            pid=str(uuid4());payload={**original.payload,'forecast_id':pid}
            db.add(PublishedForecast(id=pid,station_id=STATION,input_fingerprint=uuid4().hex,
                generated_at=original.generated_at,valid_until=original.valid_until,payload=payload))
        db.commit()
    pages=[client.get(f'/api/forecast-workspaces/{STATION}?limit=1&offset={i}',headers=reviewer).json() for i in range(3)]
    assert all(row['total']==3 and len(row['products'])==1 for row in pages)
    ids=[row['products'][0]['product']['forecast_id'] for row in pages]
    assert ids==sorted(ids,reverse=True) and len(set(ids))==3
    assert [row['has_more'] for row in pages]==[True,True,False]
    assert client.get(f'/api/forecast-workspaces/{STATION}?limit=21',headers=reviewer).status_code==422


def test_deployed_evidence_fails_closed_on_database_bundle_corruption(client,setup):
    from sqlalchemy import update
    from app.forecast_models import ForecastModel
    _,reviewer,identity,_=setup
    with SessionLocal() as db:
        bundle=json.loads(json.dumps(db.get(ForecastModel,identity).bundle))
        bundle['card']['limitations']='Corrupted database fixture; identity no longer matches the registered evidence'
        db.execute(update(ForecastModel.__table__).where(ForecastModel.id==identity).values(bundle=bundle))
        db.commit()
    assert client.get(f'/api/forecast-registry/{identity}/evidence',headers=reviewer).status_code==503


def test_missing_processing_timestamp_stays_unknown_instead_of_zero_age(client,station):
    prepare(client,station);now=utc_now()
    with SessionLocal() as db:
        row=db.scalar(select(NotificationDelivery));row.state='PROCESSING';row.attempted_at=None
        row.created_at=now-timedelta(minutes=5);db.commit()
        report=diagnostics(db,Settings(_env_file=None,notification_provider='test',hybrid_projection_enabled=False,mqtt_enabled=False),now=now)
    component=next(row for row in report['components'] if row['name']=='notifications')
    assert component['oldest_processing_seconds'] is None and component['stalled']==1


@pytest.mark.parametrize('state,code',[('PENDING','NOTIFICATION_QUEUE_OLD'),('PROCESSING','NOTIFICATION_DELIVERY_STALLED'),
    ('UNKNOWN','NOTIFICATION_DELIVERY_UNCERTAIN'),('FAILED','NOTIFICATION_DELIVERY_FAILED')])
def test_queue_faults_and_fractional_worker_heartbeat_are_independent(client,station,state,code):
    prepare(client,station);now=utc_now()
    with SessionLocal() as db:
        delivery=db.scalar(select(NotificationDelivery));delivery.state=state
        delivery.created_at=now-timedelta(minutes=5);delivery.attempted_at=now-timedelta(minutes=4)
        db.add(WorkerHeartbeat(role='notifications',state='healthy',observed_at=now-timedelta(seconds=.5),
            last_success_at=now-timedelta(seconds=.5),detail='SENSITIVE_INTERNAL_DETAIL'))
        db.commit()
        report=diagnostics(db,Settings(_env_file=None,notification_provider='test',hybrid_projection_enabled=False,mqtt_enabled=False),now=now)
    component=next(row for row in report['components'] if row['name']=='notifications')
    assert component['code']==code
    assert next(row for row in report['workers'] if row['role']=='notifications')['fresh'] is True
    assert component['stalled']==(1 if state=='PROCESSING' else 0)
    assert 'SENSITIVE_INTERNAL_DETAIL' not in json.dumps(report)
    assert all(row['state']=='unknown' for row in report['external_quotas'])


def test_recovery_review_is_an_audited_attestation_and_never_resets_delivery_or_fault(client,station):
    prepare(client,station);access=staff(client);now=utc_now()
    with SessionLocal() as db:
        row=db.scalar(select(NotificationDelivery));row.state='UNKNOWN';db.commit();delivery_id=row.id
        db.add(OperatorAlert(code='NOTIFICATION_DELIVERY_UNCERTAIN',severity='warning',message='Synthetic uncertainty',first_seen_at=now,last_seen_at=now))
        db.commit()
    payload=dict(checked_at=now.isoformat(),code='NOTIFICATION_DELIVERY_UNCERTAIN',activity='investigated',
        reason='Synthetic provider investigation; outcome remains uncertain',evidence_sha256='a'*64)
    result=client.post('/api/operations/recovery-reviews',headers=access,json=payload)
    assert result.status_code==201,result.text
    assert result.json()['recorded'] and 'nothing was resent' in result.json()['notice']
    with SessionLocal() as db:
        assert db.get(NotificationDelivery,delivery_id).state=='UNKNOWN'
        assert db.get(OperatorAlert,payload['code']).resolved_at is None
        audit=db.get(MutationAudit,result.json()['id'])
        assert audit.after['evidence_sha256']=='a'*64 and audit.after['attestation_kind']=='operator_attestation'
        assert audit.after['diagnostic_checked_at'] and audit.actor_id
        from app.services.mutation_audit import redact
        assert redact({'code':'SENSITIVE_VERIFICATION_CODE','source':'SENSITIVE_OPAQUE_TOKEN'})=={}
    assert client.post('/api/operations/recovery-reviews',headers=access,json={**payload,'reset_to_pending':True}).status_code==422
    assert client.post('/api/operations/recovery-reviews',headers=access,json={**payload,'checked_at':(now+timedelta(hours=1)).isoformat()}).status_code==409
    assert client.post('/api/operations/recovery-reviews',headers=staff(client,'officer'),json=payload).status_code==403
    assert client.post('/api/operations/recovery-reviews',json=payload).status_code==401


def test_resident_stage_latency_uses_unique_durable_server_receipts_without_inferred_stages(client,station,monkeypatch):
    from app.services import observability as obs
    from app.services.notification_service import process_pending
    from test_delivery_evidence import ControlledProvider, SendOutcome, consent, own, receipt
    access,_=prepare(client,station);consent(client,access)
    provider=ControlledProvider(SendOutcome.UNKNOWN);process_pending(provider)
    measured=[];monkeypatch.setattr(obs,'observe',lambda metric,seconds,**kwargs:measured.append((metric,seconds)))
    value=receipt(provider,'OPENED')
    assert client.post('/api/notification-receipts',json=value).status_code==200
    assert client.post('/api/notification-receipts',json=value).status_code==200
    row=own(client,access)
    acknowledged=client.post(f"/api/notification-deliveries/{row['id']}/acknowledge",headers=access,
        json={'expected_version':row['version'],'confirmed':True})
    assert acknowledged.status_code==200,acknowledged.text
    seen=[(name,seconds) for name,seconds in measured if name.startswith('notification.')]
    assert [name for name,_ in seen]==['notification.app_opened','notification.user_acknowledged']
    assert all(seconds>=0 for _,seconds in seen)
    assert acknowledged.json()['state']=='UNKNOWN'
    assert not any(stage['stage']=='RECEIVED' for stage in acknowledged.json()['receipt_stages'])
