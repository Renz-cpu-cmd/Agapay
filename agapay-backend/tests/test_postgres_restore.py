"""Opt-in real PostgreSQL restore test. Never selects a deployment database.

Set AGAPAY_TEST_POSTGRES_URL to a NEW EMPTY loopback database named agapay_test_*.
This test creates the schema and leaves the restored database for inspection.
"""
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
import pytest
from app.migrations import upgrade, require_current
from app.transfer_database import transfer


def test_real_postgresql_empty_restore_and_repeat_protection(tmp_path):
    url=os.environ.get('AGAPAY_TEST_POSTGRES_URL')
    if not url:
        pytest.skip('No disposable PostgreSQL runtime configured; real-engine restore acceptance pending')
    parsed=make_url(url)
    if parsed.host not in ('127.0.0.1','localhost','::1') or not (parsed.database or '').startswith('agapay_test_'):
        pytest.fail('PostgreSQL test target must be an explicit loopback agapay_test_* database')
    source=create_engine('sqlite:///'+str(tmp_path/'restore-source.db'));target=create_engine(url)
    try:
        if inspect(target).get_table_names():
            pytest.fail('Use a NEW EMPTY disposable database for this test')
        upgrade(source)
        with source.begin() as db:
            db.exec_driver_sql("INSERT INTO stations (station_id,station_name,sensor_height_cm,threshold_advisory_cm,threshold_warning_cm,threshold_evacuate_cm,status,created_at) VALUES ('PG_RESTORE','Synthetic restore fixture',120,60,85,100,'maintenance','2026-10-22')")
        assert transfer(source,target)['stations']==1
        require_current(target)
        with pytest.raises(RuntimeError,match='contains application data'):transfer(source,target)
    finally:
        source.dispose();target.dispose()
