"""Bounded, redacted workflow telemetry. Metrics are shared, auth decisions are not cached."""
from collections import defaultdict
from contextvars import ContextVar
from datetime import datetime,timezone,timedelta
import json,logging,math,re,time
from threading import Lock
from uuid import uuid4
from sqlalchemy import delete,select
from app.database import SessionLocal
from app.runtime_models import MetricBucket,WorkerHeartbeat
from app.models import utc_now

log=logging.getLogger('agapay.workflow')
request_id=ContextVar('request_id',default=None)
query_count=ContextVar('query_count',default=0)
BOUNDS=(.005,.01,.025,.05,.1,.25,.5,1,2,5,10,30,120)
METRICS={'http.monitoring','http.hybrid','http.sos','http.other','ingest.live','ingest.backfill',
         'hazard.decision','notification.delivery','notification.queue','identity.delivery',
         'readmodel.build','readmodel.hit','hybrid.build','hybrid.hit','http.queries'}
_lock=Lock();_buffer={};_last_flush=0.0
_scheduled=False


def schedule_flush():
    global _scheduled
    import asyncio
    with _lock:
        if _scheduled or not _buffer or time.monotonic()-_last_flush<5:return
        _scheduled=True
    async def background():
        global _scheduled
        context=query_count.set(None)
        try:await asyncio.to_thread(flush)
        finally:
            query_count.reset(context)
            with _lock:_scheduled=False
    asyncio.get_running_loop().create_task(background())


def correlation(value=None):
    return value if value and re.fullmatch(r'[a-fA-F0-9-]{36}',value) else str(uuid4())


def event(name,*,correlation_id=None,**fields):
    allowed={'sample_id','station_id','transition_id','event_id','delivery_id','state','duration_seconds','code','role','status','route'}
    log.info(json.dumps({'event':name,'correlation_id':correlation_id or request_id.get() or str(uuid4()),
                         **{k:v for k,v in fields.items() if k in allowed}},separators=(',',':')))


def observe(metric,seconds=0,*,failed=False):
    from app.config import get_settings
    if not get_settings().observability_enabled or metric not in METRICS:return
    if not math.isfinite(seconds) or seconds<0:return
    minute=int(time.time())//60
    bucket=next((str(bound) for bound in BOUNDS if seconds<=bound),'inf')
    with _lock:
        if len(_buffer)>=256 and (metric,minute) not in _buffer:return
        value=_buffer.setdefault((metric,minute),dict(count=0,failures=0,total_seconds=0.,maximum_seconds=0.,histogram={}))
        value['count']+=1;value['failures']+=int(failed);value['total_seconds']+=seconds
        value['maximum_seconds']=max(value['maximum_seconds'],seconds)
        value['histogram'][bucket]=value['histogram'].get(bucket,0)+1


def flush(*,force=False,session_factory=SessionLocal):
    global _last_flush
    with _lock:
        if not _buffer or not force and time.monotonic()-_last_flush<5:return
        pending=dict(_buffer);_buffer.clear();_last_flush=time.monotonic()
    try:
        with session_factory() as db:
            if db.bind.dialect.name=='sqlite':db.connection().exec_driver_sql('BEGIN IMMEDIATE')
            for (metric,minute),delta in pending.items():
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                insert=sqlite_insert if db.bind.dialect.name=='sqlite' else pg_insert
                db.execute(insert(MetricBucket).values(metric=metric,minute=minute,count=0,failures=0,total_seconds=0,maximum_seconds=0,histogram={}).on_conflict_do_nothing())
                row=db.scalar(select(MetricBucket).where(MetricBucket.metric==metric,MetricBucket.minute==minute).with_for_update())
                for field in ('count','failures','total_seconds'):setattr(row,field,getattr(row,field)+delta[field])
                row.maximum_seconds=max(row.maximum_seconds,delta['maximum_seconds'])
                histogram=dict(row.histogram)
                for key,value in delta['histogram'].items():histogram[key]=histogram.get(key,0)+value
                row.histogram=histogram
            db.execute(delete(MetricBucket).where(MetricBucket.minute<int(time.time())//60-7*1440));db.commit()
    except Exception:
        # Preserve bounded telemetry for a later flush; never block the actual job.
        with _lock:
            for key,delta in pending.items():
                if len(_buffer)>=256 and key not in _buffer:continue
                value=_buffer.setdefault(key,dict(count=0,failures=0,total_seconds=0.,maximum_seconds=0.,histogram={}))
                for field in ('count','failures','total_seconds'):value[field]+=delta[field]
                value['maximum_seconds']=max(value['maximum_seconds'],delta['maximum_seconds'])
                for bucket,count in delta['histogram'].items():value['histogram'][bucket]=value['histogram'].get(bucket,0)+count
        log.warning('Workflow metrics unavailable; bounded buffer retained; job outcome unchanged')


def heartbeat(role,state='healthy',detail='',*,session_factory=SessionLocal):
    if role not in ('notifications','identity-mail','sos-drills','read-model','ingestion','diagnostics','forecasts'):raise ValueError('Unknown worker role')
    if state not in ('healthy','failed','stopped'):raise ValueError('Unknown worker state')
    try:
        with session_factory() as db:
            from sqlalchemy.dialects.sqlite import insert as si
            from sqlalchemy.dialects.postgresql import insert as pi
            now=utc_now();insert=si if db.bind.dialect.name=='sqlite' else pi
            values=dict(role=role,state=state,observed_at=now,detail=detail[:64])
            if state=='healthy':values['last_success_at']=now
            statement=insert(WorkerHeartbeat).values(**values)
            db.execute(statement.on_conflict_do_update(index_elements=['role'],set_={k:v for k,v in values.items() if k!='role'}));db.commit()
    except Exception:log.warning('Worker heartbeat unavailable; monitoring will expire it')


def metrics(db,*,now=None):
    minute=int((now or utc_now()).timestamp())//60
    result={}
    for row in db.scalars(select(MetricBucket).where(MetricBucket.minute>=minute-4)):
        value=result.setdefault(row.metric,dict(count=0,failures=0,total_seconds=0.,maximum_seconds=0.,histogram={}))
        for field in ('count','failures','total_seconds'):value[field]+=getattr(row,field)
        value['maximum_seconds']=max(value['maximum_seconds'],row.maximum_seconds)
        for key,count in row.histogram.items():value['histogram'][key]=value['histogram'].get(key,0)+count
    for value in result.values():
        for quantile in (.95,.99):
            count=0;target=math.ceil(value['count']*quantile);estimate=None
            for bound in (*BOUNDS,float('inf')):
                count+=value['histogram'].get(str(bound) if math.isfinite(bound) else 'inf',0)
                if count>=target:estimate=bound if math.isfinite(bound) else None;break
            value[f'p{int(quantile*100)}_seconds_upper_bound']=estimate
    return result


def reset():
    global _last_flush
    with _lock:_buffer.clear();_last_flush=0
