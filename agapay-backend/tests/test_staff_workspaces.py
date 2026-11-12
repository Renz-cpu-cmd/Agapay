from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Alert, StationAuditEvent, TelemetryProvenance, utc_now
from app.governance_models import GovernanceAudit
from app.identity_models import MutationAudit
from test_alerts import station, send, episodes
from station_support import command_queue_rows
from test_accounts import account, headers, reset_accounts, staff


def test_staff_views_are_private(client, station):
    for path in ("/api/alerts/command-queue", f"/api/stations/{station}/workspace"):
        assert client.get(path).status_code == 401
    resident = headers(client.post('/api/auth/register', json=account()))
    for path in ("/api/alerts/command-queue", f"/api/stations/{station}/workspace"):
        assert client.get(path, headers=resident).status_code == 403
    sample = send(client, station, 1, 105)
    episode, = episodes(station)
    assert client.post(f'/api/alerts/{episode.id}/ownership', headers=resident, json={
        'expected_revision': 0, 'expected_telemetry_id': sample['id'], 'action': 'take', 'reason': 'Test review'}).status_code == 403


def test_provenance_cannot_be_relabelled(client, station):
    access = staff(client)
    send(client, station, 1, 61)
    first, = episodes(station)
    # A physical designation at trigger and latest observation is required.
    # R5: select this test's own episode by its stable ID across complete pagination;
    # unrelated retained episodes may legitimately rank ahead of it.
    operational = {row['id']: row for row in command_queue_rows(client, access, 'operational')}
    assert first.id in operational and first.id not in {row['id'] for row in command_queue_rows(client, access, 'unverified')}
    assert operational[first.id]['ownership']['owner_id'] is None
    assert operational[first.id]['source'] == 'recorded_physical'
    with SessionLocal() as db:
        db.delete(db.get(TelemetryProvenance, first.trigger_telemetry_id))
        db.commit()
    # Removing the recorded trigger provenance must demote the episode: it can never
    # remain (or be relabelled) operational, and it stays visible as unverified.
    assert first.id not in {row['id'] for row in command_queue_rows(client, access, 'operational')}
    assert client.get('/api/alerts/command-queue', headers=access).json()['total'] == 0
    unverified = {row['id']: row for row in command_queue_rows(client, access, 'unverified')}
    assert first.id in unverified and unverified[first.id]['source'] == 'unverified'


def test_priority_and_oldest_first_are_applied_before_pagination(client, station):
    from uuid import uuid4
    from app.models import Station
    from station_support import device_token
    access = staff(client)
    send(client, station, 1, 61)
    ids = []
    for i in range(2):
        sid = 'PRIORITY_' + uuid4().hex[:12].upper()
        with SessionLocal() as db:
            db.add(Station(station_id=sid, station_name='Synthetic priority station'))
            db.commit()
        device_token(sid)
        send(client, sid, 1, 105)
        ep, = episodes(sid)
        ids.append(ep.id)
        with SessionLocal() as db:
            db.get(Alert, ep.id).triggered_at = utc_now() - timedelta(hours=2-i)
            db.commit()
    pages = [client.get(f'/api/alerts/command-queue?limit=1&offset={i}', headers=access).json() for i in range(3)]
    assert [p['items'][0]['id'] for p in pages] == ids + [episodes(station)[0].id]
    assert [p['has_more'] for p in pages] == [True, True, False]


