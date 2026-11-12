"""F29: no serving-time schema mutation or seeding, copy preservation, fail closed."""
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from app.migrations import upgrade, require_current, LEDGER, migration_lock, REVISIONS
from app.verify_upgrade import verify


def test_fresh_explicit_upgrade_is_empty_idempotent_and_versioned(tmp_path):
    bind=create_engine('sqlite:///'+str(tmp_path/'fresh.db'))
    with pytest.raises(RuntimeError,match='migration required'):require_current(bind)
    assert upgrade(bind)==list(REVISIONS)
    assert upgrade(bind)==[]
    require_current(bind)
    with bind.connect() as db:
        for table in ('users','stations','telemetry','alerts','sos_requests','notification_events','notification_deliveries'):
            assert db.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()==0
    bind.dispose()


@pytest.mark.parametrize('change',[
    "UPDATE schema_migrations SET checksum='invalid'",
    "UPDATE schema_migrations SET revision='unknown-future' WHERE revision='0002_workflow_runtime'",
    'DROP TABLE notification_events',
    'DROP INDEX ix_telemetry_station_measured_id',
])
def test_readiness_rejects_version_checksum_table_or_index_drift(tmp_path,change):
    bind=create_engine('sqlite:///'+str(tmp_path/'drift.db'));upgrade(bind)
    with bind.begin() as connection:connection.execute(text(change))
    with pytest.raises(RuntimeError):require_current(bind)
    bind.dispose()


def test_serving_an_empty_database_does_not_create_or_seed(tmp_path,monkeypatch):
    import app.main as module
    bind=create_engine('sqlite:///'+str(tmp_path/'empty.db'))
    monkeypatch.setattr(module,'engine',bind)
    with pytest.raises(RuntimeError,match='migration required'):
        with TestClient(module.app):pass
    assert inspect(bind).get_table_names()==[]
    bind.dispose()


def test_copy_upgrade_preserves_data_and_cannot_replace_source(tmp_path):
    source=tmp_path/'original.db';destination=tmp_path/'copy.db'
    bind=create_engine('sqlite:///'+str(source));upgrade(bind)
    with bind.begin() as connection:
        connection.exec_driver_sql("INSERT INTO stations (station_id,station_name,sensor_height_cm,threshold_advisory_cm,threshold_warning_cm,threshold_evacuate_cm,status,created_at) VALUES ('COPY_ONLY','Synthetic preservation fixture',120,60,85,100,'maintenance','2026-10-22')")
        LEDGER.drop(connection)
    bind.dispose();before=source.read_bytes()
    assert verify(source,destination)['stations']==1
    assert source.read_bytes()==before
    with pytest.raises(ValueError):verify(source,source)
    with pytest.raises(ValueError):verify(source,destination)


def test_offline_migration_lock_rejects_a_second_owner(tmp_path):
    bind=create_engine('sqlite:///'+str(tmp_path/'lock.db'))
    with migration_lock(bind):
        with pytest.raises(RuntimeError,match='lock exists'):upgrade(bind)
    assert upgrade(bind)
    bind.dispose()


def test_unrecognized_partial_database_is_never_stamped(tmp_path):
    bind=create_engine('sqlite:///'+str(tmp_path/'partial.db'))
    with bind.begin() as connection:connection.exec_driver_sql('CREATE TABLE unexpected (id INTEGER)')
    with pytest.raises(RuntimeError,match='partial legacy'):upgrade(bind)
    assert not inspect(bind).has_table('schema_migrations')
    bind.dispose()


def test_serving_initialized_empty_schema_never_inserts_demo_rows(tmp_path,monkeypatch):
    import app.main as module
    bind=create_engine('sqlite:///'+str(tmp_path/'initialized.db'));upgrade(bind)
    monkeypatch.setattr(module,'engine',bind)
    with TestClient(module.app):
        with bind.connect() as db:
            assert db.scalar(text('SELECT COUNT(*) FROM stations'))==0
    bind.dispose()


def test_running_readiness_detects_a_migration_mismatch(client):
    from app.database import engine
    from app.migrations import checksum
    assert client.get('/ready').status_code==200
    try:
        with engine.begin() as connection:
            connection.execute(text("UPDATE schema_migrations SET checksum='stale-deployment' WHERE revision=:revision"),{'revision':REVISIONS[-1]})
        assert client.get('/ready').status_code==503
        assert client.get('/health').status_code==200
    finally:
        with engine.begin() as connection:
            connection.execute(text('UPDATE schema_migrations SET checksum=:checksum WHERE revision=:revision'),{'checksum':checksum(),'revision':REVISIONS[-1]})


def test_external_worker_health_is_shared_and_expires_without_http_inference(tmp_path):
    import json
    from datetime import timedelta
    from app.models import utc_now
    from app.services.broker_health import publish_shared,snapshot
    path=tmp_path/'ingestion.json'
    assert snapshot(True,shared_path=str(path))['state']=='unknown'
    publish_shared(path,'connected')
    observed=snapshot(True,shared_path=str(path))
    assert observed['state']=='connected' and observed['scope']=='dedicated ingestion worker heartbeat'
    assert snapshot(True,shared_path=str(path),now=observed['observed_at']+timedelta(seconds=16))['state']=='unknown'
    path.write_text(json.dumps({'state':'connected','observed_at':(utc_now()+timedelta(days=1)).isoformat()}))
    assert snapshot(True,shared_path=str(path))['state']=='unknown'


def test_restore_refuses_unreviewed_source_tables_instead_of_omitting_them(tmp_path):
    from types import SimpleNamespace
    from app.transfer_database import transfer
    source=create_engine('sqlite:///'+str(tmp_path/'custom-source.db'));upgrade(source)
    with source.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE custom_history (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql('INSERT INTO custom_history VALUES (1)')
    # Rejection must occur before any target connection/mutation is attempted.
    target=SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))
    with pytest.raises(RuntimeError,match='unreviewed tables'):transfer(source,target)
    with source.connect() as connection:
        assert connection.scalar(text('SELECT COUNT(*) FROM custom_history'))==1
    source.dispose()
