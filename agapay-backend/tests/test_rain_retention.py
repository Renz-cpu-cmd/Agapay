"""F32 differential products, transaction rollback, archival and portable recovery."""
from datetime import timedelta
import json,sqlite3
import pytest
from app.services.rain_gauge_service import RainGaugeStore
from app.services.rain_rollups import upgrade
from app.services.rain_archive import archive_batch,backup,verify,verify_bundle
from rain_reference import RawReference
from test_rain_gauge import event,NOW


def assert_products(store,now):
    old=RawReference(store.path).snapshot('RAIN_TEST','physical_rain_gauge',now=now,anchor_at=now-timedelta(minutes=10))
    new=store.snapshot('RAIN_TEST','physical_rain_gauge',now=now,anchor_at=now-timedelta(minutes=10))
    for name in ('completed_hours','current_hour_product','accepted_tip_count','unallocated_recovered_mm','last_tip_at','latest_tip_event_id','calibration_version','source_trusted'):
        def normalized(value):
            if isinstance(value,float):return round(value,8)
            if isinstance(value,dict):return {k:normalized(v) for k,v in value.items()}
            if isinstance(value,list):return [normalized(v) for v in value]
            return value
        assert normalized(new[name])==normalized(old[name]),name
    for name in ('accepted_rainfall_mm','session_rainfall_mm','rainfall_after_anchor_mm'):assert new[name]==pytest.approx(old[name]),name


def test_rollups_reproduce_raw_rain_coverage_gaps_calibrations_and_sources(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.db');count=0
    for seq in range(151):
        seconds=seq*30+(120 if seq>=125 else 0)
        if seq%11==0:count+=1
        item=event(count,seq+1,seconds*1000)
        if seq>=135:item=item.model_copy(update={'schema_version':2,'calibration_version':'a'*64})
        store.ingest(item,.7,now=NOW+timedelta(seconds=seconds))
    store.ingest(event(5,1,1000,source='simulated_rain_gauge'),.7,now=NOW+timedelta(seconds=seconds))
    assert_products(store,NOW+timedelta(seconds=seconds))
    assert_products(store,NOW+timedelta(days=2))


def test_initialization_is_once_and_readers_never_run_schema_or_wal_setup(tmp_path,monkeypatch):
    path=tmp_path/'rain.db';calls=[];original=RainGaugeStore._initialize
    def initialize(self,new):calls.append(new);return original(self,new)
    monkeypatch.setattr(RainGaugeStore,'_initialize',initialize)
    for _ in range(12):RainGaugeStore(path).snapshot('RAIN_TEST','physical_rain_gauge')
    for _ in range(12):RainGaugeStore(path,read_only=True).snapshot('RAIN_TEST','physical_rain_gauge')
    assert calls==[True]
    missing=tmp_path/'not-created.db'
    assert RainGaugeStore(missing,read_only=True).snapshot('RAIN_TEST','physical_rain_gauge')['status']=='no_data'
    assert not missing.exists()


def test_snapshot_reads_one_committed_wal_cut_during_ingestion(tmp_path,monkeypatch):
    from contextlib import contextmanager
    writer=RainGaugeStore(tmp_path/'rain.db');writer.ingest(event(),.7,now=NOW)
    reader=RainGaugeStore(writer.path,read_only=True);connect=reader.connect;interleaved=[]
    @contextmanager
    def concurrent_read():
        with connect() as db:
            def trace(sql):
                if sql.startswith('SELECT * FROM sessions') and not interleaved:
                    interleaved.append(True)
                    writer.ingest(event(1,2,1000),.7,now=NOW+timedelta(seconds=1))
            db.set_trace_callback(trace);yield db
    monkeypatch.setattr(reader,'connect',concurrent_read)
    snapshot=reader.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(seconds=1))
    assert interleaved and snapshot['accepted_tip_count']==snapshot['cumulative_tip_count']==0
    assert snapshot['incomplete_hour_mm']==0
    assert writer.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(seconds=1))['accepted_tip_count']==1


def test_rollup_failure_rolls_back_raw_counter_and_ackable_payload(tmp_path,monkeypatch):
    from app.services import rain_rollups
    store=RainGaugeStore(tmp_path/'rain.db');store.ingest(event(),.7,now=NOW)
    original=rain_rollups.summarize
    def broken(*args):original(*args);raise RuntimeError('Synthetic crash before journal commit')
    monkeypatch.setattr(rain_rollups,'summarize',broken)
    with pytest.raises(RuntimeError):store.ingest(event(1,2,1000),.7,now=NOW+timedelta(seconds=1))
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM events').fetchone()[0]==1
        assert db.execute('SELECT last_count FROM sessions').fetchone()[0]==0
        assert db.execute('SELECT tips FROM rain_stream_totals').fetchone()[0]==0
    monkeypatch.setattr(rain_rollups,'summarize',original)
    assert RainGaugeStore(store.path).ingest(event(1,2,1000),.7,now=NOW+timedelta(seconds=1))['delta_tips']==1


