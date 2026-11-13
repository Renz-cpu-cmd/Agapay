"""The web BFF (/api/account/* in Next.js) does not check roles itself: it forwards the
staff session token with ``X-Agapay-Require-Staff: 1`` and relies on FastAPI to refuse
non-staff callers. That only fails closed if every user-facing route authenticates through
``current_user`` (which honours the header). This contract walks every registered route
and proves a resident token carrying the header is refused, except on a small reviewed
list of routes that never identify a user (public, device-token or bootstrap endpoints).
A new route that skips ``current_user`` fails here instead of silently admitting residents
through the web console.

The second half proves staff authorization does NOT depend on that optional header:
called directly (as the mobile app does), every staff read and mutation refuses
residents, admin-only reads refuse officers, and authorized roles are admitted."""
import re

import pytest
from fastapi.routing import APIRoute

from app.main import app
from test_accounts import account, headers, reset_accounts, staff  # noqa: F401  (autouse isolation)

STAFF = {'X-Agapay-Require-Staff': '1'}

# Routes that do not resolve a user account. Each was reviewed: public read models,
# station-device or receipt tokens, unauthenticated identity bootstrap, or health probes.
# None of these is on the BFF allowlist except the public identity paths
# (capabilities, mfa/verify, recovery/*), login/logout and the local-only setup page,
# which the BFF forwards WITHOUT the staff header, and the public privacy notice.
NON_USER_ROUTES = {
    # Identity bootstrap: unauthenticated by design (rate limited, origin checked by the BFF).
    ('GET', '/api/auth/capabilities'), ('GET', '/api/auth/setup'), ('POST', '/api/auth/setup'),
    ('POST', '/api/auth/login'), ('POST', '/api/auth/logout'), ('POST', '/api/auth/register'),
    ('POST', '/api/auth/mfa/verify'), ('POST', '/api/auth/recovery/request'),
    ('POST', '/api/auth/recovery/complete'),
    # Public notice text; contains no account data.
    ('GET', '/api/privacy/notice'),
    # Station-device ingest, authenticated by station credentials, not user sessions.
    ('POST', '/api/telemetry'), ('POST', '/api/exercises/telemetry'),
    # Delivery receipt, authenticated by a per-notification receipt token.
    ('POST', '/api/notification-receipts'),
    # Prometheus scrape, authenticated by its own scrape token (503 when unconfigured).
    ('GET', '/api/operations/metrics'),
    # Anonymous public read models (station registry and measurements). Not reachable
    # through the BFF; flagged separately for a policy decision, see the security report.
    ('GET', '/api/stations'), ('GET', '/api/stations/{station_id}'),
    ('GET', '/api/telemetry/{station_id}'), ('GET', '/api/telemetry/{station_id}/latest'),
    ('GET', '/api/exercises/telemetry/{station_id}'), ('GET', '/api/exercises/telemetry/{station_id}/latest'),
}


def test_reviewed_non_user_routes_still_exist():
    # A removed or renamed route must also leave this reviewed list.
    assert NON_USER_ROUTES <= set(_routes())


def _api_routes(routes):
    # FastAPI 0.141 wraps included routers; their APIRoutes keep the full path
    # because AGAPAY sets prefixes on the routers, not on include_router().
    for route in routes:
        nested = getattr(route, 'original_router', None)
        if nested is not None:
            yield from _api_routes(nested.routes)
        elif isinstance(route, APIRoute):
            yield route


def _routes():
    for route in _api_routes(app.routes):
        if not route.path.startswith('/api/'):
            continue
        for method in sorted(route.methods - {'HEAD', 'OPTIONS'}):
            yield method, route.path


def test_contract_sees_the_application_routes():
    # Guard against a silent empty parametrization if route discovery breaks.
    assert len(set(_routes())) > 100


def _concrete(path):
    samples = {'station_id': 'STATION_001', 'device_id': 'DEVICE_001'}
    return re.sub(r'\{(\w+)(?::\w+)?\}', lambda m: samples.get(m.group(1), '1'), path)


@pytest.mark.parametrize('method,path', sorted(set(_routes())))
def test_resident_with_bff_staff_header_is_refused(client, method, path):
    if (method, path) in NON_USER_ROUTES:
        pytest.skip('reviewed non-user route')
    resident = headers(client.post('/api/auth/register', json=account('bff-contract@example.com')))
    response = client.request(method, _concrete(path), headers={**resident, **STAFF},
                              json={} if method in ('POST', 'PATCH', 'PUT') else None)
    assert response.status_code in (401, 403), f'{method} {path} -> {response.status_code}'


# ---------------------------------------------------------------------------------------
# Direct FastAPI access WITHOUT the BFF header. Staff authorization must not depend on the
# optional header: a resident calling the API directly (as the mobile app does) may read
# only the routes reviewed below, and every staff mutation refuses residents.

