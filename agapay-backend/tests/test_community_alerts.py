from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Alert, AuthSession, Station, User, utc_now
from test_accounts import account, headers, reset_accounts, staff
from test_alerts import episodes, payload, send, station


ROOT = '/api/community-alerts'
EPISODE_FIELDS = {
    'id', 'station_id', 'station_name', 'barangay', 'municipality', 'status',
    'severity', 'source', 'trigger_depth_cm', 'latest_depth_cm', 'triggered_at',
    'last_transition_at', 'resolved_at',
}
TRANSITION_FIELDS = {'previous_severity', 'new_severity', 'water_depth_cm', 'transitioned_at'}


@pytest.fixture
def resident(client):
    return headers(client.post('/api/auth/register', json={**account(), 'barangay': 'Different area'}))


def page(client, access, station_id, route='', **params):
    response = client.get(ROOT + route, headers=access, params={'station_id': station_id, **params})
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    return response.json()


def detail(client, access, episode_id, **params):
    response = client.get(f'{ROOT}/{episode_id}', headers=access, params=params)
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    return response.json()


@pytest.mark.parametrize('role', ['resident', 'officer', 'admin'])
def test_roles_can_read_sanitized_community_contract(client, station, role):
    access = headers(client.post('/api/auth/register', json=account())) if role == 'resident' else staff(client, role)
    with SessionLocal() as db:
        s = db.scalar(select(Station).where(Station.station_id == station))
        s.station_name, s.barangay, s.municipality = 'Community test station', 'Other barangay', 'Urdaneta'
        db.commit()
    send(client, station, 1, 100)
    episode, = page(client, access, station)['items']
    assert set(episode) == EPISODE_FIELDS  # Excludes all telemetry IDs/sequences and account/actor data.
    assert episode['station_name'] == 'Community test station'
    assert (episode['barangay'], episode['municipality']) == ('Other barangay', 'Urdaneta')
    assert page(client, access, station, '/active')['items'] == [episode]
    result = detail(client, access, episode['id'])
    assert set(result) == EPISODE_FIELDS | {'transitions'}
    transition, = result['transitions']['items']
    assert set(transition) == TRANSITION_FIELDS
    assert (transition['previous_severity'], transition['new_severity']) == ('NORMAL', 'EVACUATE')
    assert transition['water_depth_cm'] == 100
    for field in ['triggered_at', 'last_transition_at']:
        assert episode[field].endswith('Z')
    assert transition['transitioned_at'].endswith('Z')
    for url in ['/api/alerts', '/api/alerts/active', f"/api/alerts/{episode['id']}", f"/api/alerts/{episode['id']}/transitions"]:
        assert client.get(url, headers=access).status_code == (403 if role == 'resident' else 200)


@pytest.mark.parametrize('mode', ['missing', 'invalid', 'expired', 'inactive', 'revoked'])
def test_every_read_requires_live_authenticated_account(client, station, resident, mode):
    send(client, station, 1, 90)
    access = resident
    if mode == 'missing':
        access = {}
    elif mode == 'invalid':
        access = {'Authorization': 'Bearer synthetic-invalid-session'}
    else:
        with SessionLocal() as db:
            if mode == 'expired':
                db.scalar(select(AuthSession)).expires_at = utc_now() - timedelta(seconds=1)
            elif mode == 'inactive':
                db.scalar(select(User)).is_active = False
            else:
                db.query(AuthSession).delete()
            db.commit()
    for route in ['', '/active', f'/{episodes(station)[0].id}', '/999999999']:
        response = client.get(ROOT + route, headers=access)
        assert response.status_code == 401
        assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('role', ['resident', 'officer', 'admin'])
def test_no_mutation_routes_for_any_role(client, station, role):
    access = headers(client.post('/api/auth/register', json=account())) if role == 'resident' else staff(client, role)
    send(client, station, 1, 100)
    before = page(client, access, station)
    for method in ['POST', 'PATCH', 'PUT', 'DELETE']:
        for route in ['', '/active', f"/{before['items'][0]['id']}"]:
            response = client.request(method, ROOT + route, headers=access, json={'status': 'RESOLVED', 'severity': 'NORMAL'})
            assert response.status_code == 405
            assert response.headers['cache-control'] == 'no-store'
    assert page(client, access, station) == before


