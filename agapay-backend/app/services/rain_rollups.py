"""Versioned rain read model. Raw observation and rollups commit together."""
from collections import OrderedDict
from datetime import datetime,timedelta,timezone
import json,sqlite3
from threading import RLock

VERSION=3
_initialized=OrderedDict()
_lock=RLock()

SCHEMA='''
CREATE INDEX IF NOT EXISTS ix_rain_events_received ON events(station,source,received,id);
CREATE INDEX IF NOT EXISTS ix_rain_archive_retention ON events(received,id);
CREATE INDEX IF NOT EXISTS ix_rain_gap_retention ON gaps(end);
CREATE INDEX IF NOT EXISTS ix_rain_events_latest ON events(station,source,id DESC);
CREATE INDEX IF NOT EXISTS ix_rain_events_tips ON events(station,source,id DESC) WHERE delta>0;
CREATE INDEX IF NOT EXISTS ix_rain_events_anchor ON events(station,source,received) WHERE recovered=0;
CREATE INDEX IF NOT EXISTS ix_rain_gaps_overlap ON gaps(station,source,end,start);
CREATE INDEX IF NOT EXISTS ix_rain_sessions_latest ON sessions(station,source,received DESC);
CREATE TABLE IF NOT EXISTS rain_stream_totals(
 station TEXT NOT NULL,source TEXT NOT NULL,tips INTEGER NOT NULL,mm REAL NOT NULL,recovered REAL NOT NULL,
 last_event TEXT NOT NULL,last_tip TEXT,archived_until TEXT,PRIMARY KEY(station,source));
CREATE TABLE IF NOT EXISTS rain_session_totals(
 station TEXT NOT NULL,source TEXT NOT NULL,boot TEXT NOT NULL,mm REAL NOT NULL,PRIMARY KEY(station,source,boot));
CREATE TABLE IF NOT EXISTS rain_hour_totals(
 station TEXT NOT NULL,source TEXT NOT NULL,hour TEXT NOT NULL,first_received TEXT NOT NULL,last_received TEXT NOT NULL,
 samples INTEGER NOT NULL,max_gap REAL NOT NULL,mm REAL NOT NULL,tips INTEGER NOT NULL,certain_mm REAL NOT NULL,
 PRIMARY KEY(station,source,hour));
CREATE TABLE IF NOT EXISTS rain_hour_versions(
 station TEXT NOT NULL,source TEXT NOT NULL,hour TEXT NOT NULL,version TEXT NOT NULL,PRIMARY KEY(station,source,hour,version));
CREATE TABLE IF NOT EXISTS rain_archives(
 id TEXT PRIMARY KEY,path TEXT NOT NULL UNIQUE,sha256 TEXT NOT NULL,events INTEGER NOT NULL,gaps INTEGER NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rain_archive_segments(
 station TEXT NOT NULL,source TEXT NOT NULL,boot TEXT NOT NULL,first_sequence INTEGER NOT NULL,last_sequence INTEGER NOT NULL,
 first_received TEXT NOT NULL,last_received TEXT NOT NULL,archive_id TEXT NOT NULL REFERENCES rain_archives(id),
 PRIMARY KEY(station,source,boot,archive_id));
CREATE INDEX IF NOT EXISTS ix_rain_archive_lookup ON rain_archive_segments(station,source,boot,first_sequence,last_sequence);
'''


def apply_statements(db,script):
    # executescript implicitly commits. Preserve the caller's migration transaction.
    for statement in script.split(';'):
        if statement.strip():db.execute(statement)


def summarize(db,row,provenance=None):
    event=dict(row);event['provenance']=dict(provenance) if provenance else None
    encoded=json.dumps(event,separators=(',',':'))
    key=(row['station'],row['source']);hour=datetime.fromisoformat(row['received']).replace(minute=0,second=0,microsecond=0).isoformat()
    previous=db.execute('SELECT last_received FROM rain_hour_totals WHERE station=? AND source=? AND hour=?',(*key,hour)).fetchone()
    gap=max(0,(datetime.fromisoformat(row['received'])-datetime.fromisoformat(previous['last_received'])).total_seconds()) if previous else 0
    allocated=row['allocated_hour']==hour
    db.execute('''INSERT INTO rain_stream_totals VALUES(?,?,?,?,?,?,?,NULL)
      ON CONFLICT(station,source) DO UPDATE SET tips=tips+excluded.tips,mm=mm+excluded.mm,recovered=recovered+excluded.recovered,
      last_event=excluded.last_event,last_tip=COALESCE(excluded.last_tip,rain_stream_totals.last_tip)''',
      (*key,row['delta'],row['mm'],row['mm'] if row['recovered'] else 0,encoded,encoded if row['delta'] else None))
    db.execute('''INSERT INTO rain_session_totals VALUES(?,?,?,?) ON CONFLICT(station,source,boot) DO UPDATE SET mm=mm+excluded.mm''',(*key,row['boot'],row['mm']))
    db.execute('''INSERT INTO rain_hour_totals VALUES(?,?,?,?,?,1,?,?,?,?) ON CONFLICT(station,source,hour) DO UPDATE SET
      last_received=excluded.last_received,samples=samples+1,max_gap=MAX(max_gap,excluded.max_gap),mm=mm+excluded.mm,
      tips=tips+excluded.tips,certain_mm=certain_mm+excluded.certain_mm''',
      (*key,hour,row['received'],row['received'],gap,row['mm'] if allocated else 0,row['delta'] if allocated else 0,row['mm'] if not row['recovered'] else 0))
    version=json.loads(row['payload']).get('calibration_version','legacy-unversioned')
    db.execute('INSERT OR IGNORE INTO rain_hour_versions VALUES(?,?,?,?)',(*key,hour,version))


