"""Cross-session coalescing, lease recovery, freshness and immediate audit invalidation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,select,text,update
from app.config import Settings,get_settings
from app.database import SessionLocal
from app.migrations import LEDGER,REVISIONS,checksum,require_current,upgrade
from app.models import StationAuditEvent,utc_now
from app.runtime_models import SharedReadModel
from app.services.read_models import cached,generation
from test_accounts import reset_accounts,staff


def config(**kw):return Settings(_env_file=None,read_model_cache_enabled=True,hybrid_projection_enabled=False,**kw)


def test_new_revision_upgrades_a_versioned_baseline_without_restamping_it(tmp_path):
    from app.runtime_models import TABLES
    from app.delivery_models import TABLES as DELIVERY_TABLES
    from app.forecast_models import TABLES as FORECAST_TABLES
    bind=create_engine('sqlite:///'+str(tmp_path/'baseline.db'));upgrade(bind)
    with bind.begin() as connection:
        original=connection.execute(select(LEDGER).where(LEDGER.c.revision==REVISIONS[0])).one()
        connection.execute(LEDGER.delete().where(LEDGER.c.revision.in_(REVISIONS[1:])))
        for table in reversed(FORECAST_TABLES):table.drop(connection)
        for table in reversed(DELIVERY_TABLES):table.drop(connection)
        for table in reversed(TABLES):table.drop(connection)
    with pytest.raises(RuntimeError,match='migration required'):require_current(bind)
    assert upgrade(bind)==list(REVISIONS[1:])
    with bind.connect() as connection:
        assert connection.execute(select(LEDGER).where(LEDGER.c.revision==REVISIONS[0])).one()==original
    bind.dispose()


def test_read_model_keeps_original_timestamp_and_stops_serving_at_expiry():
    settings=config();at=utc_now();builds=[]
    def build():builds.append(1);return {'checked_at':at.isoformat(),'value':len(builds)}
    first=cached('monitor:test','same',build,ttl=2,settings=settings,now=at)
    second=cached('monitor:test','same',build,ttl=2,settings=settings,now=at+timedelta(seconds=1))
    assert first==second and len(builds)==1
    third=cached('monitor:test','same',build,ttl=2,settings=settings,now=at+timedelta(seconds=3))
    assert third['value']==2 and third['checked_at']==at.isoformat()


def test_concurrent_sessions_share_one_producer_and_return_explicit_busy():
    entered=Event();release=Event();builds=[];settings=config()
    def build():builds.append(1);entered.set();assert release.wait(5);return {'value':'committed'}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first=executor.submit(cached,'monitor:race','g',build,ttl=2,settings=settings)
        assert entered.wait(5)
        with pytest.raises(HTTPException) as error:cached('monitor:race','g',build,ttl=2,settings=settings)
        assert error.value.status_code==503 and error.value.headers['Retry-After']=='1'
        release.set();assert first.result(timeout=5)=={'value':'committed'}
    assert len(builds)==1


def test_expired_lease_takeover_rejects_late_producer_result():
    entered=Event();release=Event();at=utc_now();settings=config()
    def stale():entered.set();assert release.wait(5);return {'value':'obsolete'}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first=executor.submit(cached,'monitor:takeover','old',stale,ttl=2,settings=settings,now=at)
        assert entered.wait(5)
        assert cached('monitor:takeover','new',lambda:{'value':'new'},ttl=2,settings=settings,now=at+timedelta(seconds=31))=={'value':'new'}
        release.set()
        with pytest.raises(HTTPException):first.result(timeout=5)
    with SessionLocal() as db:assert db.get(SharedReadModel,'monitor:takeover').payload=={'value':'new'}


def test_bounded_wait_coalesces_reader_without_duplicate_build():
    import time
    entered=Event();settings=config();builds=[]
    def produce():builds.append(1);entered.set();time.sleep(.2);return {'value':'shared'}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first=executor.submit(cached,'monitor:wait','g',produce,ttl=2,settings=settings)
        assert entered.wait(5)
        second=cached('monitor:wait','g',produce,ttl=2,settings=settings,wait_seconds=1)
        assert first.result(timeout=5)==second=={'value':'shared'}
    assert len(builds)==1


def test_last_known_grace_is_explicit_bounded_and_keeps_original_timestamps():
    settings=config();at=utc_now();entered=Event();release=Event()
    original={'checked_at':at.isoformat(),'value':1,'service_health':{'status':'healthy','codes':[]}}
    cached('monitor:grace','g',lambda:original,ttl=2,settings=settings,now=at)
    def produce():entered.set();assert release.wait(5);return {'value':2}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first=executor.submit(cached,'monitor:grace','g',produce,ttl=2,settings=settings,now=at+timedelta(seconds=3))
        assert entered.wait(5)
        retained=cached('monitor:grace','g',produce,ttl=2,settings=settings,now=at+timedelta(seconds=3),stale_seconds=2)
        assert retained['checked_at']==original['checked_at'] and retained['value']==1
        assert retained['service_health']['status']=='degraded' and 'READ_MODEL_REBUILDING' in retained['service_health']['codes']
        assert original['service_health']['status']=='healthy'
        with pytest.raises(HTTPException):cached('monitor:grace','g',produce,ttl=2,settings=settings,now=at+timedelta(seconds=5),stale_seconds=2)
        with pytest.raises(HTTPException):cached('monitor:grace','new-config',produce,ttl=2,settings=settings,now=at+timedelta(seconds=3),stale_seconds=2)
        release.set();assert first.result(timeout=5)=={'value':2}


def test_failed_producer_does_not_exhaust_cache_capacity():
    settings=config(read_model_max_entries=8)
    def fail():raise OSError('Synthetic dependency failure')
    for i in range(12):
        with pytest.raises(OSError):cached(f'failed:{i}','g',fail,ttl=2,settings=settings)
    assert cached('monitor:healthy','g',lambda:{'value':1},ttl=2,settings=settings)=={'value':1}
    with SessionLocal() as db:assert len(list(db.scalars(select(SharedReadModel))))==1


def test_proactive_producer_refreshes_before_expiry_and_uses_actual_check_time():
    settings=config();at=utc_now();builds=[]
    def produce():
        checked=at+timedelta(seconds=len(builds));builds.append(checked)
        return {'checked_at':checked.isoformat(),'value':len(builds)}
    cached('monitor:proactive','g',produce,ttl=2,settings=settings,now=at)
    assert cached('monitor:proactive','g',produce,ttl=2,settings=settings,now=at+timedelta(seconds=1))['value']==1
    assert cached('monitor:proactive','g',produce,ttl=2,settings=settings,now=at+timedelta(seconds=1),refresh_before_seconds=1)['value']==2
    with SessionLocal() as db:
        from app.services.station_security import utc
        row=db.get(SharedReadModel,'monitor:proactive')
        assert utc(row.checked_at)==at+timedelta(seconds=1) and utc(row.expires_at)==at+timedelta(seconds=3)


def test_audited_changes_invalidate_cache_and_authentication_is_always_fresh(client):
    access=staff(client);settings=config()
    with SessionLocal() as db:
        before=generation(db,settings,include_data=False)
    # An ordinary account edit writes a monotonic general audit record.
    me=client.get('/api/auth/me',headers=access).json()
    response=client.patch('/api/auth/me',headers=access,json={'expected_version':me['version'],'name':'Reviewed change'})
    assert response.status_code==200
    with SessionLocal() as db:assert generation(db,settings,include_data=False)!=before
    from app.main import app
    app.dependency_overrides[get_settings]=lambda:settings
    try:
        # R5: seeded station filter keeps this session check independent of the station budget.
        assert client.get('/api/monitoring/stations?station_id=STATION_001',headers=access).status_code==200
        assert client.post('/api/auth/logout',headers=access).status_code==204
        assert client.get('/api/monitoring/stations?station_id=STATION_001',headers=access).status_code==401
    finally:app.dependency_overrides.pop(get_settings,None)
