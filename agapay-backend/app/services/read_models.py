"""Database-shared bounded read models and inference single-flight leases.

Every request still authenticates. Expired/revoked/config-changed values are never
silently refreshed by extending timestamps. Busy readers retry; leases recover after
producer failure without permitting a late producer to overwrite a newer result.
"""
from datetime import timedelta
import hashlib,json,time
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import delete,func,or_,select,update
from sqlalchemy.orm import sessionmaker
from app.database import SessionLocal
from app.models import Station,StationAuditEvent,Telemetry,utc_now
from app.governance_models import GovernanceAudit
from app.identity_models import MutationAudit
from app.runtime_models import SharedReadModel
from app.services.station_security import utc
from app.services import observability as obs


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def file_version(path):
    result=[]
    for candidate in (Path(path),Path(str(path)+'-wal')):
        try:
            stat=candidate.stat();result.append((stat.st_mtime_ns,stat.st_size))
        except OSError:result.append(None)
    return result


def generation(db,settings,*,extra=None,include_data=True,station_id=None):
    # Audited writes invalidate configuration/credential/lifecycle views immediately.
    models=(StationAuditEvent,GovernanceAudit,MutationAudit)
    columns=[select(func.max(model.id)).scalar_subquery() for model in models]
    if include_data:
        telemetry=select(func.max(Telemetry.id))
        if station_id:telemetry=telemetry.where(Telemetry.station_id==station_id)
        columns.append(telemetry.scalar_subquery())
    heads=db.execute(select(*columns,select(func.count()).select_from(Station).scalar_subquery())).one()
    return digest([list(heads),file_version(settings.rain_gauge_store_path) if include_data else None,settings.telemetry_stale_after_seconds,
                   settings.mqtt_enabled,settings.mqtt_external_subscriber,extra])


