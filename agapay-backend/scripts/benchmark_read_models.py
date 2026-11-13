"""Synthetic ASGI benchmark; private disposable DB, no broker/provider/live data.

Run each mode in a fresh process. HTTP timings include ASGI/auth/SQL/serialization,
but exclude network, BFF, rendering, device sensing and native battery consumption.
"""
import argparse,json,logging,math,os,secrets,sys,tempfile,time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
parser.add_argument('--mode',choices=['uncached','shared','mobile'],required=True)
parser.add_argument('--stations',type=int,default=20)
parser.add_argument('--viewers',type=int,default=40)
parser.add_argument('--rounds',type=int,default=2)
parser.add_argument('--concurrency',type=int,default=10)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if not 1<=args.stations<=100 or not 1<=args.viewers<=200 or not 1<=args.rounds<=10 or not 1<=args.concurrency<=20:
    raise SystemExit('Benchmark exceeds bounded synthetic test scale')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if args.worker:
    from app.database import SessionLocal,engine
    from app.config import get_settings
    from app.services.read_models import snapshot
    from app.services import observability as obs
    from sqlalchemy import event
    timestamps=[]
    @event.listens_for(engine,'before_cursor_execute')
    def counted(*unused):timestamps.append(time.time())
    marker=args.output
    logging.getLogger().setLevel(logging.ERROR)
    while not marker.with_suffix('.stop').exists():
        try:
            with SessionLocal() as db:snapshot(db,get_settings(),history_limit=120,refresh_before_seconds=1)
            obs.heartbeat('read-model')
        except Exception:obs.heartbeat('read-model','failed','benchmark_tick_failed')
        marker.with_suffix('.ready').write_text('ready')
        time.sleep(.5)
    obs.flush(force=True)
    marker.write_text(json.dumps(timestamps))
    engine.dispose()
    raise SystemExit(0)

scratch=tempfile.TemporaryDirectory(prefix='agapay-readmodel-bench-')
os.environ.update(AGAPAY_ENVIRONMENT='development',AGAPAY_DATABASE_URL='sqlite:///'+Path(scratch.name,'synthetic.db').as_posix(),
    AGAPAY_MQTT_ENABLED='false',AGAPAY_MQTT_EXTERNAL_SUBSCRIBER='false',AGAPAY_RAIN_GAUGE_ENABLED='false',
    AGAPAY_SEED_DEMO_DATA='false',AGAPAY_NOTIFICATION_PROVIDER='disabled',AGAPAY_IDENTITY_MAIL_PROVIDER='disabled',
    AGAPAY_HYBRID_PROJECTION_ENABLED='false',AGAPAY_PREDICTION_PREVIEW_ENABLED='false',
    AGAPAY_READ_MODEL_CACHE_ENABLED='false' if args.mode=='uncached' else 'true',AGAPAY_READ_MODEL_WORKER_ENABLED='false',
    AGAPAY_OPERATIONS_PROBE_ENABLED='false',AGAPAY_OPERATIONS_REQUIRED='["monitoring"]',AGAPAY_OBSERVABILITY_ENABLED='true')
from app.database import engine,SessionLocal
from app.migrations import upgrade
from app.models import Station,Telemetry,User,AuthSession,utc_now
from app.runtime_models import SharedReadModel
from app.services.accounts import token_digest
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import delete,event
logging.getLogger().setLevel(logging.ERROR)
upgrade(engine)
tokens=[secrets.token_urlsafe(32) for _ in range(args.viewers)]
at=utc_now()
with SessionLocal() as db:
    for i,token in enumerate(tokens):
        user=User(name='Synthetic resident',email=f'bench-{i}@synthetic.invalid',password_hash='benchmark-no-login',role='resident')
        db.add(user);db.flush();db.add(AuthSession(token_hash=token_digest(token),user_id=user.id,audience='mobile',expires_at=at+timedelta(hours=1)))
    for station in range(args.stations):
        sid=f'BENCH_{station:03d}';db.add(Station(station_id=sid,station_name='SYNTHETIC BENCHMARK'));db.flush()
        for sequence in range(120):
            measured=at-timedelta(seconds=(119-sequence)*10)
            db.add(Telemetry(station_id=sid,sequence_no=sequence,boot_id='synthetic-boot',boot_sequence=1,config_version=1,
                source_id='synthetic-only',sensor_quality='valid',water_depth_cm=20,device_uptime_ms=sequence*10000,
                measured_at=measured,recorded_at=measured,received_at=measured,eligible_for_current=True,disposition='benchmark'))
    db.commit()
