"""R1: the station registry is the only source of a map position. Disposable SQLite."""
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from app.database import SessionLocal
from app.models import Station, StationIdentity
from app.services.monitoring_service import registry_location
from test_accounts import reset_accounts, staff  # noqa: F401  (autouse account isolation)
from test_alerts import payload
from test_station_security import commissioning, device, provision, token_headers  # noqa: F401


@pytest.mark.parametrize('lat,lon,verified,expected', [
    (15.97, 120.57, True, (15.97, 120.57, 'verified')),
    (15.97, 120.57, False, (15.97, 120.57, 'unverified')),
    (0.0, 0.0, True, (0.0, 0.0, 'verified')),          # zero is a valid coordinate
    (0, 120.5, False, (0.0, 120.5, 'unverified')),
    (-90, 180, True, (-90.0, 180.0, 'verified')),
    (None, None, True, (None, None, 'missing')),
    (None, 120.5, True, (None, None, 'invalid')),
    (15.9, None, True, (None, None, 'invalid')),
    (90.0001, 120, True, (None, None, 'invalid')),
    (15.9, -180.5, True, (None, None, 'invalid')),
    (float('nan'), 120, True, (None, None, 'invalid')),
    (15.9, float('inf'), True, (None, None, 'invalid')),
])
def test_registry_location_rules(lat, lon, verified, expected):
    station = SimpleNamespace(latitude=lat, longitude=lon)
    identity = SimpleNamespace(coordinates_verified=verified)
    assert registry_location(station, identity) == expected


def test_no_identity_is_never_verified():
    assert registry_location(SimpleNamespace(latitude=15.9, longitude=120.5), None)[2] == 'unverified'


def monitored(client, access, station_id):
    response = client.get('/api/monitoring/stations', headers=access, params={'station_id': station_id})
    assert response.status_code == 200, response.text
    row, = response.json()['stations']
    return row


def test_monitoring_reports_registry_location_state(client, device):
    station_id, admin, issued = device
    row = monitored(client, admin, station_id)
    assert (row['latitude'], row['longitude'], row['coordinate_status']) == (15.98, 120.56, 'verified')
    with SessionLocal() as db:
        db.execute(update(StationIdentity).where(StationIdentity.station_id == station_id).values(coordinates_verified=False))
        db.commit()
    assert monitored(client, admin, station_id)['coordinate_status'] == 'unverified'


@pytest.mark.parametrize('lat,lon,state', [(None, None, 'missing'), (None, 120.5, 'invalid'), (95.0, 120.5, 'invalid')])
def test_missing_or_invalid_location_keeps_measurement_and_active_alert(client, device, lat, lon, state):
    station_id, admin, issued = device
    response = client.post('/api/telemetry', headers=token_headers(issued), json=payload(station_id, 1, 105))
    assert response.status_code == 201, response.text
    with SessionLocal() as db:  # simulate a legacy/manual registry row; the API validates new writes
        db.execute(update(Station).where(Station.station_id == station_id).values(latitude=lat, longitude=lon))
        db.commit()
    row = monitored(client, admin, station_id)
    assert (row['latitude'], row['longitude'], row['coordinate_status']) == (None, None, state)
    assert row['current_depth_cm'] == 105 and row['active_hazard_tier'] == 'EVACUATE'


def test_registry_writes_reject_out_of_range_or_half_coordinates(client):
    admin = staff(client)
    for changes in ({'latitude': 91}, {'longitude': 181}, {'latitude': None}):
        body, response = provision(client, admin, **changes)
        assert response.status_code == 422, (changes, response.text)


# A7.1: precision of the registry position is structured metadata, never inferred.
def precision(client, admin, station_id, **body):
    return client.put(f'/api/stations/{station_id}/location-precision', headers=admin,
                      json={'reason': 'Record location precision', **body})


def test_precision_is_absent_until_recorded_and_never_inferred(client, device):
    station_id, admin, issued = device
    row = monitored(client, admin, station_id)
    # 15.98/120.56 look "rounded", but nothing is inferred from digits or datum notes.
    assert row['coordinate_status'] == 'verified'
    assert (row['coordinate_precision_m'], row['coordinate_basis']) == (None, None)


@pytest.mark.parametrize('metres,basis', [(1100, 'owner_confirmed'), (5, 'surveyed'), (300, 'estimated')])
def test_recorded_precision_is_reported_without_touching_identity_or_credentials(client, device, metres, basis):
    station_id, admin, issued = device
    with SessionLocal() as db:
        version = db.get(StationIdentity, station_id).version
    response = precision(client, admin, station_id, precision_m=metres, basis=basis, note='synthetic')
    assert response.status_code == 200, response.text
    row = monitored(client, admin, station_id)
    assert (row['coordinate_status'], row['coordinate_precision_m'], row['coordinate_basis']) == ('verified', metres, basis)
    with SessionLocal() as db:
        assert db.get(StationIdentity, station_id).version == version          # never re-commissioned
    # The device credential still ingests: recording precision is metadata, not commissioning.
    assert client.post('/api/telemetry', headers=token_headers(issued), json=payload(station_id, 7, 40)).status_code == 201


def test_precision_never_creates_a_pin_for_missing_or_invalid_coordinates(client, device):
    station_id, admin, issued = device
    assert precision(client, admin, station_id, precision_m=1100, basis='owner_confirmed').status_code == 200
    with SessionLocal() as db:
        db.execute(update(Station).where(Station.station_id == station_id).values(latitude=None, longitude=None))
        db.commit()
    row = monitored(client, admin, station_id)
    assert (row['latitude'], row['longitude'], row['coordinate_status']) == (None, None, 'missing')
    assert (row['coordinate_precision_m'], row['coordinate_basis']) == (None, None)


@pytest.mark.parametrize('body', [
    {'precision_m': 0, 'basis': 'surveyed'}, {'precision_m': 100001, 'basis': 'surveyed'},
    {'precision_m': 10, 'basis': 'guess'}, {'precision_m': 10, 'basis': 'surveyed', 'extra': 1},
])
def test_precision_writes_are_validated(client, device, body):
    station_id, admin, issued = device
    assert precision(client, admin, station_id, **body).status_code == 422


def test_precision_write_requires_admin(client, device):
    station_id, admin, issued = device
    resident = client.post('/api/auth/register', json={'name': 'Resident', 'email': 'precision-resident@example.com',
                           'password': 'resident-password-123', 'phone': '09170000002', 'barangay': 'Synthetic'})
    assert resident.status_code == 201, resident.text
    headers = {'Authorization': 'Bearer ' + resident.json()['access_token']}
    assert precision(client, headers, station_id, precision_m=10, basis='surveyed').status_code in (401, 403)
