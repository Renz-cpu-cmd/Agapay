"""Isolated workflow faults, redacted correlation and required-capability readiness."""
from datetime import timedelta
import errno,json
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from app.config import Settings,get_settings
from app.database import SessionLocal,get_db
from app.main import app
from app.models import NotificationDelivery,utc_now
from app.runtime_models import OperatorAlert
from app.services import observability as obs
from app.services.operations_health import diagnostics,reconcile
from app.services.rain_gauge_service import RainGaugeStore
from test_accounts import reset_accounts,staff,account,headers
from test_alerts import station
from test_notifications import prepare


def configuration(**changes):
    return Settings(_env_file=None,hybrid_projection_enabled=False,mqtt_enabled=False,**changes)


def codes(report):return {alert['code'] for alert in report['alerts']}


def test_liveness_remains_available_when_database_dependency_is_unusable(client,monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    broken=create_engine('sqlite://')
    def database():
        with Session(broken) as db:yield db
    app.dependency_overrides[get_db]=database
    try:
        assert client.get('/live').json()=={'status':'alive'}
        assert client.get('/ready').status_code==503
    finally:app.dependency_overrides.pop(get_db,None);broken.dispose()


def test_stopped_worker_creates_and_resolves_specific_operator_alert_without_resending(client):
    settings=configuration(notification_provider='test',operations_required=['monitoring','notifications'])
    with SessionLocal() as db:
        report=diagnostics(db,settings)
        assert not report['ready'] and 'NOTIFICATIONS_WORKER_STALE' in codes(report)
        reconcile(db,report)
        assert db.get(OperatorAlert,'NOTIFICATIONS_WORKER_STALE').resolved_at is None
    obs.heartbeat('notifications')
    with SessionLocal() as db:
        report=diagnostics(db,settings);assert report['ready'];reconcile(db,report)
        assert db.get(OperatorAlert,'NOTIFICATIONS_WORKER_STALE').resolved_at is not None
    obs.heartbeat('notifications','stopped')
    with SessionLocal() as db:
        assert 'NOTIFICATIONS_WORKER_STOPPED' in codes(diagnostics(db,settings))
        assert 'NOTIFICATIONS_WORKER_STALE' in codes(diagnostics(db,settings,now=utc_now()+timedelta(seconds=46)))


def test_broker_auth_and_subscription_failure_are_not_http_health(client,monkeypatch):
    import paho.mqtt.client as mqtt
    from app.services.mqtt_subscriber import start_mqtt_subscriber
    settings=Settings(_env_file=None,hybrid_projection_enabled=False,mqtt_enabled=True,mqtt_username='isolated',mqtt_password='synthetic',operations_required=['mqtt'])
    monkeypatch.setattr(mqtt.Client,'connect_async',lambda *a,**k:None)
    monkeypatch.setattr(mqtt.Client,'loop_start',lambda *a,**k:None)
    mids=iter(range(1,10));monkeypatch.setattr(mqtt.Client,'subscribe',lambda *a,**k:(0,next(mids)))
    sub=start_mqtt_subscriber(settings)
    sub.on_connect(sub,None,None,5,None)
    with SessionLocal() as db:assert 'BROKER_DISCONNECTED' in codes(diagnostics(db,settings))
    sub.on_connect(sub,None,None,0,None)
    with SessionLocal() as db:assert 'BROKER_SUBSCRIPTION_UNCONFIRMED' in codes(diagnostics(db,settings))
    sub.on_subscribe(sub,None,1,[128],None)
    with SessionLocal() as db:assert 'BROKER_SUBSCRIPTION_REJECTED' in codes(diagnostics(db,settings))


def test_rain_storage_full_write_failure_and_dependency_interruption_are_specific(tmp_path,monkeypatch):
    from app.services import operations_health as health
    path=tmp_path/'rain.db';RainGaugeStore(path)
    settings=configuration(rain_gauge_enabled=True,rain_gauge_store_path=str(path),operations_required=['rain'])
    with SessionLocal() as db:assert diagnostics(db,settings,write_probe=True)['ready']
    assert not list(tmp_path.glob('.agapay-health-*'))
    original=health.shutil.disk_usage
    monkeypatch.setattr(health.shutil,'disk_usage',lambda *_:SimpleNamespace(free=0))
    with SessionLocal() as db:assert 'RAIN_STORAGE_FULL' in codes(diagnostics(db,settings))
    monkeypatch.setattr(health.shutil,'disk_usage',original)
    def full(*a,**k):raise OSError(errno.ENOSPC,'Synthetic full test filesystem')
    monkeypatch.setattr(health.tempfile,'mkstemp',full)
    with SessionLocal() as db:assert 'RAIN_STORAGE_FULL' in codes(diagnostics(db,settings,write_probe=True))
    path.unlink()
    with SessionLocal() as db:assert 'RAIN_JOURNAL_MISSING' in codes(diagnostics(db,settings))


def test_removing_a_cached_artifact_reports_unavailability(tmp_path,monkeypatch):
    from app.services import hybrid_projection as hybrid
    for name in ('metadata.json','forest.json','data.csv'):(tmp_path/name).write_text('{}')
    monkeypatch.setattr(hybrid,'_get_engine',lambda *a:object())
    settings=Settings(_env_file=None,hybrid_projection_enabled=True,hybrid_model_directory=str(tmp_path),hybrid_dataset_path=str(tmp_path/'data.csv'),operations_required=['models'])
    with SessionLocal() as db:assert diagnostics(db,settings)['ready']
    (tmp_path/'forest.json').unlink()
    with SessionLocal() as db:
        report=diagnostics(db,settings)
        assert not report['ready'] and 'MODEL_ARTIFACT_UNAVAILABLE' in codes(report)


def test_old_and_uncertain_delivery_states_require_review_without_replay(client,station):
    prepare(client,station)
    settings=configuration(notification_provider='test')
    obs.heartbeat('notifications')
    with SessionLocal() as db:
        row=db.scalar(select(NotificationDelivery));row.created_at=utc_now()-timedelta(minutes=5);db.commit()
        assert 'NOTIFICATION_QUEUE_OLD' in codes(diagnostics(db,settings))
        row.state='PROCESSING';row.attempted_at=utc_now()-timedelta(minutes=5);db.commit()
        assert 'NOTIFICATION_DELIVERY_STALLED' in codes(diagnostics(db,settings))
        row.state='UNKNOWN';db.commit()
        assert 'NOTIFICATION_DELIVERY_UNCERTAIN' in codes(diagnostics(db,settings))
        assert db.get(NotificationDelivery,row.id).attempts==0


def test_metrics_and_correlation_are_bounded_shared_and_redacted(client,monkeypatch,caplog):
    monkeypatch.setattr(get_settings(),'observability_enabled',True);obs.reset()
    try:
        for latency in (.01,.1,1):obs.observe('ingest.live',latency)
        obs.observe('unbounded-user-label',2);obs.flush(force=True)
        with SessionLocal() as db:
            value=obs.metrics(db)['ingest.live'];assert value['count']==3 and value['maximum_seconds']==1
        caplog.set_level('INFO',logger='agapay.workflow')
        obs.event('test.redaction',password='must-not-appear',provider_token='secret-push',code='TEST')
        assert 'must-not-appear' not in caplog.text and 'secret-push' not in caplog.text
        response=client.get('/live',headers={'X-Request-ID':'12345678-1234-1234-1234-123456789abc'})
        assert response.headers['X-Request-ID']=='12345678-1234-1234-1234-123456789abc'
    finally:obs.reset()


def test_single_auth_staff_header_is_stricter_and_never_grants_staff_access(client):
    access=headers(client.post('/api/auth/register',json=account()))
    assert client.get('/api/monitoring/stations',headers={**access,'X-Agapay-Require-Staff':'1'}).status_code==403
    assert client.get('/api/monitoring/stations?station_id=STATION_001',headers=access).status_code==200  # R5: seeded station, budget-independent
    admin=staff(client)
    assert client.get('/api/operations/diagnostics',headers=admin).status_code==200
    assert client.get('/api/operations/diagnostics',headers=access).status_code==403


def test_metrics_scrape_requires_a_separate_secret_and_never_returns_private_labels(client,monkeypatch):
    from pydantic import SecretStr
    settings=get_settings()
    monkeypatch.setattr(settings,'observability_scrape_token',SecretStr('synthetic-scrape-secret-of-more-than-32-characters'))
    assert client.get('/api/operations/metrics').status_code==401
    assert client.get('/api/operations/metrics',headers={'Authorization':'Bearer invalid'}).status_code==401
    result=client.get('/api/operations/metrics',headers={'Authorization':'Bearer '+settings.observability_scrape_token.get_secret_value()})
    assert result.status_code==200 and 'agapay_workflow_ready' in result.text
    assert 'user_id' not in result.text and 'station_id' not in result.text and 'synthetic-scrape' not in result.text
    assert result.headers['Cache-Control']=='no-store'


def test_overflow_latency_and_http_error_budgets_emit_specific_faults(client,monkeypatch):
    monkeypatch.setattr(get_settings(),'observability_enabled',True);obs.reset()
    try:
        for _ in range(20):obs.observe('ingest.live',200);obs.observe('http.monitoring',.1,failed=True)
        obs.flush(force=True)
        with SessionLocal() as db:
            faults=codes(diagnostics(db,configuration()))
            assert {'INGESTION_LATENCY_BUDGET_BURN','HTTP_ERROR_BUDGET_BURN'}<=faults
    finally:obs.reset()


def test_account_mail_queue_and_uncertain_acceptance_are_visible_without_replay(client):
    from app.identity_models import IdentityAction,IdentityMail
    with SessionLocal() as db:
        db.add(IdentityAction(token_hash='a'*64,purpose='recovery',created_at=utc_now()-timedelta(minutes=5),expires_at=utc_now()+timedelta(minutes=5)))
        db.flush();row=IdentityMail(action_hash='a'*64,recipient='synthetic@example.invalid',body_ciphertext='synthetic-only',expires_at=utc_now()+timedelta(minutes=5))
        db.add(row);db.commit()
        assert 'IDENTITY_MAIL_QUEUE_OLD' in codes(diagnostics(db,configuration()))
        row.state='UNKNOWN';db.commit()
        assert 'IDENTITY_MAIL_DELIVERY_UNCERTAIN' in codes(diagnostics(db,configuration()))
        assert db.get(IdentityMail,row.id).state=='UNKNOWN'


def test_stalled_monitoring_producer_prevents_readiness(client):
    from app.runtime_models import SharedReadModel
    with SessionLocal() as db:
        db.add(SharedReadModel(key='monitor:stalled',generation='g',lease_token='synthetic',lease_until=utc_now()-timedelta(seconds=1)));db.commit()
        report=diagnostics(db,configuration())
        assert not report['ready'] and 'READ_MODEL_PRODUCER_STALLED' in codes(report)