queries=0
@event.listens_for(engine,'before_cursor_execute')
def count(*unused):
    global queries
    queries+=1
history=20 if args.mode=='mobile' else 120
def percentile(values,q):return sorted(values)[max(0,math.ceil(len(values)*q)-1)] if values else None
with TestClient(app) as client:
    def read(i):
        started=time.perf_counter();response=client.get('/api/monitoring/stations',params={'history_limit':history},headers={'Authorization':'Bearer '+tokens[i%args.viewers]})
        ended=time.perf_counter();age=None
        if response.status_code==200:
            payload=response.json();age=(utc_now()-datetime.fromisoformat(payload['checked_at'].replace('Z','+00:00'))).total_seconds()
        return dict(seconds=ended-started,status=response.status_code,bytes=len(response.content),snapshot_age_seconds=age,
                    retained=response.status_code==200 and 'READ_MODEL_REBUILDING' in payload.get('service_health',{}).get('codes',[]),
                    error=response.json().get('detail') if response.status_code!=200 else None,
                    request_queries=int(response.headers.get('X-DB-Queries','0')))
    def phase(indices):
        global queries
        queries=0;cpu=time.process_time();start=time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:rows=list(pool.map(read,indices))
        wall=time.perf_counter()-start;cpu=time.process_time()-cpu
        good=[r for r in rows if r['status']==200]
        return dict(requests=len(rows),status_counts=dict(Counter(r['status'] for r in rows)),sql_statements=queries,
            retained_refresh_responses=sum(r['retained'] for r in rows),errors=dict(Counter(str(r['error']) for r in rows if r['error'])),
            cpu_seconds=cpu,wall_seconds=wall,cpu_seconds_per_success=cpu/len(good) if good else None,
            response_bytes=sum(r['bytes'] for r in rows),mean_success_bytes=sum(r['bytes'] for r in good)/len(good) if good else None,
            p95_http_seconds=percentile([r['seconds'] for r in rows],.95),p99_http_seconds=percentile([r['seconds'] for r in rows],.99),
            p95_snapshot_age_seconds=percentile([r['snapshot_age_seconds'] for r in good],.95),
            p99_snapshot_age_seconds=percentile([r['snapshot_age_seconds'] for r in good],.99))
    cold=phase(range(args.concurrency))
    warm=read(0)
    producer=None
    worker_data=Path(scratch.name,'worker.json')
    def worker_cpu():
        if producer is None:return 0.
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            kernel=ctypes.windll.kernel32
            class Entry(ctypes.Structure):
                _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),('heap',ctypes.c_void_p),('module',wintypes.DWORD),('threads',wintypes.DWORD),('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('name',wintypes.WCHAR*260)]
            kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
            kernel.OpenProcess.restype=wintypes.HANDLE
            kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
            kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
            kernel.CloseHandle.argtypes=[wintypes.HANDLE]
            snapshot=kernel.CreateToolhelp32Snapshot(2,0);entry=Entry();entry.size=ctypes.sizeof(entry);parents={}
            try:
                found=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
                while found:
                    parents[entry.pid]=entry.parent;found=kernel.Process32NextW(snapshot,ctypes.byref(entry))
            finally:kernel.CloseHandle(snapshot)
            # A Windows venv redirector may start the real interpreter as a child.
            # Include the entire owned worker tree, never unrelated Python apps.
            owned={producer.pid}
            while True:
                more={pid for pid,parent in parents.items() if parent in owned}
                if more<=owned:break
                owned|=more
            total=0.
            for pid in owned:
                handle=kernel.OpenProcess(0x1000,False,pid)
                if not handle:raise OSError('Cannot read owned benchmark worker CPU')
                try:
                    values=[wintypes.FILETIME() for _ in range(4)]
                    if not kernel.GetProcessTimes(wintypes.HANDLE(handle),*[ctypes.byref(v) for v in values]):raise OSError('Cannot read benchmark worker CPU')
                    total+=sum((v.dwHighDateTime<<32)+v.dwLowDateTime for v in values[2:])/10000000
                finally:kernel.CloseHandle(handle)
            return total
        fields=Path(f'/proc/{producer.pid}/stat').read_text().split()
        return (int(fields[13])+int(fields[14]))/os.sysconf('SC_CLK_TCK')
    if args.mode!='uncached':
        producer=subprocess.Popen([sys.executable,'-u',__file__,'--worker','--mode',args.mode,'--output',str(worker_data)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        import atexit
        def stop_owned_worker():
            if producer.poll() is None:
                worker_data.with_suffix('.stop').write_text('stop')
                producer.wait(timeout=15)
        atexit.register(stop_owned_worker)
        deadline=time.monotonic()+30
        while not worker_data.with_suffix('.ready').exists():
            if producer.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Isolated benchmark producer failed to start')
            time.sleep(.05)
    worker_before=worker_cpu();phase_start=time.time()
    steady=phase(range(args.viewers*args.rounds))
    phase_end=time.time();worker_used=worker_cpu()-worker_before
    steady['api_cpu_seconds']=steady['cpu_seconds'];steady['producer_cpu_seconds']=worker_used
    steady['cpu_seconds']+=worker_used
    steady['cpu_seconds_per_success']=steady['cpu_seconds']/steady['status_counts'].get(200,1)
    # A new committed observation must become visible within the bounded cache TTL.
    committed=utc_now()
    with SessionLocal() as db:
        db.add(Telemetry(station_id='BENCH_000',sequence_no=120,boot_id='synthetic-boot',boot_sequence=1,config_version=1,
            source_id='synthetic-only',sensor_quality='valid',water_depth_cm=21,device_uptime_ms=1200000,
            measured_at=committed,recorded_at=committed,received_at=committed,eligible_for_current=True,disposition='benchmark'));db.commit()
    seen=None;attempts=0
    while (utc_now()-committed).total_seconds()<15:
        attempts+=1;response=client.get('/api/monitoring/stations',params={'history_limit':history},headers={'Authorization':'Bearer '+tokens[0]})
        if response.status_code==200 and response.json()['stations'][0]['latest_depth_cm']==21:
            seen=(utc_now()-committed).total_seconds();break
        time.sleep(.1)
    if producer:
        worker_data.with_suffix('.stop').write_text('stop');producer.wait(timeout=15)
        steady['producer_sql_statements']=sum(phase_start<=at<=phase_end for at in json.loads(worker_data.read_text()))
        steady['sql_statements']+=steady['producer_sql_statements']
result=dict(mode=args.mode,stations=args.stations,viewers=args.viewers,rounds=args.rounds,concurrency=args.concurrency,
    samples_per_station=120,response_history_limit=history,cold=cold,steady=steady,
    committed_to_first_visible_seconds=seen,visibility_probe_attempts=attempts,
    scope='Synthetic SQLite ASGI; dedicated producer process in shared modes; CPU and SQL include producer. No TCP/BFF/render/device/battery evidence. All modes include auth and workflow instrumentation.')
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
from app.services import observability as obs
obs.flush(force=True)
with SessionLocal() as db:result['producer_metrics']={k:v for k,v in obs.metrics(db).items() if k.startswith('readmodel.')}
args.output.write_text(json.dumps(result,indent=2)+'\n')
engine.dispose();scratch.cleanup();print(json.dumps(result))
