"""Synthetic rain read benchmark. No device, broker, live journal or API DB access."""
import argparse,json,math,shutil,statistics,sys,tempfile,time
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from app.services.rain_gauge_service import RainGaugeStore
from rain_reference import RawReference


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days',type=int,default=30)
    parser.add_argument('--cadence-seconds',type=int,default=5)
    parser.add_argument('--summary-years',type=int,default=5)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    count=args.days*86400//args.cadence_seconds+1
    if not 2<=args.days<=60 or not 5<=args.cadence_seconds<=30 or not 1<=args.summary_years<=10 or count>1100000:raise ValueError('Synthetic workload exceeds the bounded benchmark budget')
    reserve=count*2200+512*1024*1024
    if shutil.disk_usage(tempfile.gettempdir()).free<reserve:raise RuntimeError('Insufficient free space for the disposable benchmark and WAL reserve')
    with tempfile.TemporaryDirectory(prefix='agapay-rain-bench-') as temporary:
        path=Path(temporary)/'synthetic.db';store=RainGaugeStore(path,raw_retention_days=args.days)
        now=datetime.now(timezone.utc).replace(microsecond=0);begin=now-timedelta(days=args.days);origin=int(begin.timestamp());cadence=args.cadence_seconds
        packet=dict(schema_version=1,station_id='RAIN_BENCH',boot_id='SYNTHETIC',packet_sequence=1,cumulative_tip_count=0,boot_start_tip_count=0,interval_start_tip_count=0,
            mm_per_tip=.7,rainfall_increment_mm=0,device_uptime_ms=0,last_tip_uptime_ms=None,interval_start_uptime_ms=0,counter_persisted=True,data_source='physical_rain_gauge',firmware_version='synthetic-benchmark')
        with store.connect() as db:
            db.execute('''WITH RECURSIVE n(i) AS(SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<?)
              INSERT INTO events(station,source,boot,sequence,count,delta,mm,mm_per_tip,received,last_tip,allocated_hour,interval_start,interval_end,recovered,payload)
              SELECT 'RAIN_BENCH','physical_rain_gauge','SYNTHETIC',i,0,0,0,.7,
              strftime('%Y-%m-%dT%H:%M:%S+00:00',?+(i-1)*?,'unixepoch'),NULL,NULL,
              strftime('%Y-%m-%dT%H:%M:%S+00:00',?+MAX(0,i-2)*?,'unixepoch'),
              strftime('%Y-%m-%dT%H:%M:%S+00:00',?+(i-1)*?,'unixepoch'),0,
              json_set(?,'$.packet_sequence',i,'$.device_uptime_ms',(i-1)*?*1000) FROM n''',
              (count,origin,cadence,origin,cadence,origin,cadence,json.dumps(packet),cadence))
            db.execute('''INSERT INTO rain_hour_totals SELECT station,source,strftime('%Y-%m-%dT%H:00:00+00:00',received),MIN(received),MAX(received),COUNT(*),?,0,0,0 FROM events GROUP BY station,source,strftime('%Y-%m-%dT%H:00:00+00:00',received)''',(cadence,))
            db.execute("INSERT INTO rain_hour_versions SELECT station,source,hour,'legacy-unversioned' FROM rain_hour_totals")
            last=dict(db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 1').fetchone());last['provenance']=None
            db.execute('INSERT INTO rain_stream_totals VALUES(?,?,?,?,?,?,?,NULL)',('RAIN_BENCH','physical_rain_gauge',0,0,0,json.dumps(last),None))
            db.execute('INSERT INTO rain_session_totals VALUES(?,?,?,?)',('RAIN_BENCH','physical_rain_gauge','SYNTHETIC',0))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)',('RAIN_BENCH','physical_rain_gauge','SYNTHETIC',0,0,count,(count-1)*cadence*1000,now.isoformat(),begin.isoformat()))
            # Older synthetic summaries exercise years of retention without
            # allocating years of raw heartbeat files. This is not field evidence.
            hour=begin.replace(minute=0,second=0)-timedelta(days=args.summary_years*365)
            while hour<begin:
                text=hour.isoformat();db.execute('INSERT OR IGNORE INTO rain_hour_totals VALUES(?,?,?,?,?,?,?,?,?,?)',('RAIN_BENCH','physical_rain_gauge',text,text,(hour+timedelta(minutes=59,seconds=55)).isoformat(),720,5,0,0,0));hour+=timedelta(hours=1)
        reference=RawReference(path)
        def call(reader):return reader.snapshot('RAIN_BENCH','physical_rain_gauge',now=now,anchor_at=now-timedelta(minutes=10))
        old=call(reference);new=call(store)
        assert old['completed_hours']==new['completed_hours'] and old['accepted_rainfall_mm']==new['accepted_rainfall_mm']==0
        def measure(reader):
            times=[];cpu=time.process_time()
            for _ in range(10):
                start=time.perf_counter();call(reader);times.append(time.perf_counter()-start)
            result=dict(iterations=10,cpu_seconds=time.process_time()-cpu,p50_seconds=statistics.median(times),p95_seconds=sorted(times)[-1],p99_seconds=sorted(times)[-1])
            original=reader.connect;instructions=0
            @contextmanager
            def tracked():
                nonlocal instructions
                with original() as db:
                    def progress():
                        nonlocal instructions
                        instructions+=1000;return 0
                    db.set_progress_handler(progress,1000);yield db
            reader.connect=tracked
            try:call(reader)
            finally:reader.connect=original
            result['sqlite_vm_instructions_approx']=instructions
            return result
        baseline=measure(reference);optimized=measure(store)
        with store.connect() as db:
            plans={name:[r['detail'] for r in db.execute('EXPLAIN QUERY PLAN '+sql,values)] for name,sql,values in (
                ('hours','SELECT * FROM rain_hour_totals WHERE station=? AND source=? AND hour>=? AND hour<=?',('RAIN_BENCH','physical_rain_gauge',(now-timedelta(hours=25)).isoformat(),now.isoformat())),
                ('latest_tips','SELECT * FROM events WHERE station=? AND source=? AND id>? AND delta>0 ORDER BY id DESC LIMIT 100',('RAIN_BENCH','physical_rain_gauge',0)),
                ('anchor','SELECT SUM(mm) FROM events WHERE station=? AND source=? AND received>? AND received<? AND recovered=0',('RAIN_BENCH','physical_rain_gauge',(now-timedelta(minutes=10)).isoformat(),now.isoformat())),
                ('gaps','SELECT * FROM gaps WHERE station=? AND source=? AND end>=? AND start<?',('RAIN_BENCH','physical_rain_gauge',(now-timedelta(hours=25)).isoformat(),now.isoformat())),
            )}
            hours=db.execute('SELECT COUNT(*) FROM rain_hour_totals').fetchone()[0]
        result=dict(raw_events=count,raw_retention_days=args.days,cadence_seconds=cadence,summary_rows=hours,summary_years=args.summary_years,journal_bytes=path.stat().st_size,
            baseline=baseline,optimized=optimized,query_plans=plans,products_equal=True,
            scope='One synthetic station, zero-rain heartbeat load, warm local SQLite reads. Bulk-generated benchmark data; not ingestion throughput, power, physical calibration or managed-store capacity evidence.')
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