# Resident-readable routes: used by the mobile app, scoped to the caller, or published
# product data. Each was reviewed in the P1 web-authorization investigation.
RESIDENT_READS = {
    '/api/auth/me', '/api/auth/preferences', '/api/auth/preferences/areas', '/api/auth/security',
    '/api/alert-subscriptions', '/api/alert-governance/capabilities',  # caller's own grants/subscriptions
    '/api/community-alerts', '/api/community-alerts/active', '/api/community-alerts/{alert_id}',
    '/api/monitoring/stations', '/api/rain-activity/{station_id}', '/api/predictions/{station_id}',
    '/api/forecasts/{identity}',  # published forecast product, no personal data
    '/api/stations/{station_id}/hazard-policy',  # station rule set, no personal data
    '/api/official-notices', '/api/response-resources', '/api/operations/status',  # public summaries
    '/api/notification-deliveries', '/api/notification-deliveries/consent',
    '/api/notification-deliveries/{identity}',
    '/api/privacy/cases', '/api/sos', '/api/sos/{sos_id}', '/api/sos-response/{sos_id}',  # caller-owned
    '/api/station-tracking/active',  # migration 0010: only the caller's own tracking assignments
}
ADMIN_ONLY_READS = {
    '/api/users', '/api/auth/audit', '/api/alert-governance/audit', '/api/stations/{station_id}/audit',
    '/api/stations/{station_id}/credentials', '/api/stations/{station_id}/configuration',
    '/api/stations/{station_id}/provisioning', '/api/privacy/admin/cases', '/api/privacy/admin/evidence',
    '/api/privacy/admin/access-review', '/api/privacy/admin/holds/{user_id}',
    '/api/delivery-recovery', '/api/delivery-recovery/holds',  # R2 P0 restored-delivery reconciliation
    '/api/stations/{station_id}/tracking-sessions',  # migration 0010: names tracker accounts
}
# Device-scoped exercise consent: refused to every web role by design.
DEVICE_ONLY_READS = {'/api/exercise-notifications/consent/{device_id}',
                     '/api/exercise-notifications/sessions/{session_id}'}
NON_USER_PATHS = {path for _, path in NON_USER_ROUTES}
STAFF_READS = sorted(p for m, p in set(_routes()) if m == 'GET' and p not in RESIDENT_READS | NON_USER_PATHS)


def test_reviewed_read_lists_match_the_application():
    paths = {p for m, p in _routes() if m == 'GET'}
    assert RESIDENT_READS <= paths and ADMIN_ONLY_READS <= paths and DEVICE_ONLY_READS <= paths
    assert len(STAFF_READS) >= 30


@pytest.mark.parametrize('path', STAFF_READS)
def test_staff_reads_refuse_residents_without_the_bff_header(client, path):
    resident = headers(client.post('/api/auth/register', json=account('direct-contract@example.com')))
    assert client.get(_concrete(path), headers=resident).status_code == 403, path


@pytest.mark.parametrize('path', STAFF_READS)
def test_staff_reads_admit_authorized_roles(client, path):
    officer, admin = staff(client, 'officer'), staff(client, 'admin')
    officer_status = client.get(_concrete(path), headers=officer).status_code
    admin_status = client.get(_concrete(path), headers=admin).status_code
    if path in DEVICE_ONLY_READS:
        assert officer_status == admin_status == 403
    elif path in ADMIN_ONLY_READS:
        assert officer_status == 403, f'officer admitted to admin-only {path}'
        assert admin_status not in (401, 403), f'admin refused on {path}'
    else:
        assert officer_status not in (401, 403), f'officer refused on {path}'
        assert admin_status not in (401, 403), f'admin refused on {path}'


def test_staff_mutations_refuse_residents_with_valid_bodies(client):
    """Role checks inside these handlers run after body validation, so an empty body
    proves nothing (422). Schema-valid bodies show the resident reaches the role check
    and is refused, directly against FastAPI and without the BFF header."""
    from datetime import timedelta
    from app.models import utc_now
    from test_alert_governance import notice_body
    resident = headers(client.post('/api/auth/register', json=account('mutation-contract@example.com')))
    sha, now = 'a' * 64, utc_now()
    cases = [
        ('POST', '/api/official-notices', notice_body()),
        ('POST', '/api/alert-governance/transitions/1/citywide',
         {'authority_id': 'APP', 'reason': 'Synthetic citywide dispatch attempt',
          'expires_at': (now + timedelta(hours=1)).isoformat()}),
        ('POST', '/api/operations/recovery-reviews',
         {'checked_at': now.isoformat(), 'code': 'SYNTHETIC_CODE', 'activity': 'investigated',
          'reason': 'Synthetic review', 'evidence_sha256': sha}),
        ('POST', '/api/notification-deliveries/1/reconcile',
         {'expected_version': 1, 'decision': 'closed_no_resend', 'evidence_kind': 'manual_review',
          'evidence_sha256': sha, 'reason': 'Synthetic reconcile'}),
        ('POST', '/api/hybrid-projections/STATION_001', {'controlled_basin_confirmed': True}),
        ('POST', '/api/auth/mfa/start', {'current_password': 'not-the-password'}),
        ('PATCH', '/api/sos/1', {'status': 'RESOLVED', 'expected_version': 1}),
    ]
    for method, url, body in cases:
        response = client.request(method, url, headers=resident, json=body)
        assert response.status_code == 403, f'{method} {url} -> {response.status_code} {response.text[:120]}'


def test_sensor_review_refuses_residents_on_a_real_episode(client):
    from uuid import uuid4
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.models import Alert, Station
    from station_support import device_token
    from test_alerts import send
    station_id = 'CONTRACT_' + uuid4().hex[:10].upper()
    with SessionLocal() as db:
        db.add(Station(station_id=station_id, station_name='Synthetic contract station'))
        db.commit()
    device_token(station_id)
    sample = send(client, station_id, 1, 90)
    with SessionLocal() as db:
        alert_id = db.scalar(select(Alert.id).where(Alert.station_id == station_id))
    resident = headers(client.post('/api/auth/register', json=account('review-contract@example.com')))
    response = client.post(f'/api/sensor-alerts/{alert_id}/reviews', headers=resident,
                           json={'expected_telemetry_id': sample['id'], 'authority_id': 'APP',
                                 'action': 'confirmed', 'reason': 'Synthetic resident review attempt'})
    assert response.status_code == 403, response.text
