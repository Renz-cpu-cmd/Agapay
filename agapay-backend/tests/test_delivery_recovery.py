"""R2 P0: restored / uncertain deliveries are never replayed; recovery is explicit and audited.

Engine-agnostic (SQLite by default, PostgreSQL in suite mode). Real pg_dump/pg_restore
scenarios live in tests/test_postgres_recovery.py. Fake providers only.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib

import pytest
from sqlalchemy import select, update

from app.config import get_settings
from app.database import SessionLocal
from app.exercise_models import ExerciseDelivery
from app.models import NotificationDelivery, User
from app.privacy_models import RecoveryFence
from app.recovery_models import DeliveryGeneration, DeliveryHold, DeliveryRecoveryEvent
from app.services import delivery_recovery as recovery
from app.services.notification_provider import FakeNotificationProvider, SendOutcome
from app.services.notification_service import process_pending
from test_accounts import reset_accounts, staff  # noqa: F401  (autouse: isolate accounts per test)
from test_alerts import send, station  # noqa: F401  (fixture)
from test_notifications import register, resident

EVIDENCE = hashlib.sha256(b'synthetic provider export').hexdigest()


class Recording:
    mode = 'test'

    def __init__(self, outcome=SendOutcome.TEST_ONLY):
        self.keys, self.outcome = [], outcome

    def send(self, target, message, *, delivery_key):
        self.keys.append(delivery_key)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def queued(client, station, depth=70, sequence=1):  # noqa: F811
    access = resident(client)
    register(client, access)
    send(client, station, sequence, depth)
    return access


def deliveries():
    with SessionLocal() as db:
        return db.scalars(select(NotificationDelivery).order_by(NotificationDelivery.id)).all()


def admin_id(client):
    headers = staff(client)
    with SessionLocal() as db:
        return headers, db.scalar(select(User.id).where(User.email == 'admin@example.com'))


def declare(actor, reason='Synthetic drill: restored database from backup'):
    with SessionLocal() as db:
        generation = recovery.declare(db, kind='declared', reason=reason, actor_id=actor)
        db.commit()
        return generation.generation


def activate(actor, **kwargs):
    with SessionLocal() as db:
        recovery.activate(db, actor_id=actor, reason='Reconciled synthetic drill holds', **kwargs)
        db.commit()


def holds():
    with SessionLocal() as db:
        return db.scalars(select(DeliveryHold).order_by(DeliveryHold.id)).all()


def anchor(path):
    with SessionLocal() as db:
        generation = db.scalar(select(DeliveryGeneration).where(DeliveryGeneration.state == 'ACTIVE'))
        recovery.Ledger(path).anchor(generation.token, generation.claim_seq)


# --- Declaration and holds ---------------------------------------------------------------

def test_declaration_holds_uncertain_rows_without_rewriting_them(client, station):  # noqa: F811
    _, actor = admin_id(client)
    queued(client, station)
    with SessionLocal() as db:
        row = db.scalar(select(NotificationDelivery))
        snapshot = (row.id, row.state, row.attempts, row.result_category, row.created_at)
    number = declare(actor)
    hold, = holds()
    assert (hold.generation, hold.kind, hold.delivery_id, hold.original_state, hold.reason_code) == (
        number, 'operational', str(snapshot[0]), 'PENDING', 'pending_at_boundary')
    with SessionLocal() as db:
        row = db.get(NotificationDelivery, snapshot[0])
        assert (row.id, row.state, row.attempts, row.result_category, row.created_at) == snapshot, 'delivery row untouched'
        assert [(g.generation, g.state) for g in db.scalars(select(DeliveryGeneration).order_by(DeliveryGeneration.generation))] == [
            (1, 'SUPERSEDED'), (2, 'RECOVERING')]
        assert db.scalar(select(DeliveryRecoveryEvent.action).where(DeliveryRecoveryEvent.generation == number)) == 'recovery_declared'


@pytest.mark.parametrize('state,held', [('PENDING', True), ('PROCESSING', True), ('UNKNOWN', True),
                                        ('FAILED', True), ('SENT', False), ('TESTED', False), ('SUPPRESSED', False)])
def test_only_replay_eligible_or_uncertain_states_are_held(client, station, state, held):  # noqa: F811
    _, actor = admin_id(client)
    queued(client, station)
    with SessionLocal() as db:
        db.execute(update(NotificationDelivery).values(state=state, attempts=0 if state == 'PENDING' else 1))
        db.commit()
    declare(actor)
    assert [h.original_state for h in holds()] == ([state] if held else [])


def test_permanently_failed_and_operator_closed_rows_are_not_held(client, station):  # noqa: F811
    _, actor = admin_id(client)
    queued(client, station)
    with SessionLocal() as db:
        row = db.scalar(select(NotificationDelivery))
        row.state, row.attempts, row.completed_at = 'FAILED', 3, row.created_at
        db.commit()
    declare(actor)
    assert holds() == []


# --- Claim boundary ---------------------------------------------------------------------

def test_no_claim_while_recovering_and_held_rows_never_claimed_after_activation(client, station):  # noqa: F811
    _, actor = admin_id(client)
    access = queued(client, station, depth=70)
    declare(actor)
    provider = Recording()
    with pytest.raises(recovery.DeliveryFenced, match='RECOVERING'):
        process_pending(provider)
    hold, = holds()
    with SessionLocal() as db:
        recovery.decide(db, hold.id, actor_id=actor, decision='outcome_unknown', evidence_kind='no_provider_record',
                        evidence_sha256=EVIDENCE, reason='No provider record retained for the drill window', expected_version=1)
        db.commit()
    activate(actor)
    assert process_pending(provider) == 0 and provider.keys == [], 'a decided hold is closed, never resent'
    send(client, station, 2, 105)  # genuinely new post-recovery escalation
    assert process_pending(provider) == 1
    old, new = deliveries()
    assert provider.keys == [f'agapay-delivery-{new.id}'] and old.state == 'PENDING' and new.state == 'TESTED'
    assert process_pending(provider) == 0 and len(provider.keys) == 1
    assert access


def test_uninitialized_or_ambiguous_generation_fails_closed(client, station):  # noqa: F811
    queued(client, station)
    with SessionLocal() as db:
        db.execute(DeliveryGeneration.__table__.delete())
        db.commit()
    with pytest.raises(recovery.DeliveryFenced, match='not initialized'):
        process_pending(Recording())
    with SessionLocal() as db:
        for number in (1, 2):
            db.add(DeliveryGeneration(generation=number, token=f'00000000-0000-4000-8000-00000000000{number}', state='ACTIVE',
                                      kind='initialize', reason='Ambiguous synthetic state', claim_seq=0,
                                      database_identity=recovery.database_identity(db)))
        db.commit()
    with pytest.raises(recovery.DeliveryFenced, match='More than one'):
        process_pending(Recording())
    assert [d.state for d in deliveries()] == ['PENDING']


def test_database_identity_mismatch_fails_closed(client, station):  # noqa: F811
    queued(client, station)
    with SessionLocal() as db:
        db.execute(update(DeliveryGeneration).values(database_identity='0:0'))
        db.commit()
    provider = Recording()
    with pytest.raises(recovery.DeliveryFenced, match='identity'):
        process_pending(provider)
    assert provider.keys == []


def test_recovery_declared_after_claim_suppresses_before_the_provider_call(client, station):  # noqa: F811
    _, actor = admin_id(client)
    queued(client, station)
    provider = Recording()

    def boundary(stage):
        if stage == 'claimed':
            declare(actor, reason='Recovery declared while a claim was in flight')
    assert process_pending(provider, boundary=boundary) == 1
    row, = deliveries()
    assert provider.keys == [] and (row.state, row.result_category) == ('SUPPRESSED', 'recovery_fenced')
    hold, = holds()
    assert hold.original_state == 'PROCESSING' and hold.reason_code == 'in_flight_at_boundary'


def test_unknown_outcome_is_never_retried_and_is_held_on_declaration(client, station):  # noqa: F811
    _, actor = admin_id(client)
    queued(client, station)
    provider = Recording(RuntimeError('synthetic timeout after possible acceptance'))
    assert process_pending(provider) == 1
    assert process_pending(provider) == 0 and len(provider.keys) == 1 and deliveries()[0].state == 'UNKNOWN'
    declare(actor)
    assert [(h.original_state, h.reason_code) for h in holds()] == [('UNKNOWN', 'provider_outcome_unknown')]


def test_concurrent_workers_during_recovery_never_reach_the_provider(client, station):  # noqa: F811
    _, actor = admin_id(client)
    queued(client, station)
    declare(actor)
    provider = Recording()

    def worker(_):
        try:
            return process_pending(provider)
        except recovery.DeliveryFenced:
            return 'fenced'
    with ThreadPoolExecutor(6) as pool:
        assert set(pool.map(worker, range(12))) == {'fenced'}
    assert provider.keys == [] and deliveries()[0].state == 'PENDING'


# --- External ledger ------------------------------------------------------------------------

def test_ledger_detects_a_rolled_back_claim_sequence(client, station, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(get_settings(), 'delivery_ledger_path', str(tmp_path / 'ledger'))
    queued(client, station)
    with pytest.raises(recovery.DeliveryFenced, match='unavailable'):
        process_pending(Recording())
    anchor(tmp_path / 'ledger')
    provider = Recording()
    assert process_pending(provider) == 1
    # Simulate restoring the database to a point before that claim: the row is unsent again
    # and the generation's claim sequence is behind the ledger high-water mark.
    with SessionLocal() as db:
        db.execute(update(NotificationDelivery).values(state='PENDING', attempts=0, completed_at=None))
        db.execute(update(DeliveryGeneration).values(claim_seq=0))
        db.commit()
    recovery._ledgers.clear()  # A different worker process after the restore.
    with pytest.raises(recovery.DeliveryFenced, match='behind the external ledger'):
        process_pending(provider)
    assert len(provider.keys) == 1, 'the restored PENDING delivery is not replayed'
    assert deliveries()[0].state == 'PENDING' and deliveries()[0].attempts == 0, 'the refused claim rolled back'


def test_ledger_token_mismatch_and_unreadable_entries_fail_closed(client, station, tmp_path, monkeypatch):  # noqa: F811
    ledger = tmp_path / 'ledger'
    monkeypatch.setattr(get_settings(), 'delivery_ledger_path', str(ledger))
    queued(client, station)
    recovery.Ledger(ledger).anchor('00000000-0000-4000-8000-0000000000ff', 0)
    with pytest.raises(recovery.DeliveryFenced, match='does not match'):
        process_pending(Recording())
    (ledger / 'anchor.json').write_text('{not json', encoding='utf-8')
    with pytest.raises(recovery.DeliveryFenced, match='unreadable'):
        process_pending(Recording())


def test_worker_restart_without_restore_keeps_delivering_new_work(client, station, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(get_settings(), 'delivery_ledger_path', str(tmp_path / 'ledger'))
    queued(client, station, depth=70)
    anchor(tmp_path / 'ledger')
    provider = Recording()
    assert process_pending(provider) == 1
    recovery._ledgers.clear()  # Unplanned worker restart: new process, same database.
    send(client, station, 2, 105)
    assert process_pending(provider) == 1 and len(provider.keys) == 2
    assert holds() == [], 'a restart without restoration quarantines nothing'


def test_production_requires_the_external_witness(client, station, monkeypatch):  # noqa: F811
    queued(client, station)
    monkeypatch.setattr(get_settings(), 'environment', 'production')
    with pytest.raises(recovery.DeliveryFenced, match='AGAPAY_DELIVERY_LEDGER_PATH'):
        process_pending(Recording())


# --- Operator workflow ----------------------------------------------------------------------

def test_admin_api_lists_explains_and_decides_holds_without_resending(client, station):  # noqa: F811
    headers, actor = admin_id(client)
    access = queued(client, station)
    declare(actor)
    assert client.get('/api/delivery-recovery', headers=access).status_code == 403
    state = client.get('/api/delivery-recovery', headers=headers).json()
    assert (state['state'], state['open'], state['undecided']) == ('RECOVERING', False, 1)
    item, = client.get('/api/delivery-recovery/holds?undecided=true', headers=headers).json()['items']
    assert item['resend'] == 'never' and 'Never resent automatically' in item['explanation']
    url = f"/api/delivery-recovery/holds/{item['id']}/decision"
    body = dict(decision='provider_accepted', evidence_kind='no_provider_record', evidence_sha256=EVIDENCE,
                reason='Provider console shows acceptance', expected_version=1)
    assert client.post(url, headers=headers, json=body).status_code == 409, 'acceptance needs a provider record'
    body['evidence_kind'] = 'provider_record'
    assert client.post(url, headers=access, json=body).status_code == 403
    decided = client.post(url, headers=headers, json=body)
    assert decided.status_code == 200 and decided.json()['decision'] == 'provider_accepted'
    assert client.post(url, headers=headers, json={**body, 'expected_version': 2}).status_code == 409, 'decisions are final'
    with SessionLocal() as db:
        actions = list(db.scalars(select(DeliveryRecoveryEvent.action).order_by(DeliveryRecoveryEvent.id)))
        assert actions == ['recovery_declared', 'hold_decided']
        event = db.scalar(select(DeliveryRecoveryEvent).where(DeliveryRecoveryEvent.action == 'hold_decided'))
        event.details = {}
        with pytest.raises(ValueError, match='append-only'):
            db.commit()
    assert deliveries()[0].state == 'PENDING', 'a decision never rewrites or re-queues the delivery'


def test_activation_requires_admin_released_data_and_decided_or_deferred_holds(client, station):  # noqa: F811
    _, actor = admin_id(client)
    queued(client, station)
    declare(actor)
    with pytest.raises(recovery.RecoveryRefused, match='administrator'):
        activate(None)
    with SessionLocal() as db:
        db.add(RecoveryFence(id=1, state='QUARANTINED', backup_sha256=EVIDENCE))
        db.commit()
    with pytest.raises(recovery.RecoveryRefused, match='restored-data fence'):
        activate(actor)
    with SessionLocal() as db:
        recovery.release_restored_data(db, actor_id=actor, reason='Privacy withdrawals reconciled for drill')
        db.commit()
    with pytest.raises(recovery.RecoveryRefused, match='undecided'):
        activate(actor)
    activate(actor, allow_undecided=True)
    with SessionLocal() as db:
        event = db.scalar(select(DeliveryRecoveryEvent).where(DeliveryRecoveryEvent.action == 'recovery_activated'))
        assert event.details['deferred_reconciliation'] is True and event.details['undecided_holds'] == 1
        assert db.scalar(select(DeliveryGeneration.state).where(DeliveryGeneration.generation == event.generation)) == 'ACTIVE'
    provider = Recording()
    assert process_pending(provider) == 0 and provider.keys == [], 'deferred holds stay blocked'


def test_restored_data_fence_cannot_be_released_before_delivery_is_fenced(client):
    _, actor = admin_id(client)
    with SessionLocal() as db:
        db.add(RecoveryFence(id=1, state='QUARANTINED', backup_sha256=EVIDENCE))
        db.commit()
        with pytest.raises(recovery.RecoveryRefused, match='Declare delivery recovery'):
            recovery.release_restored_data(db, actor_id=actor, reason='Attempted early release of restored data')


def test_initialize_refuses_existing_history_and_cli_requires_quiescence(client, station):  # noqa: F811
    from app.delivery_recovery import main
    queued(client, station)
    with SessionLocal() as db:
        db.execute(DeliveryGeneration.__table__.delete())
        db.commit()
        with pytest.raises(recovery.RecoveryRefused, match='declare recovery'):
            recovery.initialize_empty(db)
    with pytest.raises(SystemExit):
        main(['declare', '--admin-id', '1', '--reason', 'Synthetic drill restore'])


def test_health_reports_the_fence_without_blocking_readiness(client, station):  # noqa: F811
    from app.services.operations_health import diagnostics
    _, actor = admin_id(client)
    queued(client, station)
    declare(actor)
    with SessionLocal() as db:
        result = diagnostics(db, get_settings())
    component = next(c for c in result['components'] if c['name'] == 'delivery_recovery')
    assert component['code'] == 'DELIVERY_RECOVERY_FENCED' and component['required'] is False
    assert component['undecided_holds'] == 1
    queue = next(c for c in result['components'] if c['name'] == 'notifications')
    assert queue['pending'] == 0, 'held rows are reported as holds, not as an aging queue'


# --- Exercise isolation ---------------------------------------------------------------------

def test_exercise_deliveries_are_held_separately_and_never_become_operational(client, monkeypatch):
    from test_exercise_notifications import allowlist, device_for, new_session, opt_in
    from test_exercise_notifications import send as exercise_send
    from app.services.exercise_notifications import process_pending as exercise_process, provider_send_problem, exercise_message
    monkeypatch.setattr(get_settings(), 'exercise_notifications_enabled', True)
    admin = staff(client)
    with SessionLocal() as db:
        actor = db.scalar(select(User.id).where(User.email == 'admin@example.com'))
    access, device_id = device_for(client, 'tester@example.com', 1)
    opt_in(client, access, device_id)
    session_id = new_session(client, admin)
    assert allowlist(client, admin, session_id, device_id).status_code == 200
    assert exercise_send(client, admin, session_id, device_id).status_code == 200
    declare(actor)
    hold, = holds()
    assert hold.kind == 'exercise_manual' and hold.original_state == 'PENDING'
    provider = FakeNotificationProvider()
    with pytest.raises(recovery.DeliveryFenced):
        exercise_process(provider)
    with pytest.raises(recovery.DeliveryFenced):
        process_pending(provider)  # The operational worker never touches exercise rows either.
    activate(actor, allow_undecided=True)
    assert exercise_process(provider) == 0 and provider.messages == {}
    with SessionLocal() as db:
        row = db.scalar(select(ExerciseDelivery))
        assert (row.state, row.message_type) == ('PENDING', 'EXERCISE_TEST') and db.scalar(select(NotificationDelivery)) is None
        row.state, row.attempts = 'PROCESSING', 1  # Even a forged claim is refused at the provider gate.
        db.commit()
        problem = provider_send_problem(exercise_message(session_id, row.id), 'synthetic-exercise-token-1', 'exercise:' + row.id)
    assert problem == ('rejected', 'recovery_fenced')


def test_ledger_is_safe_under_concurrent_writer_and_reader_processes(tmp_path):
    """Four OS processes each record 150 increasing claims in their own file while reading
    every peer's file; no reader may ever see an unreadable or missing entry."""
    import subprocess
    import sys
    from pathlib import Path
    recovery.Ledger(tmp_path).anchor('00000000-0000-4000-8000-0000000000aa', 0)
    script = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from app.services.delivery_recovery import Ledger, DeliveryFenced\n"
        "ledger = Ledger(sys.argv[2]); offset = int(sys.argv[3]); failures = 0\n"
        "for n in range(1, 151):\n"
        "    ledger.record('00000000-0000-4000-8000-0000000000aa', n * 4 + offset)\n"
        "    try:\n"
        "        assert all(t == '00000000-0000-4000-8000-0000000000aa' for t, _ in ledger.entries())\n"
        "    except DeliveryFenced:\n"
        "        failures += 1\n"
        "print(failures)\n")
    backend = str(Path(__file__).resolve().parents[1])
    processes = [subprocess.Popen([sys.executable, '-c', script, backend, str(tmp_path), str(i)], stdout=subprocess.PIPE, text=True)
                 for i in range(4)]
    outputs = [p.communicate(timeout=120)[0].strip() for p in processes]
    assert [p.returncode for p in processes] == [0, 0, 0, 0] and outputs == ['0'] * 4, outputs
    entries = recovery.Ledger(tmp_path).entries()
    assert max(seq for _, seq in entries) == 150 * 4 + 3 and len(entries) == 5, 'anchor + one file per process'
    assert not list(tmp_path.glob('*.tmp-*')), 'no temporary files left behind'