@pytest.mark.parametrize('depth', [0, 59, None])
def test_normal_or_invalid_creates_no_community_alert(client, station, resident, depth):
    send(client, station, 1, depth)
    assert page(client, resident, station) == {'items': [], 'total': 0}
    assert page(client, resident, station, '/active') == {'items': [], 'total': 0}


@pytest.mark.parametrize('depth,severity', [(60, 'ADVISORY'), (85, 'WARNING'), (100, 'EVACUATE')])
def test_direct_valid_rises_appear_active(client, station, resident, depth, severity):
    send(client, station, 1, depth)
    episode, = page(client, resident, station, '/active')['items']
    assert episode['severity'] == severity and episode['status'] == 'ACTIVE'
    assert episode['trigger_depth_cm'] == episode['latest_depth_cm'] == depth
    assert episode['resolved_at'] is None and episode['source'] == 'sensor'
    assert episode['barangay'] is None and episode['municipality'] is None


def test_lifecycle_visibility_peak_history_invalid_and_second_episode(client, station, resident):
    episode_id = None
    for sequence, (depth, expected) in enumerate([(60, 'ADVISORY'), (85, 'WARNING'), (100, 'EVACUATE'), (90, 'WARNING')], 1):
        send(client, station, sequence, depth)
        item, = page(client, resident, station, '/active')['items']
        assert item['severity'] == expected and item['latest_depth_cm'] == depth
        episode_id = episode_id or item['id']
        assert item['id'] == episode_id
    before = detail(client, resident, episode_id)
    for sequence in [5, 6]:
        send(client, station, sequence, None)
        assert detail(client, resident, episode_id) == before
        assert page(client, resident, station, '/active')['items'] == [item]
    send(client, station, 7, 0)
    assert page(client, resident, station, '/active') == {'items': [], 'total': 0}
    resolved, = page(client, resident, station, status='RESOLVED')['items']
    assert resolved['status'] == 'RESOLVED' and resolved['severity'] == 'EVACUATE'
    assert resolved['trigger_depth_cm'] == 60 and resolved['latest_depth_cm'] == 0
    assert resolved['resolved_at'] == resolved['last_transition_at']
    assert resolved['resolved_at'].endswith('Z')
    timeline = detail(client, resident, episode_id)['transitions']
    assert timeline['total'] == 5
    assert [t['new_severity'] for t in timeline['items']] == ['ADVISORY', 'WARNING', 'EVACUATE', 'WARNING', 'NORMAL']
    assert [t['transitioned_at'] for t in timeline['items']] == sorted(t['transitioned_at'] for t in timeline['items'])
    assert all(set(t) == TRANSITION_FIELDS for t in timeline['items'])
    send(client, station, 8, 90)
    active, = page(client, resident, station, '/active')['items']
    assert active['id'] != episode_id and active['severity'] == 'WARNING'
    assert page(client, resident, station)['items'] == [active, resolved]
    assert page(client, resident, station, status='ACTIVE')['items'] == [active]
    assert page(client, resident, station, status='RESOLVED')['items'] == [resolved]
    # A retry, even with altered content, never changes the resident history.
    assert client.post('/api/telemetry', json=payload(station, 8, 0)).status_code == 409
    assert page(client, resident, station, '/active')['items'] == [active]


@pytest.mark.parametrize('station_status', ['active', 'inactive', 'maintenance'])
def test_no_implicit_geographic_or_station_status_suppression(client, station, resident, station_status):
    with SessionLocal() as db:
        s = db.scalar(select(Station).where(Station.station_id == station))
        s.status, s.barangay, s.firmware_version = station_status, 'Not the resident barangay', 'simulator-dev'
        db.commit()
    send(client, station, 1, 100)
    with SessionLocal() as db:
        db.scalar(select(Station).where(Station.station_id == station)).firmware_version = 'simulator-dev'
        db.commit()
    item, = page(client, resident, station, '/active')['items']
    assert item['severity'] == 'EVACUATE' and item['source'] == 'sensor'
    assert set(item) == EPISODE_FIELDS  # No invented device/simulator historical origin.
    # Default unfiltered feed also includes alerts outside the resident's area.
    assert item in client.get(ROOT + '/active?limit=100', headers=resident).json()['items']


