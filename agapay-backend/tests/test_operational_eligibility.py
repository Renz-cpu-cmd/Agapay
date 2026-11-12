"""R4: reviewed-configuration eligibility for production-authoritative sensor actions.

Raw measurements, hazard decisions and incidents are always retained. Operational review
is required by default everywhere and fails closed whenever an external notification
provider is configured or the environment is production. Then only a station whose current installation
configuration is ``field_reviewed`` may capture resident push recipients, reach the
staff operational command queue or be dispatched citywide. Disposable SQLite fixtures
only; no provider, device or live database is contacted.
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.device_config import operational_eligibility, operational_review_required
from app.governance_models import HazardDecision
from app.models import Alert, AlertTransition, NotificationDelivery, NotificationEvent, Telemetry, TelemetryProvenance, utc_now
from app.operations_models import StationDeliveryGate
from app.services.notification_provider import FakeNotificationProvider
from app.services.notification_service import process_pending
from test_accounts import reset_accounts  # noqa: F401  (autouse account isolation)
from test_alerts import payload as legacy_payload
from test_interval_configuration import installation
from test_notifications import register, resident
from test_station_security import device, token_headers  # noqa: F401  (pytest fixture)


@pytest.fixture
def review_required(monkeypatch):
    monkeypatch.setattr(get_settings(), 'operational_review_required', True)


def configure(client, device, status, expected_revision=0, **changes):
    body = dict(expected_revision=expected_revision, installation=installation(**changes), validation_status=status,
                evidence='Synthetic software fixture; not a physical calibration certificate or authority approval',
                reason='R4 eligibility regression', effective_at=utc_now().isoformat())
    response = client.post(f'/api/stations/{device[0]}/configuration', headers=device[1], json=body)
    assert response.status_code == 201, response.text
    return response.json()['config_hash']


def water(client, device, sequence, depth, config_hash):
    body = {**legacy_payload(device[0], sequence, depth), 'schema_version': 3, 'rainfall_mm': None,
            'applied_config_hash': config_hash}
    response = client.post('/api/telemetry', headers=token_headers(device[2]), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def legacy_water(client, device, sequence, depth):
    response = client.post('/api/telemetry', headers=token_headers(device[2]), json=legacy_payload(device[0], sequence, depth))
    assert response.status_code == 201, response.text
    return response.json()


def evidence(station_id):
    with SessionLocal() as db:
        telemetry = list(db.scalars(select(Telemetry).where(Telemetry.station_id == station_id).order_by(Telemetry.id)))
        episode = db.scalar(select(Alert).where(Alert.station_id == station_id))
        transitions = list(db.scalars(select(AlertTransition).where(AlertTransition.station_id == station_id)
                                           .order_by(AlertTransition.id)))  # PostgreSQL has no implicit order
        events = list(db.scalars(select(NotificationEvent).where(
            NotificationEvent.transition_id.in_([t.id for t in transitions])))) if transitions else []
        gates = [db.get(StationDeliveryGate, e.id) for e in events]
        deliveries = list(db.scalars(select(NotificationDelivery).where(
            NotificationDelivery.event_id.in_([e.id for e in events])))) if events else []
        decisions = list(db.scalars(select(HazardDecision).where(HazardDecision.station_id == station_id)))
        provenance = [db.get(TelemetryProvenance, t.id) for t in telemetry]
        return SimpleNamespace(telemetry=telemetry, episode=episode, transitions=transitions, events=events,
                               gates=gates, deliveries=deliveries, decisions=decisions, provenance=provenance)


def queue_ids(client, device, scope):
    from station_support import command_queue_rows  # complete pagination (R5)
    return [row['id'] for row in command_queue_rows(client, device[1], scope)]


def operations(client, device):
    return client.get(f'/api/stations/{device[0]}/operations', headers=device[1]).json()


# --- Known R4 failure (re-audit 2026-10-23), reproduced through the public API ----------

def test_r4_prototype_configuration_cannot_capture_resident_push_when_review_required(client, device, review_required):
    register(client, resident(client))
    config_hash = configure(client, device, 'prototype')
    water(client, device, 1, 105, config_hash)
    found = evidence(device[0])
    # Measurement, provenance, hazard decision and incident are preserved.
    assert len(found.telemetry) == 1 and found.telemetry[0].eligible_for_current
    assert found.telemetry[0].water_depth_cm == 105 and found.provenance[0].source_class == 'physical_device'
    assert found.decisions and found.decisions[0].observation_tier == 'EVACUATE'
    assert found.episode.status == 'ACTIVE' and found.episode.current_severity == 'EVACUATE'
    # No resident notification intent can be acted on: the event is a suppressed audit
    # record with zero captured recipients, exactly like the maintenance contract.
    assert len(found.events) == 1 and found.gates[0].external_allowed is False
    assert found.gates[0].lifecycle_state == 'configuration_prototype'
    assert found.deliveries == []
    # Staff see it only as unverified, never in the operational command queue.
    assert found.episode.id not in queue_ids(client, device, 'operational')
    assert found.episode.id in queue_ids(client, device, 'unverified')
    assert operations(client, device)['external_sensor_notifications'] is False


@pytest.mark.parametrize('status', ['prototype', 'bench_reviewed'])
def test_unreviewed_configuration_statuses_are_ineligible(client, device, review_required, status):
    register(client, resident(client))
    config_hash = configure(client, device, status)
    for sequence, depth in enumerate((65, 90, 105), start=1):  # ADVISORY -> WARNING -> EVACUATE
        water(client, device, sequence, depth, config_hash)
    found = evidence(device[0])
    assert [t.new_severity for t in found.transitions] == ['ADVISORY', 'WARNING', 'EVACUATE']
    assert len(found.events) == 3 and all(g.external_allowed is False for g in found.gates)
    assert {g.lifecycle_state for g in found.gates} == {'configuration_' + status}
    assert found.deliveries == []
    with SessionLocal() as db:
        assert operational_eligibility(db, device[0]) == (False, 'configuration_' + status)


def test_station_without_reviewed_configuration_is_ineligible(client, device, review_required):
    register(client, resident(client))
    legacy_water(client, device, 1, 105)  # schema v2, no configuration has ever been reviewed
    found = evidence(device[0])
    assert found.telemetry[0].eligible_for_current and found.episode.current_severity == 'EVACUATE'
    assert found.gates[0].external_allowed is False and found.gates[0].lifecycle_state == 'configuration_missing'
    assert found.deliveries == []
    assert found.episode.id not in queue_ids(client, device, 'operational')


# --- Positive: reviewed stations keep immediate upward escalation -----------------------

def test_field_reviewed_configuration_keeps_immediate_escalation_and_delivery(client, device, review_required):
    register(client, resident(client))
    config_hash = configure(client, device, 'field_reviewed')
    for sequence, depth in enumerate((65, 90, 105), start=1):
        water(client, device, sequence, depth, config_hash)
    found = evidence(device[0])
    assert [t.new_severity for t in found.transitions] == ['ADVISORY', 'WARNING', 'EVACUATE']
    # Synthetic samples are 50 ms apart, so the provisional rate check may flag review;
    # it must never delay an upward escalation (both reasons escalate immediately).
    assert [d.episode_tier for d in found.decisions] == ['ADVISORY', 'WARNING', 'EVACUATE']
    assert {d.reason for d in found.decisions} <= {'immediate_escalation', 'immediate_escalation_review'}
    assert all(g.external_allowed is True and g.lifecycle_state == 'active' for g in found.gates)
    assert len(found.deliveries) == 3 and {d.state for d in found.deliveries} == {'PENDING'}
    assert found.episode.id in queue_ids(client, device, 'operational')
    assert operations(client, device)['external_sensor_notifications'] is True
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 3
    # Existing worker contract: superseded lower tiers are suppressed, the newest tier is
    # sent (fake provider: TESTED, no external send).
    states = [d.state for d in sorted(evidence(device[0]).deliveries, key=lambda d: d.event_id)]
    assert states == ['SUPPRESSED', 'SUPPRESSED', 'TESTED'] and len(provider.messages) == 1


def test_direct_jump_to_evacuate_is_not_delayed_for_reviewed_station(client, device, review_required):
    register(client, resident(client))
    config_hash = configure(client, device, 'field_reviewed')
    water(client, device, 1, 105, config_hash)
    found = evidence(device[0])
    assert [(t.previous_severity, t.new_severity) for t in found.transitions] == [('NORMAL', 'EVACUATE')]
    assert len(found.deliveries) == 1


# --- Boundaries ---------------------------------------------------------------------------

def test_downgrade_after_capture_suppresses_pending_push_without_replay(client, device, review_required):
    register(client, resident(client))
    reviewed = configure(client, device, 'field_reviewed')
    water(client, device, 1, 105, reviewed)
    assert [d.state for d in evidence(device[0]).deliveries] == ['PENDING']
    configure(client, device, 'prototype', expected_revision=1)  # review withdrawn before the worker runs
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 1
    assert [d.state for d in evidence(device[0]).deliveries] == ['SUPPRESSED'] and provider.messages == {}
    configure(client, device, 'field_reviewed', expected_revision=2)  # review restored
    assert process_pending(provider) == 0 and provider.messages == {}  # suppressed delivery is never replayed
    assert [d.state for d in evidence(device[0]).deliveries] == ['SUPPRESSED']


def test_later_review_does_not_replay_suppressed_prototype_events(client, device, review_required):
    register(client, resident(client))
    prototype = configure(client, device, 'prototype')
    water(client, device, 1, 105, prototype)
    reviewed = configure(client, device, 'field_reviewed', expected_revision=1)
    provider = FakeNotificationProvider()
    assert process_pending(provider) == 0 and provider.messages == {}
    found = evidence(device[0])
    assert found.deliveries == [] and found.gates[0].external_allowed is False
    # The episode is still unverified: its trigger used the prototype configuration.
    assert found.episode.id not in queue_ids(client, device, 'operational')
    # Telemetry still reporting the superseded prototype hash is a configuration
    # mismatch and cannot become current under the reviewed revision.
    stale = water(client, device, 2, 106, prototype)
    assert stale['disposition'] == 'configuration_mismatch'
    assert reviewed != prototype


def test_citywide_dispatch_cannot_bypass_unreviewed_configuration(client, device, review_required):
    config_hash = configure(client, device, 'prototype')
    water(client, device, 1, 105, config_hash)
    with SessionLocal() as db:
        from app.services.station_lifecycle import delivery_allowed
        event = db.scalar(select(NotificationEvent))
        transition = db.get(AlertTransition, event.transition_id)
        assert delivery_allowed(db, event, transition.station_id) is False


def test_development_default_is_deny(monkeypatch):
    from app.config import Settings
    monkeypatch.delenv('AGAPAY_OPERATIONAL_REVIEW_REQUIRED', raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.environment == 'development' and defaults.operational_review_required is True
    assert defaults.notification_provider == 'disabled'
    assert operational_review_required(defaults)


@pytest.mark.parametrize('environment,flag,provider,required', [
    ('production', False, 'disabled', True),   # production can never opt out
    ('production', False, 'fcm', True),
    ('development', True, 'disabled', True),   # default
    ('development', False, 'fcm', True),       # fail closed: flag alone cannot reach real phones
    ('development', False, 'apns', True),      # any future external provider also fails closed
    ('testing', False, 'fcm', True),
    ('development', False, 'disabled', False),  # only relaxation: no external provider exists
    ('testing', False, 'disabled', False),
])
def test_review_requirement_fails_closed(environment, flag, provider, required):
    assert operational_review_required(SimpleNamespace(
        environment=environment, operational_review_required=flag, notification_provider=provider)) is required


def test_flag_false_with_external_provider_still_blocks_prototype_push(client, device, monkeypatch):
    monkeypatch.setattr(get_settings(), 'operational_review_required', False)
    monkeypatch.setattr(get_settings(), 'notification_provider', 'fcm')  # configuration only; nothing is sent
    register(client, resident(client))
    config_hash = configure(client, device, 'prototype')
    water(client, device, 1, 105, config_hash)
    found = evidence(device[0])
    assert found.episode.current_severity == 'EVACUATE'
    assert found.gates[0].external_allowed is False and found.deliveries == []


def test_explicit_test_relaxation_requires_disabled_provider(client, device):
    # conftest relaxes review only because the provider is "disabled" (fake providers only).
    assert get_settings().notification_provider == 'disabled' and get_settings().operational_review_required is False
    register(client, resident(client))
    config_hash = configure(client, device, 'prototype')
    water(client, device, 1, 105, config_hash)
    found = evidence(device[0])
    assert found.gates[0].external_allowed is True and len(found.deliveries) == 1
    with SessionLocal() as db:
        assert operational_eligibility(db, device[0]) == (True, 'review_not_required')


# --- Resident community feed verification (fail closed, server-derived) -------------------

def feed(client, access, device, route='/active'):
    response = client.get(f'/api/community-alerts{route}', headers=access, params={'station_id': device[0]})
    assert response.status_code == 200, response.text
    return response.json()['items']


def instantaneous_policy(station_id):
    from app.governance_models import HazardPolicy
    with SessionLocal() as db:
        db.add(HazardPolicy(station_id=station_id, version=1, evidence='Synthetic instantaneous fixture, not approved policy',
                            rules=dict(advisory_hysteresis_cm=0, warning_hysteresis_cm=0, evacuate_hysteresis_cm=0,
                                       recovery_samples=1, recovery_seconds=0, max_sample_gap_seconds=3600,
                                       max_change_cm_per_second=10000)))
        db.commit()


@pytest.mark.parametrize('status,expected', [('prototype', 'unverified'), ('bench_reviewed', 'unverified'),
                                             ('field_reviewed', 'operational')])
def test_community_feed_verification_follows_recorded_configuration(client, device, review_required, status, expected):
    access = resident(client)
    config_hash = configure(client, device, status)
    water(client, device, 1, 105, config_hash)
    item, = feed(client, access, device)
    assert item['severity'] == 'EVACUATE' and item['verification'] == expected
    detail = client.get(f"/api/community-alerts/{item['id']}", headers=access).json()
    assert detail['verification'] == expected and detail['transitions']['total'] == 1
    assert evidence(device[0]).deliveries == [] if expected == 'unverified' else True


def test_community_feed_missing_configuration_fails_closed(client, device):
    # Even with the test-only review relaxation, the resident label never relaxes.
    access = resident(client)
    legacy_water(client, device, 1, 105)
    item, = feed(client, access, device)
    assert item['verification'] == 'unverified'


def test_later_review_never_promotes_earlier_unverified_incident(client, device, review_required):
    access = resident(client)
    prototype = configure(client, device, 'prototype')
    water(client, device, 1, 105, prototype)
    reviewed = configure(client, device, 'field_reviewed', expected_revision=1)
    assert feed(client, access, device)[0]['verification'] == 'unverified'
    water(client, device, 2, 106, reviewed)  # latest observation is now reviewed, the trigger was not
    item, = feed(client, access, device)
    assert item['latest_depth_cm'] == 106 and item['verification'] == 'unverified'


@pytest.mark.parametrize('withdrawal', ['configuration', 'maintenance'])
def test_withdrawn_eligibility_demotes_active_incident(client, device, review_required, withdrawal):
    access = resident(client)
    reviewed = configure(client, device, 'field_reviewed')
    water(client, device, 1, 105, reviewed)
    assert feed(client, access, device)[0]['verification'] == 'operational'
    if withdrawal == 'configuration':
        configure(client, device, 'prototype', expected_revision=1)
    else:
        current = operations(client, device)
        response = client.post(f'/api/stations/{device[0]}/lifecycle', headers=device[1], json=dict(
            expected_revision=current['revision'], expected_identity_version=current['identity_version'],
            state='maintenance', reason='Synthetic eligibility withdrawal'))
        assert response.status_code == 200, response.text
    item, = feed(client, access, device)
    assert item['status'] == 'ACTIVE' and item['verification'] == 'unverified'  # retained, not deleted


def test_resolved_reviewed_incident_keeps_its_recorded_verification(client, device, review_required):
    access = resident(client)
    instantaneous_policy(device[0])
    reviewed = configure(client, device, 'field_reviewed')
    water(client, device, 1, 105, reviewed)
    water(client, device, 2, 0, reviewed)  # valid NORMAL reading resolves the episode
    item, = feed(client, access, device, route='')
    assert item['status'] == 'RESOLVED' and item['verification'] == 'operational'
    configure(client, device, 'prototype', expected_revision=1)  # later withdrawal does not rewrite history
    assert feed(client, access, device, route='')[0]['verification'] == 'operational'
    assert feed(client, access, device) == []


def test_staff_diagnostics_remain_available_for_unverified_incident(client, device, review_required):
    config_hash = configure(client, device, 'prototype')
    water(client, device, 1, 105, config_hash)
    episode = evidence(device[0]).episode
    assert episode.id in queue_ids(client, device, 'unverified')
    workspace = client.get(f'/api/stations/{device[0]}/workspace', headers=device[1])
    assert workspace.status_code == 200, workspace.text
    last_valid = workspace.json()['last_valid']
    assert last_valid['quality'] == 'valid' and last_valid['source_class'] == 'physical_device'
    history = client.get(f'/api/alerts/{episode.id}/transitions', headers=device[1])
    assert history.status_code == 200 and history.json()


def test_exercise_and_local_bench_outputs_stay_outside_operational_channels(client, device, review_required):
    register(client, resident(client))
    config_hash = configure(client, device, 'field_reviewed')
    body = {**legacy_payload(device[0], 1, 105), 'schema_version': 3, 'rainfall_mm': None,
            'applied_config_hash': config_hash, 'local_alert_profile': 'cardboard_bench'}
    response = client.post('/api/telemetry', headers=token_headers(device[2]), json=body)
    assert response.status_code == 201 and response.json()['disposition'] == 'exercise_local_outputs'
    found = evidence(device[0])
    assert found.telemetry[0].water_depth_cm == 105 and not found.telemetry[0].eligible_for_current
    assert found.episode is None and found.events == []
