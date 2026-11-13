"""R2 pool/cache acceptance: monitoring read-model freshness semantics (SQLite and PostgreSQL).

Fresh data is served only before expiry. Refresh-ahead rebuilds once (single-flight) in the
last half-life. After expiry, a bounded last-known view is labelled degraded with original
timestamps; beyond that bound readers get 503 Retry-After, never stale data labelled current.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import threading

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import utc_now
from app.runtime_models import SharedReadModel
from app.services.read_models import cached

KEY = 'monitor:policy-test'


@pytest.fixture
def settings():
    value = get_settings().model_copy(update={'read_model_cache_enabled': True})
    yield value
    with SessionLocal() as db:
        db.query(SharedReadModel).filter(SharedReadModel.key.like('monitor:policy%')).delete(synchronize_session=False)
        db.commit()


def seed(*, age, ttl=2, lease_seconds=None, generation='g1'):
    checked = utc_now() - timedelta(seconds=age)
    with SessionLocal() as db:
        db.merge(SharedReadModel(key=KEY, generation=generation, checked_at=checked, expires_at=checked + timedelta(seconds=ttl),
                                 payload={'checked_at': checked.isoformat(), 'value': 'old', 'service_health': {'status': 'healthy', 'codes': []}},
                                 lease_token='other-producer' if lease_seconds else None,
                                 lease_until=utc_now() + timedelta(seconds=lease_seconds) if lease_seconds else None))
        db.commit()
    return checked


class Build:
    def __init__(self, delay=0.0, fail=False):
        self.calls, self.delay, self.fail, self.lock = 0, delay, fail, threading.Lock()

    def __call__(self):
        with self.lock:
            self.calls += 1
        if self.delay:
            threading.Event().wait(self.delay)
        if self.fail:
            raise RuntimeError('synthetic build failure')
        return {'checked_at': utc_now().isoformat(), 'value': 'new', 'service_health': {'status': 'healthy', 'codes': []}}


def read(settings, build, **kwargs):
    options = dict(ttl=2, settings=settings, wait_seconds=settings.read_model_wait_seconds,
                   stale_seconds=settings.read_model_stale_seconds, refresh_before_seconds=1)
    options.update(kwargs)
    return cached(KEY, 'g1', build, **options)


def test_fresh_value_is_served_without_rebuilding(settings):
    seed(age=0.2)
    build = Build()
    assert read(settings, build)['value'] == 'old' and build.calls == 0


def test_refresh_ahead_rebuilds_once_while_others_keep_the_unexpired_value(settings):
    seed(age=1.3, lease_seconds=30)  # another producer is already refreshing in the last half-life
    build = Build()
    value = read(settings, build)
    assert value['value'] == 'old' and build.calls == 0, 'still fresh: served as current, not stale'
    assert 'READ_MODEL_REBUILDING' not in value['service_health']['codes']
    seed(age=1.3)                    # no producer: exactly this reader refreshes ahead of expiry
    assert read(settings, build)['value'] == 'new' and build.calls == 1
    assert read(settings, build)['value'] == 'new' and build.calls == 1, 'the refreshed value is reused'


def test_expired_value_within_grace_is_labelled_last_known_with_original_timestamp(settings):
    checked = seed(age=2.5, lease_seconds=30)  # expired 0.5 s ago; grace is 2 s
    value = read(settings, Build())
    assert value['value'] == 'old' and value['checked_at'] == checked.isoformat()
    assert value['service_health']['status'] == 'degraded' and 'READ_MODEL_REBUILDING' in value['service_health']['codes']


def test_beyond_grace_readers_get_retry_after_never_unlabelled_stale_data(settings):
    seed(age=6, lease_seconds=30)  # expired 4 s ago, producer still busy
    with pytest.raises(HTTPException) as refused:
        read(settings.model_copy(update={'read_model_wait_seconds': 0.3}), Build())
    assert refused.value.status_code == 503 and refused.value.headers['Retry-After'] == '1'


def test_zero_grace_disables_last_known_views(settings):
    seed(age=2.5, lease_seconds=30)
    strict = settings.model_copy(update={'read_model_stale_seconds': 0, 'read_model_wait_seconds': 0.2})
    with pytest.raises(HTTPException):
        read(strict, Build())


def test_failed_build_releases_the_lease_for_the_next_reader(settings):
    seed(age=5)
    with pytest.raises(RuntimeError):
        read(settings, Build(fail=True))
    with SessionLocal() as db:
        row = db.get(SharedReadModel, KEY)
        assert row.lease_token is None and row.lease_until is None
    assert read(settings, Build())['value'] == 'new'


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='Concurrent single-flight needs independent server connections')
def test_concurrent_expired_readers_build_once_on_postgresql(settings):
    seed(age=5)
    build = Build(delay=0.6)
    with ThreadPoolExecutor(8) as pool:
        outcomes = list(pool.map(lambda _: _outcome(settings, build), range(8)))
    assert build.calls == 1, 'single-flight: one producer for eight concurrent readers'
    assert all(kind in ('new', 'retry') for kind in outcomes), outcomes
    assert outcomes.count('new') >= 1


def _outcome(settings, build):
    try:
        return read(settings, build)['value']
    except HTTPException as error:
        assert error.status_code == 503
        return 'retry'
