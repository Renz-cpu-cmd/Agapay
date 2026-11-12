"""Durable rain journal outside operational tables. Counts never trigger alerts."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sqlite3
from threading import RLock
from contextlib import contextmanager
from app.rain_schemas import RainCounterEvent

UTC=timezone.utc


def hour_start(time: datetime) -> datetime:
    return time.astimezone(UTC).replace(minute=0,second=0,microsecond=0)


class RainGaugeStore:
    def __init__(self,path: Path,*,read_only=False,raw_retention_days=30):
        self.path=Path(path)
        self.read_only=read_only
        if not 2<=raw_retention_days<=365:raise ValueError('Raw rain retention must be 2..365 days')
        self.raw_retention_days=raw_retention_days
        self.lock=RLock()
        if not read_only:
            from app.services.rain_rollups import initialized
            initialized(self.path,self._initialize)

    def _initialize(self,new):
        from app.services.rain_rollups import require_current,upgrade
        if not new:
            with self.connect() as db:require_current(db)
            return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('\n              CREATE TABLE IF NOT EXISTS sessions (\n                station TEXT NOT NULL, source TEXT NOT NULL, boot TEXT NOT NULL,\n                boot_start INTEGER NOT NULL, last_count INTEGER NOT NULL, last_seq INTEGER NOT NULL,\n                uptime INTEGER NOT NULL, received TEXT NOT NULL, boot_origin TEXT NOT NULL,\n                PRIMARY KEY(station,source,boot));\n              CREATE TABLE IF NOT EXISTS events (\n                id INTEGER PRIMARY KEY AUTOINCREMENT, station TEXT NOT NULL, source TEXT NOT NULL,\n                boot TEXT NOT NULL, sequence INTEGER NOT NULL, count INTEGER NOT NULL,\n                delta INTEGER NOT NULL, mm REAL NOT NULL, mm_per_tip REAL NOT NULL, received TEXT NOT NULL,\n                last_tip TEXT, allocated_hour TEXT, interval_start TEXT NOT NULL, interval_end TEXT NOT NULL,\n                recovered INTEGER NOT NULL, payload TEXT NOT NULL,\n                UNIQUE(station,source,boot,sequence));\n              CREATE TABLE IF NOT EXISTS gaps (\n                station TEXT NOT NULL,source TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,reason TEXT NOT NULL);\n              CREATE TABLE IF NOT EXISTS ingress_provenance (\n                event_id INTEGER PRIMARY KEY REFERENCES events(id), credential_id TEXT NOT NULL,\n                ingress_transport TEXT NOT NULL, ingress_identity TEXT NOT NULL, source_class TEXT NOT NULL,\n                stream TEXT NOT NULL, registry_version INTEGER NOT NULL);\n            ')
            upgrade(db)

    @contextmanager
    def connect(self):
        from urllib.parse import quote
        db=sqlite3.connect(f"file:{quote(self.path.resolve().as_posix())}?mode=ro",uri=True,timeout=1) if self.read_only else sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def ingest(self,event: RainCounterEvent,calibrated_mm: float,*,now: datetime|None=None, provenance: dict|None=None) -> dict:
        now=(now or datetime.now(UTC)).astimezone(UTC)
        if not math.isfinite(calibrated_mm) or calibrated_mm<=0 or not math.isclose(event.mm_per_tip,calibrated_mm,rel_tol=1e-5):
            raise ValueError("Device mm/tip differs from configured operator-confirmed calibration")
        with self.lock,self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            identity=(event.station_id,event.data_source,event.boot_id)
            session=db.execute("SELECT * FROM sessions WHERE station=? AND source=? AND boot=?",identity).fetchone()
            latest=db.execute("SELECT * FROM sessions WHERE station=? AND source=? ORDER BY received DESC,rowid DESC LIMIT 1",identity[:2]).fetchone()
            prior_event=db.execute("SELECT * FROM events WHERE station=? AND source=? ORDER BY id DESC LIMIT 1",identity[:2]).fetchone()
            existing=db.execute("SELECT payload FROM events WHERE station=? AND source=? AND boot=? AND sequence=?",(*identity,event.packet_sequence)).fetchone()
            if not existing and session and event.packet_sequence<=session['last_seq']:
                from app.services.rain_archive import archived_payload
                payload=archived_payload(db,event)
                if payload is None:raise ValueError('Packet is not a verified committed observation; no acknowledgement')
                existing={'payload':payload}
            if existing and RainCounterEvent.model_validate_json(existing['payload']).model_dump()!=event.model_dump():
                raise ValueError("Conflicting repeated MQTT packet; committed data cannot be overwritten")
            if session and latest and latest['boot']!=event.boot_id:
                # An old queued boot must not become current again or manufacture connectivity.
                if not existing:raise ValueError('Uncommitted packet from a retired boot; reconciliation required, no acknowledgement')
                return {"accepted":False,"duplicate":True,"reason":"retired_boot","delta_tips":0}
            if session and event.packet_sequence<=session['last_seq']:
                if event.cumulative_tip_count>session['last_count']:
                    raise ValueError("Out-of-order packet claims an uncommitted counter")
                return {"accepted":False,"duplicate":True,"reason":"duplicate_or_out_of_order","delta_tips":0}
            if session and (event.cumulative_tip_count<session['last_count'] or event.device_uptime_ms<session['uptime'] or event.boot_start_tip_count!=session['boot_start']):
                raise ValueError("Counter, uptime or boot baseline regressed; manual reconciliation required")
            if not session and latest and event.cumulative_tip_count<latest['last_count']:
                raise ValueError("Lifetime counter reset across reboot; manual reconciliation required")
            if not session and latest and event.boot_start_tip_count<latest['last_count']:
                raise ValueError("Reboot baseline regressed below committed counter")
            if latest and now<datetime.fromisoformat(latest['received']):raise ValueError('Receive clock regressed; reconciliation required')
            baseline=session['last_count'] if session else latest['last_count'] if latest else event.boot_start_tip_count
            delta=event.cumulative_tip_count-baseline
            origin=datetime.fromisoformat(session['boot_origin']) if session else now-timedelta(milliseconds=event.device_uptime_ms)
            previous=datetime.fromisoformat(session['received']) if session else now-timedelta(milliseconds=event.device_uptime_ms-event.interval_start_uptime_ms)
            last_tip=origin+timedelta(milliseconds=event.last_tip_uptime_ms) if event.last_tip_uptime_ms is not None else None
            if last_tip and last_tip>now+timedelta(seconds=2):
                raise ValueError("Device timing places a tip in the future")
            calibration_changed=bool(prior_event and (not math.isclose(prior_event['mm_per_tip'],calibrated_mm,rel_tol=1e-5) or json.loads(prior_event['payload']).get('calibration_version','legacy-unversioned')!=event.calibration_version))
            gap=calibration_changed or not session and event.device_uptime_ms>30000 or session is not None and (now-previous).total_seconds()>30
            # Counts recovered across an outage/reboot remain visible, but are not invented hourly observations.
            allocated=hour_start(now).isoformat() if delta and not gap and session and hour_start(previous)==hour_start(now) else None
            if delta and not session and not latest and event.device_uptime_ms<=30000 and hour_start(previous)==hour_start(now):
                allocated=hour_start(now).isoformat()
            if gap or (delta and allocated is None):
                db.execute("INSERT INTO gaps VALUES(?,?,?,?,?)",(*identity[:2],previous.isoformat(),now.isoformat(),"outage/reboot/cross-hour timing uncertainty"))
            if latest and not session:
                db.execute("INSERT INTO gaps VALUES(?,?,?,?,?)",(*identity[:2],latest['received'],now.isoformat(),"boot transition; continuous hourly coverage not established"))
            db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",(*identity,event.boot_start_tip_count,event.cumulative_tip_count,event.packet_sequence,event.device_uptime_ms,now.isoformat(),origin.isoformat()))
            cursor=db.execute("INSERT INTO events(station,source,boot,sequence,count,delta,mm,mm_per_tip,received,last_tip,allocated_hour,interval_start,interval_end,recovered,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*identity,event.packet_sequence,event.cumulative_tip_count,delta,delta*calibrated_mm,calibrated_mm,now.isoformat(),last_tip.isoformat() if last_tip else None,allocated,previous.isoformat(),now.isoformat(),int(bool(delta and allocated is None)),event.model_dump_json()))
            if provenance:
                db.execute("INSERT INTO ingress_provenance VALUES(?,?,?,?,?,?,?)", (cursor.lastrowid,
                    *(provenance[k] for k in ("credential_id","ingress_transport","ingress_identity","source_class","stream","registry_version"))))
            from app.services.rain_rollups import summarize
            committed=db.execute('SELECT * FROM events WHERE id=?',(cursor.lastrowid,)).fetchone()
            summarize(db,committed,provenance)
            return {"accepted":True,"duplicate":False,"event_id":cursor.lastrowid,"delta_tips":delta,"rainfall_increment_mm":delta*calibrated_mm,
                    "received_at":now.isoformat(),"allocation":allocated,"recovered":bool(delta and allocated is None)}

    def snapshot(self,station: str,source: str,*,now: datetime|None=None,since_id: int=0,anchor_at: datetime|None=None) -> dict:
        from app.services.rain_rollups import snapshot
        return snapshot(self,station,source,now=(now or datetime.now(UTC)).astimezone(UTC),since_id=since_id,anchor_at=anchor_at)
