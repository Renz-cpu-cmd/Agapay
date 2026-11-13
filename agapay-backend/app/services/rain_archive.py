"""Explicit bounded archival. Publish/verify immutable files before deleting raw rows."""
from collections import OrderedDict
from contextlib import closing
from datetime import datetime,timedelta,timezone
import hashlib,json,math,os,sqlite3,shutil
from pathlib import Path
from uuid import uuid4
from app.services.rain_rollups import require_current

_verified=OrderedDict()


def checksum(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        while part:=source.read(1024*1024):digest.update(part)
    return digest.hexdigest()


def resolve_archive(db,path):
    value=Path(path)
    return value if value.is_absolute() else Path(db.execute('PRAGMA database_list').fetchone()[2]).parent/value


def checked_archive(path,expected):
    path=Path(path);stat=path.stat();key=(str(path.resolve()),stat.st_ino,stat.st_size,stat.st_mtime_ns,expected)
    if key not in _verified:
        if checksum(path)!=expected:raise ValueError('Rain archive integrity failure; no acknowledgement')
        _verified[key]=True
        while len(_verified)>32:_verified.popitem(last=False)
    return path


def archived_payload(db,event):
    match=db.execute('''SELECT a.path,a.sha256 FROM rain_archive_segments s JOIN rain_archives a ON a.id=s.archive_id
      WHERE s.station=? AND s.source=? AND s.boot=? AND s.first_sequence<=? AND s.last_sequence>=?''',
      (event.station_id,event.data_source,event.boot_id,event.packet_sequence,event.packet_sequence)).fetchall()
    for item in match:
        path=checked_archive(resolve_archive(db,item['path']),item['sha256'])
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as archive:
            found=archive.execute('SELECT payload FROM events WHERE station=? AND source=? AND boot=? AND sequence=?',
                (event.station_id,event.data_source,event.boot_id,event.packet_sequence)).fetchone()
            if found:return found[0]
    return None


def archive_batch(store,directory,*,now=None,limit=5000,fault=None):
    if store.read_only:raise ValueError('Archival requires an explicit writable maintenance store')
    if not 1<=limit<=10000:raise ValueError('Archive batch must be 1..10000')
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc);cutoff=(now-timedelta(days=store.raw_retention_days)).isoformat()
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    with store.lock,store.connect() as db:
        require_current(db);db.execute('BEGIN IMMEDIATE')
        # Keep each boot's last committed packet online, including lost-ACK recovery.
        rows=db.execute('''SELECT e.* FROM events e WHERE e.received<? AND NOT EXISTS(
          SELECT 1 FROM sessions s WHERE s.station=e.station AND s.source=e.source AND s.boot=e.boot AND s.last_seq=e.sequence)
          ORDER BY e.received,e.id LIMIT ?''',(cutoff,limit)).fetchall()
        gaps=db.execute('SELECT rowid AS gap_id,* FROM gaps WHERE end<? ORDER BY end LIMIT ?',(cutoff,limit)).fetchall()
        if not rows and not gaps:return {'events':0,'gaps':0,'archive_id':None}
        identity=str(uuid4());target=directory/f'rain-{identity}.sqlite3';temporary=target.with_suffix('.partial')
        with closing(sqlite3.connect(temporary)) as archive:
            archive.execute('PRAGMA synchronous=FULL')
            for table in ('events','ingress_provenance','gaps'):
                archive.execute(db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()[0])
            for row in rows:
                archive.execute('INSERT INTO events VALUES('+','.join('?' for _ in row)+')',tuple(row))
                provenance=db.execute('SELECT * FROM ingress_provenance WHERE event_id=?',(row['id'],)).fetchone()
                if provenance:archive.execute('INSERT INTO ingress_provenance VALUES(?,?,?,?,?,?,?)',tuple(provenance))
            archive.executemany('INSERT INTO gaps VALUES(?,?,?,?,?)',[tuple(row)[1:] for row in gaps]);archive.commit()
            if archive.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or archive.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Archive verification failed')
            reread=archive.execute('SELECT * FROM events ORDER BY received,id').fetchall()
            if reread!=[tuple(row) for row in rows]:raise ValueError('Archive content differs from selected committed rows')
        with temporary.open('r+b') as source:os.fsync(source.fileno())
        expected=checksum(temporary);temporary.rename(target)
        # Directory fsync where supported; file fsync above is mandatory on Windows.
        if os.name!='nt':
            descriptor=os.open(directory,os.O_RDONLY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
        if fault:fault('published')
        db.execute('INSERT INTO rain_archives VALUES(?,?,?,?,?,?)',(identity,str(target),expected,len(rows),len(gaps),now.isoformat()))
        groups={}
        for row in rows:groups.setdefault((row['station'],row['source'],row['boot']),[]).append(row)
        for key,items in groups.items():
            db.execute('INSERT INTO rain_archive_segments VALUES(?,?,?,?,?,?,?,?)',(*key,min(r['sequence'] for r in items),max(r['sequence'] for r in items),min(r['received'] for r in items),max(r['received'] for r in items),identity))
            db.execute('UPDATE rain_stream_totals SET archived_until=MAX(COALESCE(archived_until,?),?) WHERE station=? AND source=?',
                (max(r['received'] for r in items),max(r['received'] for r in items),*key[:2]))
        db.execute('CREATE TEMP TABLE archive_event_ids(id INTEGER PRIMARY KEY)')
        db.executemany('INSERT INTO archive_event_ids VALUES(?)',[(r['id'],) for r in rows])
        db.execute('DELETE FROM ingress_provenance WHERE event_id IN (SELECT id FROM archive_event_ids)')
        db.execute('DELETE FROM events WHERE id IN (SELECT id FROM archive_event_ids)')
        db.executemany('DELETE FROM gaps WHERE rowid=?',[(r['gap_id'],) for r in gaps])
        if fault:fault('before_commit')
        db.commit()
    return {'events':len(rows),'gaps':len(gaps),'archive_id':identity,'sha256':expected}


def verify(store):
    """Slow deliberate integrity operation, never a viewer query."""
    totals={};archives=0
    def accumulate(rows):
        for station,source,tips,mm in rows:
            value=totals.setdefault((station,source),[0,0.]);value[0]+=tips;value[1]+=mm
    with store.connect() as db:
        db.execute('BEGIN')
        require_current(db)
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Journal integrity failure')
        accumulate(db.execute('SELECT station,source,SUM(delta),SUM(mm) FROM events GROUP BY station,source'))
        for record in db.execute('SELECT * FROM rain_archives'):
            path=resolve_archive(db,record['path'])
            if checksum(path)!=record['sha256']:raise ValueError('Archive checksum mismatch')
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as archive:
                if archive.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or archive.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Archive integrity failure')
                if archive.execute('SELECT COUNT(*) FROM events').fetchone()[0]!=record['events']:raise ValueError('Archive count mismatch')
                if archive.execute('SELECT COUNT(*) FROM gaps').fetchone()[0]!=record['gaps']:raise ValueError('Archive gap count mismatch')
                accumulate(archive.execute('SELECT station,source,SUM(delta),SUM(mm) FROM events GROUP BY station,source'))
            archives+=1
        for row in db.execute('SELECT * FROM rain_stream_totals'):
            tips,mm=totals.get((row['station'],row['source']),[0,0.])
            if tips!=row['tips'] or not math.isclose(mm,row['mm'],rel_tol=1e-9,abs_tol=1e-6):raise ValueError('Journal/archive lifetime totals disagree')
    return {'integrity':'ok','archives':archives,'streams':len(totals)}


def backup(store,destination):
    """Create-only portable bundle. SQLite backup supplies a consistent catalog cut."""
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=False)
    journal=destination/'journal.sqlite3';archive_dir=destination/'archives';archive_dir.mkdir()
    with store.connect() as source,closing(sqlite3.connect(journal)) as copy:
        source.backup(copy);copy.row_factory=sqlite3.Row
        for item in copy.execute('SELECT * FROM rain_archives').fetchall():
            path=resolve_archive(source,item['path']);target=archive_dir/path.name
            shutil.copyfile(path,target)
            if checksum(target)!=item['sha256']:raise ValueError('Backup archive checksum mismatch')
            copy.execute('UPDATE rain_archives SET path=? WHERE id=?',('archives/'+path.name,item['id']))
        copy.commit()
    from app.services.rain_gauge_service import RainGaugeStore
    result=verify(RainGaugeStore(journal,read_only=True,raw_retention_days=store.raw_retention_days))
    files=[journal,*sorted(archive_dir.iterdir())]
    for path in files:
        with path.open('r+b') as handle:os.fsync(handle.fileno())
    manifest={'format':1,'raw_retention_days':store.raw_retention_days,'files':{str(path.relative_to(destination).as_posix()):checksum(path) for path in files},'verification':result}
    # Publish the manifest last. An interrupted bundle has no completion marker.
    with (destination/'manifest.json').open('w',encoding='utf-8') as handle:
        handle.write(json.dumps(manifest,indent=2)+'\n');handle.flush();os.fsync(handle.fileno())
    return result


def verify_bundle(directory):
    directory=Path(directory).resolve();manifest=json.loads((directory/'manifest.json').read_text())
    if manifest.get('format')!=1 or 'journal.sqlite3' not in manifest.get('files',{}):raise ValueError('Incomplete backup manifest')
    for name,expected in manifest['files'].items():
        path=(directory/name).resolve()
        if not path.is_relative_to(directory) or checksum(path)!=expected:raise ValueError('Backup path/checksum mismatch')
    with closing(sqlite3.connect((directory/'journal.sqlite3').as_uri()+'?mode=ro',uri=True)) as journal:
        for (name,) in journal.execute('SELECT path FROM rain_archives'):
            path=(directory/name).resolve()
            if Path(name).is_absolute() or not path.is_relative_to(directory) or path.relative_to(directory).as_posix() not in manifest['files']:
                raise ValueError('Archive catalog must reference checksummed files inside the backup bundle')
    from app.services.rain_gauge_service import RainGaugeStore
    return verify(RainGaugeStore(directory/'journal.sqlite3',read_only=True,raw_retention_days=manifest['raw_retention_days']))
