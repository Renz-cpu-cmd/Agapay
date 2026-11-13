"""Frozen pre-F32 snapshot oracle, used only for compatibility tests."""
from datetime import datetime,timedelta,timezone
import json
from threading import RLock
from contextlib import contextmanager,closing
import sqlite3
UTC=timezone.utc
def hour_start(time):return time.astimezone(UTC).replace(minute=0,second=0,microsecond=0)
class RawReference:
    def __init__(self,path):self.path=path;self.lock=RLock()
    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            yield db
    def snapshot(self,station: str,source: str,*,now: datetime|None=None,since_id: int=0,anchor_at: datetime|None=None) -> dict:
        now=(now or datetime.now(UTC)).astimezone(UTC)
        with self.lock,self.connect() as db:
            session=db.execute("SELECT * FROM sessions WHERE station=? AND source=? ORDER BY received DESC,rowid DESC LIMIT 1",(station,source)).fetchone()
            events=db.execute("SELECT * FROM events WHERE station=? AND source=? AND received>=? ORDER BY id",(station,source,(hour_start(now)-timedelta(hours=25)).isoformat())).fetchall()
            gaps=db.execute("SELECT * FROM gaps WHERE station=? AND source=?",(station,source)).fetchall()
            totals=db.execute("SELECT COALESCE(SUM(delta),0) tips,COALESCE(SUM(mm),0) mm,COALESCE(SUM(CASE WHEN recovered=1 THEN mm ELSE 0 END),0) recovered FROM events WHERE station=? AND source=?",(station,source)).fetchone()
            session_amount=db.execute("SELECT COALESCE(SUM(mm),0) FROM events WHERE station=? AND source=? AND boot=?",(station,source,session['boot'])).fetchone()[0] if session else None
            latest_tip=db.execute("SELECT * FROM events WHERE station=? AND source=? AND delta>0 ORDER BY id DESC LIMIT 1",(station,source)).fetchone()
            last_event=db.execute("SELECT * FROM events WHERE station=? AND source=? ORDER BY id DESC LIMIT 1",(station,source)).fetchone()
            provenance=db.execute("SELECT * FROM ingress_provenance WHERE event_id=?",(last_event['id'],)).fetchone() if last_event else None
            new_events=db.execute("SELECT * FROM events WHERE station=? AND source=? AND id>? AND delta>0 ORDER BY id DESC LIMIT 100",(station,source,since_id)).fetchall()
            # Outage recovery has uncertain occurrence time; retain it in totals,
            # but never add it to a newer depth initialization automatically.
            after_anchor=db.execute("SELECT COALESCE(SUM(mm),0) FROM events WHERE station=? AND source=? AND received>? AND recovered=0",(station,source,anchor_at.astimezone(UTC).isoformat())).fetchone()[0] if anchor_at else None
        if session is None:
            return {"station_id":station,"data_source":source,"connected":False,"checked_at":now.isoformat(),"status":"no_data","events":[],"completed_hours":[],"ml_ready":False}
        heartbeat=datetime.fromisoformat(session['received']);age=(now-heartbeat).total_seconds()
        start=hour_start(now)
        timed=[(e,datetime.fromisoformat(e['received'])) for e in events]
        parsed_gaps=[(datetime.fromisoformat(g['start']),datetime.fromisoformat(g['end'])) for g in gaps]
        completed=[]
        for offset in range(24,0,-1):
            begin=start-timedelta(hours=offset);end=begin+timedelta(hours=1)
            hour_events=[t for e,t in timed if begin<=t<end]
            previous=[t for e,t in timed if t<=begin]
            after=[t for e,t in timed if end<=t<=end+timedelta(seconds=30)]
            uncertain=any(a<end and b>=begin for a,b in parsed_gaps)
            bounds=bool(previous and after and (begin-previous[-1]).total_seconds()<=30)
            timeline=[previous[-1]] if previous else []
            timeline += hour_events
            if after:timeline.append(after[0])
            continuous=bounds and all((b-a).total_seconds()<=30 for a,b in zip(timeline,timeline[1:]))
            valid=bool(continuous and not uncertain)
            amount=sum(e['mm'] for e in events if e['allocated_hour']==begin.isoformat()) if valid else None
            completed.append({"timestamp_utc":end.isoformat(),"interval_start":begin.isoformat(),"interval_seconds":3600,"rainfall_mm":amount,"valid":valid})
            completed[-1].update(interval_end=end.isoformat(),quality="valid" if valid else "unknown",
                tip_count=sum(e['delta'] for e in events if e['allocated_hour']==begin.isoformat()) if valid else None,
                source=source,calibration_versions=sorted({json.loads(e['payload']).get('calibration_version','legacy-unversioned') for e in events if begin<=datetime.fromisoformat(e['received'])<end}),
                coverage="continuous receive coverage" if valid else "missing or uncertain receive coverage")
        latest_new=list(reversed(new_events))
        previous=[t for e,t in timed if t<=start]
        hour_times=([previous[-1]] if previous else [])+[t for e,t in timed if start<t<=now]
        hour_covered=bool(previous and (start-previous[-1]).total_seconds()<=30 and age<=30 and all((b-a).total_seconds()<=30 for a,b in zip(hour_times,hour_times[1:])) and not any(a<now and b>=start for a,b in parsed_gaps))
        current_events=[e for e in events if e['allocated_hour']==start.isoformat()]
        current_mm=sum(e['mm'] for e in current_events)
        calibration_version=json.loads(last_event['payload']).get('calibration_version','legacy-unversioned')
        product_versions=sorted({calibration_version}|{json.loads(e['payload']).get('calibration_version','legacy-unversioned') for e in current_events})
        current_product=dict(product="current_hour_received_tips",interval_start=start.isoformat(),interval_end=now.isoformat(),
            rainfall_mm=current_mm,tip_count=sum(e['delta'] for e in current_events),quality="partial",
            coverage_complete=hour_covered,coverage="covered so far; hour incomplete" if hour_covered else "missing or uncertain coverage; received tips only",
            source=source,calibration_version=calibration_version if len(product_versions)==1 else "mixed",
            calibration_versions=product_versions,mm_per_tip=last_event['mm_per_tip'] if len(product_versions)==1 else None,
            timestamp_basis="server receive intervals; occurrence during gaps remains unknown")
        return {"station_id":station,"data_source":source,"boot_id":session['boot'],"connected":0<=age<=30,
                "source_class":provenance['source_class'] if provenance else "unverified",
                "source_trusted":bool(provenance and provenance['source_class']=='physical_device' and provenance['stream']=='operational'),
                "status":"fresh" if 0<=age<=30 else "stale","checked_at":now.isoformat(),"last_received_at":session['received'],"age_seconds":max(0,age),
                "cumulative_tip_count":session['last_count'],"boot_session_tip_count":session['last_count']-session['boot_start'],
                "accepted_tip_count":totals['tips'],"accepted_rainfall_mm":totals['mm'],
                "session_rainfall_mm":session_amount,
                "anchor_at":anchor_at.astimezone(UTC).isoformat() if anchor_at else None,"rainfall_after_anchor_mm":after_anchor,
                "mm_per_tip":last_event['mm_per_tip'],"latest_increment_mm":latest_tip['mm'] if latest_tip else 0,
                "last_tip_at":latest_tip['last_tip'] or latest_tip['received'] if latest_tip else None,
                "last_tip_received_at":latest_tip['received'] if latest_tip else None,
                "current_hour_start":start.isoformat(),"incomplete_hour_mm":current_mm,"current_hour_product":current_product,
                "calibration_version":calibration_version,"quality":"valid","product_version":2,
                "unallocated_recovered_mm":totals['recovered'],
                "latest_event_id":last_event['id'],"latest_tip_event_id":latest_tip['id'] if latest_tip else 0,
                "events":[{"id":e['id'],"tip_count":e['count'],"delta_tips":e['delta'],"rainfall_increment_mm":e['mm'],"received_at":e['received'],"last_tip_at":e['last_tip'],"recovered":bool(e['recovered']),"interval_start":e['interval_start'],"interval_end":e['interval_end'],"quality":"timing_uncertain" if e['recovered'] else "received_interval","source":source,"calibration_version":json.loads(e['payload']).get('calibration_version','legacy-unversioned')} for e in latest_new],
                "completed_hours":completed,"ml_ready":all(h['valid'] for h in completed),
                "timestamp_basis":"server receive intervals; device uptime estimates last tip; gaps remain unknown"}