def test_ledger_written_by_another_host_fails_closed(client, station, tmp_path, monkeypatch):  # noqa: F811
    """Multi-host send coordination is unproven, so a peer host's ledger entry refuses delivery."""
    import json as _json
    ledger = tmp_path / 'ledger'
    monkeypatch.setattr(get_settings(), 'delivery_ledger_path', str(ledger))
    queued(client, station)
    anchor(ledger)
    assert _json.loads((ledger / 'anchor.json').read_text())['host'] == recovery.HOST
    token = _json.loads((ledger / 'anchor.json').read_text())['token']
    (ledger / 'worker-otherhost.json').write_text(_json.dumps(dict(token=token, seq=0, host=recovery.HOST + '-peer')))
    provider = Recording()
    with pytest.raises(recovery.DeliveryFenced, match='another host'):
        process_pending(provider)
    assert provider.keys == [] and deliveries()[0].state == 'PENDING'


@pytest.mark.parametrize('mode,windows,refused', [(0o40700, False, False), (0o40750, False, False), (0o40770, False, True),
                                                   (0o40777, False, True), (0o40777, True, False)])
def test_ledger_directory_must_not_be_writable_by_others_on_posix(mode, windows, refused):
    assert bool(recovery.permission_problem(mode, windows)) is refused