def cached(key,generation,build,*,ttl,settings,session_factory=SessionLocal,now=None,kind='readmodel',wait_seconds=0,stale_seconds=0,refresh_before_seconds=0):
    if not settings.read_model_cache_enabled:return build()
    now=utc(now or utc_now());token=str(uuid4());started=time.perf_counter()
    refresh_at=now+timedelta(seconds=min(ttl/2,max(0,refresh_before_seconds)))
    with session_factory() as db:
        row=db.get(SharedReadModel,key)
        if row and row.generation==generation and row.payload is not None and row.expires_at and utc(row.expires_at)>refresh_at:
            obs.observe(kind+'.hit');return row.payload
        if row is None:
            if db.bind.dialect.name=='postgresql':db.execute(__import__('sqlalchemy').text('SELECT pg_advisory_xact_lock(7310043131)'))
            # Enforce a hard cardinality cap; old arbitrary parameter sets expire.
            db.execute(delete(SharedReadModel).execution_options(synchronize_session=False).where(SharedReadModel.expires_at<=now,
                or_(SharedReadModel.lease_until.is_(None),SharedReadModel.lease_until<now)))
            if db.scalar(select(func.count()).select_from(SharedReadModel).where(SharedReadModel.key.not_like('forecast-gate:%')))>=settings.read_model_max_entries:
                default_monitor='monitor:'+digest([120,None])[:48]
                victim=db.scalar(select(SharedReadModel.key).where(SharedReadModel.key!=default_monitor,SharedReadModel.key.not_like('forecast-gate:%'),
                    or_(SharedReadModel.lease_until.is_(None),SharedReadModel.lease_until<now)).order_by(SharedReadModel.checked_at).limit(1))
                if victim:db.execute(delete(SharedReadModel).where(SharedReadModel.key==victim))
                else:
                    db.rollback();raise HTTPException(503,'Read-model capacity reached; retry later',headers={'Retry-After':'5'})
            from sqlalchemy.dialects.sqlite import insert as si
            from sqlalchemy.dialects.postgresql import insert as pi
            insert=si if db.bind.dialect.name=='sqlite' else pi
            db.execute(insert(SharedReadModel).values(key=key,generation='').on_conflict_do_nothing())
        claimed=db.execute(update(SharedReadModel).execution_options(synchronize_session=False).where(SharedReadModel.key==key,
            or_(SharedReadModel.generation!=generation,SharedReadModel.payload.is_(None),SharedReadModel.expires_at.is_(None),SharedReadModel.expires_at<=refresh_at),
            or_(SharedReadModel.lease_until.is_(None),SharedReadModel.lease_until<=now))
            .values(lease_token=token,lease_until=now+timedelta(seconds=30)))
        db.commit()
        if claimed.rowcount!=1:
            db.expire_all()
            latest=db.get(SharedReadModel,key)
            if latest and latest.generation==generation and latest.payload is not None and latest.expires_at and utc(latest.expires_at)>now:
                obs.observe(kind+'.hit');return latest.payload
            # Monitoring alone may show a bounded last-known view while another
            # producer refreshes. Never extend timestamps or inference validity,
            # and never reuse a payload after configuration generation changes.
            current=now+timedelta(seconds=time.perf_counter()-started)
            if stale_seconds and latest and latest.generation==generation and latest.payload is not None and latest.expires_at and utc(latest.expires_at)+timedelta(seconds=stale_seconds)>current:
                value=dict(latest.payload)
                health=dict(value.get('service_health') or {})
                health.update(status='degraded',codes=list(dict.fromkeys([*health.get('codes',[]),'READ_MODEL_REBUILDING'])),
                    message='Monitoring refresh is in progress. Showing last-known observations with original timestamps.')
                value['service_health']=health;obs.observe(kind+'.hit');return value
            # Release the request's extra connection before bounded coalescing.
            # Only reads are retried; no failed mutation is replayed.
            db.close()
            deadline=time.monotonic()+min(5,max(0,wait_seconds))
            while time.monotonic()<deadline:
                time.sleep(.05)
                with session_factory() as reader:
                    latest=reader.get(SharedReadModel,key)
                    if latest and latest.generation==generation and latest.payload is not None and latest.expires_at and utc(latest.expires_at)>now+timedelta(seconds=time.perf_counter()-started):
                        obs.observe(kind+'.hit');return latest.payload
            raise HTTPException(503,'Read model is rebuilding; retain original timestamps and retry',headers={'Retry-After':'1'})
    try:
        result=build()
        # Queue/connection wait before the producer starts is not observation age.
        # Base TTL on the producer's original checked_at, never on a cache hit.
        built_at=utc(__import__('datetime').datetime.fromisoformat(result['checked_at'].replace('Z','+00:00'))) if result.get('checked_at') else now
        expires=built_at+timedelta(seconds=ttl)
        if result.get('valid_until'):expires=min(expires,utc(__import__('datetime').datetime.fromisoformat(result['valid_until'].replace('Z','+00:00'))))
        with session_factory() as db:
            saved=db.execute(update(SharedReadModel).where(SharedReadModel.key==key,SharedReadModel.lease_token==token)
                .values(generation=generation,payload=result,checked_at=built_at,expires_at=expires,lease_token=None,lease_until=None))
            db.commit()
            if saved.rowcount!=1:raise HTTPException(503,'Read-model build superseded; refresh required',headers={'Retry-After':'1'})
        obs.observe(kind+'.build',time.perf_counter()-started)
        return result
    except Exception:
        with session_factory() as db:
            db.execute(delete(SharedReadModel).where(SharedReadModel.key==key,SharedReadModel.lease_token==token,SharedReadModel.payload.is_(None)))
            db.execute(update(SharedReadModel).where(SharedReadModel.key==key,SharedReadModel.lease_token==token).values(lease_token=None,lease_until=None));db.commit()
        obs.observe(kind+'.build',time.perf_counter()-started,failed=True)
        raise


def snapshot(db,settings,*,history_limit=60,station_ids=None,refresh_before_seconds=0):
    from app.services.monitoring_service import monitoring_snapshot
    from app.monitoring_schemas import MonitoringSnapshot
    canonical=max(120,history_limit)
    if station_ids:station_ids=sorted(set(station_ids))
    key='monitor:'+digest([canonical,station_ids])[:48]
    fingerprint=generation(db,settings,extra=station_ids,include_data=False)
    factory=sessionmaker(bind=db.get_bind(),expire_on_commit=False)
    # Auth/config reads are complete. Do not retain their pooled connection while
    # waiting for a separate producer; enough viewers would starve that producer.
    if db.new or db.dirty or db.deleted:raise RuntimeError('Read-model production requires a clean read transaction')
    db.rollback()
    def produce():
        with factory() as reader:
            result=monitoring_snapshot(reader,stale_after_seconds=settings.telemetry_stale_after_seconds,
                history_limit=canonical,station_ids=station_ids,settings=settings)
            from app.services.operations_health import diagnostics,public_summary
            result.service_health=public_summary(diagnostics(reader,settings))
            return result.model_dump(mode='json')
    if settings.read_model_refresh_ahead:refresh_before_seconds=max(refresh_before_seconds,settings.read_model_seconds/2)
    value=cached(key,fingerprint,produce,ttl=settings.read_model_seconds,settings=settings,session_factory=factory,
        wait_seconds=settings.read_model_wait_seconds,stale_seconds=settings.read_model_stale_seconds,refresh_before_seconds=refresh_before_seconds)
    result=MonitoringSnapshot.model_validate(value)
    for station in result.stations:station.history=station.history[-history_limit:]
    return result
