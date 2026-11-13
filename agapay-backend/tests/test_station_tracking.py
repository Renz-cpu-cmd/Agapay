"""Migration 0010: operator-phone tracking of a portable station. Disposable SQLite."""
from datetime import datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models import Station, StationCredential, StationIdentity

from test_accounts import account, headers, reset_accounts, sign_in, staff  # noqa: F401
from test_alerts import payload
from test_station_security import commissioning, device, provision, token_headers  # noqa: F401


def now():
    return datetime.now(timezone.utc)


def resident(client, email='tracker@example.com'):
    assert client.post('/api/auth/register', json={**account(email), 'phone': '09170000123'}).status_code == 201
    return headers(sign_in(client, email, 'mobile'))


def grant(client, admin, station_id, email='tracker@example.com', **changes):
    return client.post(f'/api/stations/{station_id}/tracking-sessions', headers=admin,
                       json={'tracker_email': email, 'duration_minutes': 60, 'reason': 'Carry the portable station', **changes})


def fix(**changes):
    return {'latitude': 15.9801, 'longitude': 120.5607, 'accuracy_m': 6.5, 'captured_at': now().isoformat(), **changes}


def snapshot(client, auth, station_id):

    response = client.get('/api/monitoring/stations', headers=auth, params={'station_id': station_id})
    assert response.status_code == 200, response.text
    row, = response.json()['stations']
    return row


@pytest.fixture
def tracked(client, device):
    station_id, admin, issued = device
    phone = resident(client)
    session = grant(client, admin, station_id)
    assert session.status_code == 201, session.text
    return station_id, admin, phone, session.json()['id']


def test_only_admin_can_grant_and_only_to_an_active_resident(client, device):
    station_id, admin, issued = device
    phone = resident(client)
    assert grant(client, phone, station_id).status_code in (401, 403)          # residents cannot grant
    staff(client, 'officer')
    assert grant(client, admin, station_id, email='officer@example.com').status_code == 422   # staff accounts are not trackers
    assert grant(client, admin, station_id, email='nobody@example.com').status_code == 422
    assert grant(client, admin, station_id, duration_minutes=721).status_code == 422


def test_tracker_sees_its_session_and_posts_fixes(client, tracked):
    station_id, admin, phone, session_id = tracked
    active = client.get('/api/station-tracking/active', headers=phone).json()
    assert [(s['id'], s['station_id']) for s in active] == [(session_id, station_id)]
    # SQLite drops tzinfo; the contract must still carry an explicit UTC offset for clients.
    expires = datetime.fromisoformat(active[0]['expires_at'])
    assert expires.utcoffset() == timedelta(0) and expires > now()
    listed = client.get(f'/api/stations/{station_id}/tracking-sessions', headers=admin).json()[0]
    assert datetime.fromisoformat(listed['expires_at']).utcoffset() == timedelta(0)
    response = client.post(f'/api/station-tracking/{session_id}/positions', headers=phone, json=fix())
    assert response.status_code == 201, response.text
    live = snapshot(client, admin, station_id)['live_position']
    assert (live['latitude'], live['longitude'], live['accuracy_m']) == (15.9801, 120.5607, 6.5)
    assert live['fresh'] is True and live['tracking_active'] is True and live['source'] == 'operator_phone_gps'


@pytest.mark.parametrize('changes,status', [
    ({'accuracy_m': 51}, 422),                                                        # too coarse
    ({'captured_at': (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()}, 422),   # too old
    ({'captured_at': (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()}, 422),   # future
    ({'latitude': 91}, 422), ({'longitude': -181}, 422), ({'accuracy_m': 0}, 422),
    ({'captured_at': '2026-11-13T13:00:00'}, 422),                                   # naive time
    ({'extra': 1}, 422),
])
def test_invalid_fixes_are_rejected_and_never_stored(client, tracked, changes, status):
    station_id, admin, phone, session_id = tracked
    assert client.post(f'/api/station-tracking/{session_id}/positions', headers=phone, json=fix(**changes)).status_code == status
    assert snapshot(client, admin, station_id)['live_position'] is None


def test_rate_limit_and_ordering(client, tracked):
    station_id, admin, phone, session_id = tracked
    first = fix()
    assert client.post(f'/api/station-tracking/{session_id}/positions', headers=phone, json=first).status_code == 201
    assert client.post(f'/api/station-tracking/{session_id}/positions', headers=phone, json=fix()).status_code == 429


def test_other_accounts_cannot_report_for_a_session(client, tracked):
    station_id, admin, phone, session_id = tracked
    other = resident(client, 'other@example.com')
    assert client.post(f'/api/station-tracking/{session_id}/positions', headers=other, json=fix()).status_code == 404
    assert client.get('/api/station-tracking/active', headers=other).json() == []


def test_live_position_is_staff_only(client, tracked):
    station_id, admin, phone, session_id = tracked
    assert client.post(f'/api/station-tracking/{session_id}/positions', headers=phone, json=fix()).status_code == 201
    assert snapshot(client, admin, station_id)['live_position'] is not None
    # Residents (including the tracker) never receive another person's location in the shared feed.
    assert snapshot(client, phone, station_id)['live_position'] is None
    # The staff copy is unaffected by a resident's redacted read of the shared cache.
    response = client.get('/api/monitoring/stations', headers=admin, params={'station_id': station_id})
    assert response.json()['stations'][0]['live_position'] is not None


def test_ending_the_session_keeps_last_known_but_not_live(client, tracked):
    station_id, admin, phone, session_id = tracked
    assert client.post(f'/api/station-tracking/{session_id}/positions', headers=phone, json=fix()).status_code == 201
    ended = client.post(f'/api/stations/{station_id}/tracking-sessions/{session_id}/end', headers=admin, json={'reason': 'Arrived'})
    assert ended.status_code == 200 and ended.json()['active'] is False
    live = snapshot(client, admin, station_id)['live_position']
    assert live is not None and live['fresh'] is False and live['tracking_active'] is False
    assert client.post(f'/api/station-tracking/{session_id}/positions', headers=phone, json=fix()).status_code == 409
    assert client.get('/api/station-tracking/active', headers=phone).json() == []


def test_new_session_supersedes_the_previous_one(client, tracked):
    station_id, admin, phone, session_id = tracked
    second = grant(client, admin, station_id)
    assert second.status_code == 201
    sessions = client.get(f'/api/stations/{station_id}/tracking-sessions', headers=admin).json()
    assert [s['active'] for s in sessions] == [True, False]
    assert client.post(f'/api/station-tracking/{session_id}/positions', headers=phone, json=fix()).status_code == 409


def test_tracking_never_touches_registry_identity_credentials_or_ingest(client, tracked):
    station_id, admin, phone, session_id = tracked
    with SessionLocal() as db:
        station = db.query(Station).filter_by(station_id=station_id).one()
        before = (station.latitude, station.longitude, db.get(StationIdentity, station_id).version,
                  db.query(StationCredential).filter_by(station_id=station_id).count())
    assert client.post(f'/api/station-tracking/{session_id}/positions', headers=phone,
                       json=fix(latitude=14.6, longitude=121.0)).status_code == 201
    with SessionLocal() as db:
        station = db.query(Station).filter_by(station_id=station_id).one()
        after = (station.latitude, station.longitude, db.get(StationIdentity, station_id).version,
                 db.query(StationCredential).filter_by(station_id=station_id).count())
    assert after == before
    row = snapshot(client, admin, station_id)
    assert (row['latitude'], row['longitude'], row['coordinate_status']) == (before[0], before[1], 'verified')
    assert (row['live_position']['latitude'], row['live_position']['longitude']) == (14.6, 121.0)