def test_history_default_max_bounds_offset_and_tied_timestamp_ordering(client, station, resident):
    for sequence in range(1, 105):
        send(client, station, sequence, 90 if sequence % 2 else 0)
    with SessionLocal() as db:
        db.query(Alert).filter(Alert.station_id == station).update({'triggered_at': datetime(2026, 1, 1, tzinfo=timezone.utc)})
        db.commit()
    result = page(client, resident, station)
    assert result['total'] == 52 and len(result['items']) == 50
    expected = sorted((a.id for a in episodes(station)), reverse=True)
    assert [a['id'] for a in result['items']] == expected[:50]
    assert page(client, resident, station) == result
    tail = page(client, resident, station, offset=50, limit=2)
    assert tail['total'] == 52 and [a['id'] for a in tail['items']] == expected[50:]
    assert len(page(client, resident, station, limit=100)['items']) == 52
    assert page(client, resident, station, offset=52) == {'items': [], 'total': 52}
    assert page(client, resident, 'UNKNOWN_COMMUNITY_STATION') == {'items': [], 'total': 0}


def test_active_station_filter_and_pagination(client, station, resident):
    other = station + '_OTHER'
    with SessionLocal() as db:
        db.add(Station(station_id=other, station_name='Second community station'))
        db.commit()
    send(client, station, 1, 90)
    send(client, other, 1, 100)
    assert page(client, resident, station, '/active')['total'] == 1
    assert page(client, resident, other, '/active')['items'][0]['station_id'] == other
    assert page(client, resident, other, '/active', offset=1, limit=1) == {'items': [], 'total': 1}
    assert page(client, resident, other, status='RESOLVED') == {'items': [], 'total': 0}


def test_detail_timeline_is_bounded_and_keeps_ingestion_order(client, station, resident):
    for sequence in range(1, 53):
        send(client, station, sequence, 100 if sequence % 2 else 90)
    episode_id = episodes(station)[0].id
    first = detail(client, resident, episode_id)
    assert len(first['transitions']['items']) == 50 and first['transitions']['total'] == 52
    assert first['transitions']['items'][0]['previous_severity'] == 'NORMAL'
    assert first['transitions']['items'][0]['new_severity'] == 'EVACUATE'
    tail = detail(client, resident, episode_id, transition_limit=2, transition_offset=50)['transitions']
    assert tail['total'] == 52 and len(tail['items']) == 2
    assert [t['new_severity'] for t in tail['items']] == ['EVACUATE', 'WARNING']
    assert len(detail(client, resident, episode_id, transition_limit=100)['transitions']['items']) == 52
    assert detail(client, resident, episode_id, transition_offset=52)['transitions'] == {'items': [], 'total': 52}
    assert client.get(f'{ROOT}/999999999', headers=resident).status_code == 404


@pytest.mark.parametrize('query', ['limit=0', 'limit=101', 'offset=-1', 'limit=bad'])
def test_invalid_list_pagination(client, resident, query):
    for route in ['', '/active']:
        response = client.get(ROOT + route + '?' + query, headers=resident)
        assert response.status_code == 422 and response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('query', ['transition_limit=0', 'transition_limit=101', 'transition_offset=-1'])
def test_invalid_transition_pagination(client, station, resident, query):
    send(client, station, 1, 100)
    assert client.get(f'{ROOT}/{episodes(station)[0].id}?{query}', headers=resident).status_code == 422


def test_invalid_status_and_identifier(client, resident):
    assert client.get(ROOT + '?status=NORMAL', headers=resident).status_code == 422
    assert client.get(ROOT + '/not-an-id', headers=resident).status_code == 422
