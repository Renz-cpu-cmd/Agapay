"""R2 pool acceptance on real PostgreSQL (suite mode only; synthetic data).

Connections return to the pool after errors; exhaustion is a clean 503 with nothing written;
the notification fence never claims when it cannot get a connection; after a server restart
the pool reconnects without 500s. AGAPAY_TEST_PG_BIN + AGAPAY_TEST_PG_DATA enable the restart.
"""
import os
import subprocess

import pytest
from sqlalchemy import select, text

from app.database import SessionLocal, engine
from app.models import NotificationDelivery
from test_accounts import reset_accounts, staff  # noqa: F401
from test_alerts import payload, send, station  # noqa: F401
from test_notifications import register, resident
from station_support import device_headers

pytestmark = pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='PostgreSQL pool behaviour')
PG_BIN = os.environ.get('AGAPAY_TEST_PG_BIN')
PG_DATA = os.environ.get('AGAPAY_TEST_PG_DATA')


def idle_in_transaction():
    with engine.connect() as c:
        return c.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                              "AND state LIKE 'idle in transaction%' AND pid <> pg_backend_pid()")).scalar()


def test_connections_return_to_the_pool_after_errors(client, station):  # noqa: F811
    officer = staff(client, 'officer')
    baseline = engine.pool.checkedout()
    send(client, station, 1, 30)
    outcomes = [
        client.post('/api/telemetry', json=payload(station, 1, 30), headers=device_headers(station)).status_code,  # duplicate
        client.post('/api/telemetry', json=payload(station, 2, 30), headers={'Authorization': 'Bearer wrong'}).status_code,
        client.post('/api/telemetry', json={'station_id': station}, headers=device_headers(station)).status_code,   # invalid
        client.get('/api/monitoring/stations?station_id=NOPE', headers=officer).status_code,
        client.get('/api/notification-deliveries/999999', headers=officer).status_code,
        client.get('/api/monitoring/stations', headers={'Authorization': 'Bearer expired'}).status_code,
    ]
    assert all(code >= 400 or code == 200 for code in outcomes) and 500 not in outcomes, outcomes
    assert engine.pool.checkedout() == baseline, 'every request returned its connection'
    assert idle_in_transaction() == 0, 'no connection left idle inside a transaction'


def test_pool_exhaustion_is_a_clean_503_and_nothing_is_written(client, station, monkeypatch):  # noqa: F811
    body, headers = payload(station, 1, 105), device_headers(station)  # built before exhausting the pool
    monkeypatch.setattr(engine.pool, '_timeout', 0.5)
    held = []
    try:
        while engine.pool.checkedout() < engine.pool.size() + engine.pool._max_overflow:
            held.append(engine.connect())
            held[-1].execute(text('SELECT 1'))
        response = client.post('/api/telemetry', json=body, headers=headers)
        assert response.status_code == 503 and response.headers['Retry-After'] == '2'
    finally:
        for connection in held:
            connection.close()
    with SessionLocal() as db:
        from app.models import Telemetry
        assert db.scalar(select(Telemetry.id).where(Telemetry.station_id == station)) is None, 'nothing written'
    assert send(client, station, 1, 105)['sequence_no'] == 1, 'service recovers when connections return'


def test_notification_fence_makes_no_claim_without_a_connection(client, station, monkeypatch):  # noqa: F811
    from app.services.notification_service import process_pending
    register(client, resident(client))
    send(client, station, 1, 105)
    monkeypatch.setattr(engine.pool, '_timeout', 0.5)
    held = []
    calls = []

    class Provider:
        mode = 'test'

        def send(self, target, message, *, delivery_key):
            calls.append(delivery_key)
    try:
        while engine.pool.checkedout() < engine.pool.size() + engine.pool._max_overflow:
            held.append(engine.connect())
            held[-1].execute(text('SELECT 1'))
        with pytest.raises(Exception):
            process_pending(Provider())
    finally:
        for connection in held:
            connection.close()
    with SessionLocal() as db:
        from app.recovery_models import DeliveryGeneration
        assert [d.state for d in db.scalars(select(NotificationDelivery))] == ['PENDING']
        assert db.scalar(select(DeliveryGeneration.claim_seq).where(DeliveryGeneration.state == 'ACTIVE')) == 0
    assert calls == [] and process_pending(Provider()) == 1 and len(calls) == 1


@pytest.mark.skipif(not (PG_BIN and PG_DATA), reason='Server restart drill not configured')
def test_pool_reconnects_after_a_server_restart(client, station):  # noqa: F811
    officer = staff(client, 'officer')
    send(client, station, 1, 30)
    assert client.get('/api/monitoring/stations', headers=officer).status_code == 200
    subprocess.run([os.path.join(PG_BIN, 'pg_ctl' + ('.exe' if os.name == 'nt' else '')), '-D', PG_DATA, '-m', 'fast', '-w', 'restart',
                    '-l', os.path.join(PG_DATA, '..', 'postgres-restart.log')],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=120)
    # Pooled connections are now dead; pre-ping replaces them transparently.
    assert send(client, station, 2, 30)['sequence_no'] == 2
    assert client.get('/api/monitoring/stations', headers=officer).status_code == 200
    assert engine.pool.checkedout() == 0 and idle_in_transaction() == 0
