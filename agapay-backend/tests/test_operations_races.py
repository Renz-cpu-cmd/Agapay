"""Concurrent writers and explicit citywide delivery gates; no external provider."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
import pytest
from app.models import AlertTransition, NotificationDelivery, Station, utc_now
from app.database import SessionLocal
from sqlalchemy import select
from test_alerts import transitions
from app.services.notification_provider import FakeNotificationProvider
from app.services.notification_service import process_pending
from test_accounts import reset_accounts
from test_alert_governance import governed, issuer, resident_device
from test_notifications import resident, rows
from test_station_security import device
from test_operations_preferences import operations, transition, water


def race(*jobs):
    barrier=Barrier(len(jobs))
    def run(job):barrier.wait();return job()
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:return list(pool.map(run,jobs))


def test_concurrent_metadata_and_lifecycle_have_one_revision_winner(client,device):
    current=operations(client,device)
    base=f'/api/stations/{device[0]}'
    metadata=dict(expected_revision=current['revision'],station_name='Concurrent descriptive update',reason='Synthetic concurrent metadata review')
    lifecycle=dict(expected_revision=current['revision'],expected_identity_version=current['identity_version'],state='maintenance',reason='Synthetic concurrent lifecycle review')
    results=race(lambda:client.patch(base+'/metadata',headers=device[1],json=metadata),lambda:client.post(base+'/lifecycle',headers=device[1],json=lifecycle))
    assert sorted(r.status_code for r in results)==[200,409]
    assert operations(client,device)['revision']==current['revision']+1


def test_concurrent_account_preference_writes_cannot_overwrite_newer_values(client):
    access=resident(client)
    results=race(*(lambda value=value:client.patch('/api/auth/preferences',headers=access,json=dict(expected_revision=0,requested_language=value)) for value in ['Community language A','Community language B']))
    assert sorted(r.status_code for r in results)==[200,409]
    winner=next(r.json() for r in results if r.status_code==200)
    assert client.get('/api/auth/preferences',headers=access).json()['requested_language']==winner['requested_language']


@pytest.mark.parametrize('state',['maintenance','inactive'])
def test_citywide_cannot_override_lifecycle_or_replay_after_reactivation(client,governed,issuer,state):
    station,send=governed
    with SessionLocal() as db:
        source=db.scalar(select(Station).where(Station.station_id==station))
        source.latitude,source.longitude=15.98,120.56  # Synthetic fixture coordinates only.
        db.commit()
    send(1,105)
    identity=(station,issuer,None)
    assert transition(client,identity,state).status_code==200
    body=dict(authority_id='APP',reason='Synthetic explicit citywide dispatch acceptance',expires_at=(utc_now()+timedelta(minutes=10)).isoformat())
    path=f'/api/alert-governance/transitions/{transitions(governed[0])[0].id}/citywide'
    assert client.post(path,headers=issuer,json=body).status_code==409
    assert transition(client,identity,'active').status_code==200
    assert client.post(path,headers=issuer,json=body).status_code==409


def test_delivery_off_is_respected_by_explicit_citywide_recipient_capture(client,governed,issuer):
    access,_=resident_device(client,'citywide-off@example.com')
    assert client.patch('/api/auth/preferences',headers=access,json=dict(expected_revision=0,notifications_enabled=False)).status_code==200
    governed[1](1,105)
    path=f'/api/alert-governance/transitions/{transitions(governed[0])[0].id}/citywide'
    body=dict(authority_id='APP',reason='Synthetic explicit citywide dispatch acceptance',expires_at=(utc_now()+timedelta(minutes=10)).isoformat())
    assert client.post(path,headers=issuer,json=body).status_code==200
    provider=FakeNotificationProvider();process_pending(provider)
    assert rows(NotificationDelivery)==[] and provider.messages=={}