def upgrade(db):
    version=db.execute('PRAGMA user_version').fetchone()[0]
    if version==VERSION:return
    if version!=0:raise ValueError('Unsupported rain journal schema; restore/review required')
    db.execute('BEGIN IMMEDIATE')
    try:
        apply_statements(db,SCHEMA)
        cursor=db.execute('SELECT * FROM events ORDER BY id')
        while rows:=cursor.fetchmany(1000):
            for row in rows:
                provenance=db.execute('SELECT * FROM ingress_provenance WHERE event_id=?',(row['id'],)).fetchone()
                summarize(db,row,provenance)
        db.execute(f'PRAGMA user_version={VERSION}');db.commit()
    except BaseException:db.rollback();raise


def require_current(db):
    if db.execute('PRAGMA user_version').fetchone()[0]!=VERSION:
        raise ValueError('Rain journal migration required: run python -m app.rain_journal upgrade on a verified backup first')


def initialized(path,initialize):
    """Only writer construction checks setup, once per inode per process (bounded)."""
    path=path.resolve()
    with _lock:
        stat=path.stat() if path.exists() else None
        key=(str(path),stat.st_dev if stat else None,stat.st_ino if stat else None)
        if key in _initialized:return
        initialize(not path.exists())
        stat=path.stat();key=(str(path),stat.st_dev,stat.st_ino)
        _initialized[key]=True
        while len(_initialized)>128:_initialized.popitem(last=False)