def test_concurrent_ownership_is_audited_and_never_overwrites_another_owner(client, station):
    admin, officer = staff(client), staff(client, 'officer')
    sample = send(client, station, 1, 105)
    episode, = episodes(station)
    path = f'/api/alerts/{episode.id}/ownership'
    payload = dict(expected_revision=0, expected_telemetry_id=sample['id'], action='take', reason='Synthetic incident review')
    start = Barrier(2)
    def claim(access):
        start.wait(timeout=10)
        return client.post(path, headers=access, json=payload)
    with ThreadPoolExecutor(2) as pool:
        a, b = list(pool.map(claim, [admin, officer]))
    assert sorted([a.status_code, b.status_code]) == [200, 409]
    winner, loser = (admin, officer) if a.status_code == 200 else (officer, admin)
    saved = a.json() if a.status_code == 200 else b.json()
    assert saved['owner_name'] and saved['revision'] > 0
    release = {**payload, 'expected_revision': saved['revision'], 'action': 'release'}
    assert client.post(path, headers=loser, json={**release, 'action':'take'}).status_code == 409
    if loser == officer:
        assert client.post(path, headers=loser, json=release).status_code == 403
    assert client.post(path, headers=winner, json=payload).status_code == 409
    assert client.post(path, headers=winner, json=release).json()['owner_id'] is None
    with SessionLocal() as db:
        audits = db.scalars(select(GovernanceAudit).where(GovernanceAudit.action == 'sensor_owner_changed')).all()
        assert len(audits) == 2
        general = db.scalars(select(MutationAudit).where(MutationAudit.action == 'sensor_owner_changed').order_by(MutationAudit.id)).all()
        assert general[0].after['owner_id'] == saved['owner_id']
        assert db.get(Alert, episode.id).current_severity == 'EVACUATE'


def test_measurement_or_resolution_change_requires_manual_refresh(client, station):
    access = staff(client)
    sample = send(client, station, 1, 90)
    episode, = episodes(station)
    payload = dict(expected_revision=0, expected_telemetry_id=sample['id'], action='take', reason='Review water incident')
    send(client, station, 2, 105)
    assert client.post(f'/api/alerts/{episode.id}/ownership', headers=access, json=payload).status_code == 409
    send(client, station, 3, 0)
    assert client.post(f'/api/alerts/{episode.id}/ownership', headers=access, json=payload).status_code == 409


def test_administrator_can_record_a_supervised_release_without_reassigning_or_resolving(client, station):
    admin, officer = staff(client), staff(client, 'officer')
    sample = send(client, station, 1, 105)
    episode, = episodes(station)
    path = f'/api/alerts/{episode.id}/ownership'
    payload = dict(expected_revision=0, expected_telemetry_id=sample['id'], action='take', reason='Synthetic officer review')
    saved = client.post(path, headers=officer, json=payload).json()
    result = client.post(path, headers=admin, json={**payload, 'action':'release',
        'expected_revision':saved['revision'], 'reason':'Supervisor records handoff because the reviewer is unavailable'})
    assert result.status_code == 200 and result.json()['owner_id'] is None
    assert episodes(station)[0].status == 'ACTIVE'


def test_workspace_keeps_invalid_heartbeat_separate_and_redacts_registry_secrets(client, station):
    access = staff(client, 'officer')
    valid = send(client, station, 1, 90)
    latest = send(client, station, 2, None)
    with SessionLocal() as db:
        from app.models import User
        actor = db.scalar(select(User).where(User.role == 'officer'))
        for i in range(3):
            db.add(StationAuditEvent(station_id=station, actor_id=actor.id, actor_name=actor.name,
                action='maintenance_review', reason=f'Synthetic range review {i}',
                details={'token_hash':'MUST_NOT_LEAK'}, created_at=utc_now()+timedelta(seconds=i)))
        db.commit()
    response = client.get(f'/api/stations/{station}/workspace?limit=2', headers=access)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['last_valid']['id'] == valid['id']
    assert data['latest_sample']['id'] == latest['id']
    assert data['latest_sample']['quality'] == 'invalid'
    assert data['last_valid']['measured_at'] != data['latest_sample']['measured_at']
    assert data['last_valid']['received_at'] and data['identity']['datum'] == 'Synthetic test datum'
    # R5: select this station explicitly. An unfiltered snapshot is refused (503) by the
    # read-model station budget once earlier tests have created more than 200 stations.
    response_monitoring = client.get('/api/monitoring/stations', headers=access,
                                     params={'history_limit': 2, 'station_id': station})
    assert response_monitoring.status_code == 200, response_monitoring.text
    history = next(s for s in response_monitoring.json()['stations'] if s['station_id'] == station)['history']
    assert history[0]['measured_at'] and history[0]['received_at']
    assert data['has_more'] and len(data['events']) == 2
    assert client.get(f'/api/stations/{station}/workspace?limit=2&offset=2', headers=access).json()['events'][0]['id'] != data['events'][0]['id']
    assert 'token_hash' not in response.text and 'MUST_NOT_LEAK' not in response.text