def test_retired_boot_ack_requires_an_exact_committed_packet(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.db');committed=event()
    store.ingest(committed,.7,now=NOW)
    store.ingest(event(0,1,0,boot='BOOT_B'),.7,now=NOW+timedelta(seconds=1))
    assert store.ingest(committed,.7,now=NOW+timedelta(seconds=2))['duplicate']
    with pytest.raises(ValueError,match='no acknowledgement'):
        store.ingest(event(9,2,1000),.7,now=NOW+timedelta(seconds=2))
    assert store.snapshot('RAIN_TEST','physical_rain_gauge',now=NOW+timedelta(seconds=2))['accepted_tip_count']==0


def test_existing_raw_journal_requires_explicit_preserving_upgrade(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.db');store.ingest(event(),.7,now=NOW);store.ingest(event(2,2,1000),.7,now=NOW+timedelta(seconds=1))
    with store.connect() as db:
        original=[tuple(r) for r in db.execute('SELECT * FROM events')]
        for table in ('rain_archive_segments','rain_archives','rain_hour_versions','rain_hour_totals','rain_session_totals','rain_stream_totals'):db.execute('DROP TABLE '+table)
        db.execute('PRAGMA user_version=0')
    with pytest.raises(ValueError,match='migration required'):RainGaugeStore(store.path,read_only=True).snapshot('RAIN_TEST','physical_rain_gauge')
    with store.connect() as db:
        upgrade(db)
        assert [tuple(r) for r in db.execute('SELECT * FROM events')]==original
    assert_products(store,NOW+timedelta(seconds=2))


def history(store):
    packets=[]
    for seq in range(91):
        seconds=seq*3600;item=event(seq,seq+1,seconds*1000);packets.append(item)
        store.ingest(item,.7,now=NOW+timedelta(seconds=seconds))
    return packets,NOW+timedelta(hours=91)


def test_archive_restore_preserves_lifetime_missingness_and_exact_lost_ack_retry(tmp_path):
    store=RainGaugeStore(tmp_path/'rain.db',raw_retention_days=2);packets,now=history(store)
    original=store.snapshot('RAIN_TEST','physical_rain_gauge',now=now)
    result=archive_batch(store,tmp_path/'archives',now=now,limit=100)
    assert result['events']>0 and verify(store)['integrity']=='ok'
    restored=store.snapshot('RAIN_TEST','physical_rain_gauge',now=now)
    for name in ('accepted_tip_count','accepted_rainfall_mm','completed_hours','last_tip_at','latest_tip_event_id','unallocated_recovered_mm'):assert restored[name]==original[name]
    assert store.ingest(packets[1],.7,now=now)['duplicate']
    with pytest.raises(ValueError,match='Conflicting'):store.ingest(packets[1].model_copy(update={'firmware_version':'conflict'}),.7,now=now)
    assert store.snapshot('RAIN_TEST','physical_rain_gauge',now=now,anchor_at=NOW)['rainfall_after_anchor_mm'] is None
    bundle=tmp_path/'portable';assert backup(store,bundle)['integrity']=='ok';assert verify_bundle(bundle)['integrity']=='ok'
    target=RainGaugeStore(bundle/'journal.sqlite3',read_only=False,raw_retention_days=2)
    assert target.ingest(packets[-1],.7,now=now)['duplicate']
    assert target.ingest(packets[1],.7,now=now)['duplicate']
    snapshot=target.snapshot('RAIN_TEST','physical_rain_gauge',now=now)
    assert snapshot['accepted_tip_count']==original['accepted_tip_count']
    with pytest.raises(FileExistsError):backup(store,bundle)
    archived=next((tmp_path/'archives').glob('*.sqlite3'))
    with archived.open('r+b') as file:file.seek(50);file.write(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):verify(store)
    with pytest.raises(ValueError,match='integrity'):store.ingest(packets[1],.7,now=now)


def test_explicit_maintenance_cli_uses_configured_budgets_and_create_only_restore(tmp_path,monkeypatch):
    import sys
    from app.config import Settings
    from app import rain_journal,config
    store=RainGaugeStore(tmp_path/'rain.db',raw_retention_days=2);history(store)
    settings=Settings(rain_raw_retention_days=2,rain_archive_batch=100,rain_archive_directory=str(tmp_path/'archives'))
    monkeypatch.setattr(config,'get_settings',lambda:settings)
    def run(action,path,*extra):
        monkeypatch.setattr(sys,'argv',['rain_journal',action,'--path',str(path),*map(str,extra)])
        rain_journal.main()
    run('upgrade',store.path);run('archive',store.path)
    assert list((tmp_path/'archives').glob('*.sqlite3'))
    run('verify',store.path)
    run('backup',store.path,'--destination',tmp_path/'backup')
    run('verify-backup',tmp_path/'backup')
    run('restore',tmp_path/'backup','--destination',tmp_path/'restored')
    assert (tmp_path/'restored/journal.sqlite3').is_file()
    with pytest.raises(ValueError,match='must be new'):run('restore',tmp_path/'backup','--destination',tmp_path/'restored')


@pytest.mark.parametrize('stage',['published','before_commit'])
def test_archive_crash_keeps_committed_hot_rows_and_leaves_only_unreferenced_file(tmp_path,stage):
    store=RainGaugeStore(tmp_path/'rain.db',raw_retention_days=2);packets,now=history(store)
    with store.connect() as db:before=[tuple(r) for r in db.execute('SELECT * FROM events')]
    def crash(at):
        if at==stage:raise RuntimeError('Synthetic maintenance crash')
    with pytest.raises(RuntimeError):archive_batch(store,tmp_path/'archives',now=now,fault=crash)
    with store.connect() as db:
        assert [tuple(r) for r in db.execute('SELECT * FROM events')]==before
        assert db.execute('SELECT COUNT(*) FROM rain_archives').fetchone()[0]==0
    assert len(list((tmp_path/'archives').glob('*.sqlite3')))==1
    assert RainGaugeStore(store.path).ingest(packets[-1],.7,now=now)['duplicate']