def snapshot(store,station,source,*,now,since_id=0,anchor_at=None):
    from app.services.rain_gauge_service import hour_start
    empty=dict(station_id=station,data_source=source,connected=False,checked_at=now.isoformat(),status='no_data',events=[],completed_hours=[],ml_ready=False)
    if not store.path.exists():return empty
    start=hour_start(now);key=(station,source);begin=start-timedelta(hours=25)
    with store.lock,store.connect() as db:
        # One WAL read transaction keeps summaries, session metadata and raw edges
        # on the same committed cut while ingestion continues on another connection.
        db.execute('BEGIN')
        require_current(db)
        totals=db.execute('SELECT * FROM rain_stream_totals WHERE station=? AND source=?',key).fetchone()
        if totals is None:return empty
        last=json.loads(totals['last_event']);tip=json.loads(totals['last_tip']) if totals['last_tip'] else None
        session=db.execute('SELECT * FROM sessions WHERE station=? AND source=? AND boot=?',(*key,last['boot'])).fetchone()
        session_mm=db.execute('SELECT mm FROM rain_session_totals WHERE station=? AND source=? AND boot=?',(*key,last['boot'])).fetchone()[0]
        hours={r['hour']:dict(r) for r in db.execute('SELECT * FROM rain_hour_totals WHERE station=? AND source=? AND hour>=? AND hour<=?',(*key,begin.isoformat(),start.isoformat()))}
        versions={}
        for r in db.execute('SELECT hour,version FROM rain_hour_versions WHERE station=? AND source=? AND hour>=? AND hour<=? ORDER BY version',(*key,begin.isoformat(),start.isoformat())):
            versions.setdefault(r['hour'],[]).append(r['version'])
        gaps=[(datetime.fromisoformat(r['start']),datetime.fromisoformat(r['end'])) for r in db.execute('SELECT start,end FROM gaps WHERE station=? AND source=? AND end>=? AND start<?',(*key,begin.isoformat(),now.isoformat()))]
        new=db.execute('SELECT * FROM events INDEXED BY ix_rain_events_tips WHERE station=? AND source=? AND id>? AND delta>0 ORDER BY id DESC LIMIT 100',(*key,since_id)).fetchall()
        after_anchor=None;anchor_status='not_requested'
        if anchor_at:
            anchor_at=anchor_at.astimezone(timezone.utc)
            if anchor_at>now:anchor_status='future_anchor'
            elif anchor_at<now-timedelta(days=store.raw_retention_days) or totals['archived_until'] and anchor_at<=datetime.fromisoformat(totals['archived_until']):anchor_status='outside_retained_raw_interval'
            else:
                boundary=hour_start(anchor_at)+timedelta(hours=1)
                edge=db.execute('SELECT COALESCE(SUM(mm),0) FROM events INDEXED BY ix_rain_events_anchor WHERE station=? AND source=? AND received>? AND received<? AND recovered=0',(*key,anchor_at.isoformat(),boundary.isoformat())).fetchone()[0]
                whole=db.execute('SELECT COALESCE(SUM(certain_mm),0) FROM rain_hour_totals WHERE station=? AND source=? AND hour>=? AND hour<=?',(*key,boundary.isoformat(),start.isoformat())).fetchone()[0]
                after_anchor=edge+whole;anchor_status='retained_receive_intervals'
    def at(value):return datetime.fromisoformat(value)
    def row(hour):return hours.get(hour.isoformat())
    def previous(hour):
        current=row(hour)
        if current and at(current['first_received'])==hour:return hour
        prior=row(hour-timedelta(hours=1));return at(prior['last_received']) if prior else None
    def uncertain(a,b):return any(x<b and y>=a for x,y in gaps)
    completed=[]
    for offset in range(24,0,-1):
        a=start-timedelta(hours=offset);b=a+timedelta(hours=1);current=row(a);prior=previous(a);following=row(b)
        after=at(following['first_received']) if following else None
        valid=bool(current and prior and after and 0<=(a-prior).total_seconds()<=30 and 0<=(after-b).total_seconds()<=30
            and current['max_gap']<=30 and (at(current['first_received'])-prior).total_seconds()<=30
            and (after-at(current['last_received'])).total_seconds()<=30 and not uncertain(a,b))
        completed.append(dict(timestamp_utc=b.isoformat(),interval_start=a.isoformat(),interval_end=b.isoformat(),interval_seconds=3600,
            rainfall_mm=current['mm'] if valid else None,valid=valid,quality='valid' if valid else 'unknown',
            tip_count=current['tips'] if valid else None,source=source,calibration_versions=versions.get(a.isoformat(),[]),
            coverage='continuous receive coverage' if valid else 'missing or uncertain receive coverage'))
    age=(now-at(session['received'])).total_seconds();current=row(start);prior=previous(start)
    covered=bool(current and prior and 0<=(start-prior).total_seconds()<=30 and 0<=age<=30 and current['max_gap']<=30
        and (at(current['first_received'])-prior).total_seconds()<=30 and not uncertain(start,now))
    version=json.loads(last['payload']).get('calibration_version','legacy-unversioned')
    product_versions=sorted(set([version,*versions.get(start.isoformat(),[])]));mm=current['mm'] if current else 0
    product=dict(product='current_hour_received_tips',interval_start=start.isoformat(),interval_end=now.isoformat(),rainfall_mm=mm,
        tip_count=current['tips'] if current else 0,quality='partial',coverage_complete=covered,
        coverage='covered so far; hour incomplete' if covered else 'missing or uncertain coverage; received tips only',source=source,
        calibration_version=version if len(product_versions)==1 else 'mixed',calibration_versions=product_versions,
        mm_per_tip=last['mm_per_tip'] if len(product_versions)==1 else None,timestamp_basis='server receive intervals; occurrence during gaps remains unknown')
    provenance=last.get('provenance') or {}
    return dict(station_id=station,data_source=source,boot_id=session['boot'],connected=0<=age<=30,
        source_class=provenance.get('source_class','unverified'),source_trusted=provenance.get('source_class')=='physical_device' and provenance.get('stream')=='operational',
        status='fresh' if 0<=age<=30 else 'stale',checked_at=now.isoformat(),last_received_at=session['received'],age_seconds=max(0,age),
        cumulative_tip_count=session['last_count'],boot_session_tip_count=session['last_count']-session['boot_start'],accepted_tip_count=totals['tips'],accepted_rainfall_mm=totals['mm'],
        session_rainfall_mm=session_mm,anchor_at=anchor_at.isoformat() if anchor_at else None,rainfall_after_anchor_mm=after_anchor,anchor_status=anchor_status,
        mm_per_tip=last['mm_per_tip'],latest_increment_mm=tip['mm'] if tip else 0,last_tip_at=(tip['last_tip'] or tip['received']) if tip else None,
        last_tip_received_at=tip['received'] if tip else None,current_hour_start=start.isoformat(),incomplete_hour_mm=mm,current_hour_product=product,
        calibration_version=version,quality='valid',product_version=3,unallocated_recovered_mm=totals['recovered'],latest_event_id=last['id'],latest_tip_event_id=tip['id'] if tip else 0,
        events=[dict(id=e['id'],tip_count=e['count'],delta_tips=e['delta'],rainfall_increment_mm=e['mm'],received_at=e['received'],last_tip_at=e['last_tip'],
            recovered=bool(e['recovered']),interval_start=e['interval_start'],interval_end=e['interval_end'],quality='timing_uncertain' if e['recovered'] else 'received_interval',source=source,
            calibration_version=json.loads(e['payload']).get('calibration_version','legacy-unversioned')) for e in reversed(new)],
        events_scope='latest 100 retained raw tip events; older events require verified archives',raw_archived_until=totals['archived_until'],raw_retention_days=store.raw_retention_days,
        completed_hours=completed,ml_ready=all(h['valid'] for h in completed),timestamp_basis='server receive intervals; device uptime estimates last tip; gaps remain unknown')
