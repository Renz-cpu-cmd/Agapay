"""Fail-closed recovery fence for external notification delivery (R2 P0).

Problem: a backup can capture a delivery as PENDING (or PROCESSING / retry-scheduled
FAILED). If that delivery is sent after the backup and the backup is later restored, the
restored row looks unsent and an unmodified worker sends it again. Neither the provider
(FCM has no idempotency key) nor database uniqueness can prevent that duplicate.

Policy (no blind replay):
* Every claim that can reach a provider takes a ticket from the single ACTIVE delivery
  generation, in the claim transaction. No ACTIVE generation, more than one open
  generation, or missing metadata => no claim (fail closed).
* Restore detection does not rely only on the restored rows:
    - PostgreSQL database identity (cluster system identifier + database OID) is bound at
      activation; a pg_restore into another database, cluster or re-created database
      no longer matches.
    - An external ledger (``delivery_ledger_path``, a directory outside the database and
      its backups) records each claim sequence BEFORE the claim commits and before any
      provider call. A restored database carries an older generation token or a claim
      sequence at or below the ledger high-water mark, so its next claim is refused.
      Required in production; outside production it is optional ("unwitnessed").
* Recovery is declared (automatically by app.recovery.restore, or by an operator): a new
  RECOVERING generation holds every delivery whose outcome may have become unknowable.
  Delivery rows are NOT rewritten. A hold is never released for resend; an operator
  decision closes it with evidence. Nothing is claimable until an operator activates the
  new generation, which anchors the ledger and re-binds the database identity.
* Work created after activation is new-generation work and passes every normal freshness
  and eligibility check at claim time. Exactly-once external delivery is NOT claimed.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import stat
import time
from uuid import uuid4

from sqlalchemy import String, cast, exists, func, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from app.exercise_models import ExerciseDelivery, ExerciseSensorDelivery
from app.models import NotificationDelivery, User, utc_now
from app.recovery_models import DeliveryGeneration, DeliveryHold, DeliveryRecoveryEvent
from app.services.station_security import utc

KINDS = {'operational': NotificationDelivery, 'exercise_manual': ExerciseDelivery, 'exercise_sensor': ExerciseSensorDelivery}
REASONS = {
    'PENDING': 'pending_at_boundary',
    'PROCESSING': 'in_flight_at_boundary',
    'FAILED': 'retry_scheduled_at_boundary',
    'UNKNOWN': 'provider_outcome_unknown',
}
EXPLANATIONS = {
    'pending_at_boundary': 'Queued when recovery was declared. It may have been sent after the backup was taken; '
                           'a restored database cannot tell. Never resent automatically.',
    'in_flight_at_boundary': 'Claimed by a worker when recovery was declared. The provider may have accepted it. '
                             'Never resent automatically.',
    'retry_scheduled_at_boundary': 'Waiting for a retry when recovery was declared. A later retry may already have '
                                   'been accepted. Never resent automatically.',
    'provider_outcome_unknown': 'The provider outcome was already unknown. Never retried automatically.',
}
# decision -> accepted evidence kinds. Every decision closes the hold; none re-queues.
DECISIONS = {
    'provider_accepted': ('provider_record',),
    'not_delivered': ('provider_record',),
    'outcome_unknown': ('provider_record', 'no_provider_record'),
    'superseded': ('operator_review',),
}
_SHA256 = re.compile(r'^[0-9a-f]{64}$')


class DeliveryFenced(RuntimeError):
    """External delivery is not permitted; the message is safe for operator logs."""


class RecoveryRefused(RuntimeError):
    """An operator recovery action was refused; the message is safe for operator output."""


def _settings(settings):
    if settings is None:
        from app.config import get_settings
        settings = get_settings()
    return settings


def not_held(kind, id_column):
    """Claim filter: the row has no recovery hold (holds are never removed)."""
    return ~exists(select(DeliveryHold.id).where(DeliveryHold.kind == kind,
                                                 DeliveryHold.delivery_id == cast(id_column, String)))


def database_identity(db):
    """PostgreSQL cluster + database identity; None on SQLite (the ledger covers SQLite)."""
    if db.get_bind().dialect.name != 'postgresql':
        return None
    return db.execute(text("SELECT (SELECT system_identifier::text FROM pg_control_system()) || ':' || "
                           "(SELECT oid::text FROM pg_database WHERE datname = current_database())")).scalar_one()


# --- External ledger --------------------------------------------------------------------

class Ledger:
    """Directory of small JSON files, one per writer process, outside the database.

    A worker writes ONLY its own file (atomic replace + fsync), so concurrent workers need
    no file lock; the high-water mark is the maximum over all files. Activation retires
    every file and writes an anchor for the new generation token.
    """

    def __init__(self, path):
        self.root = Path(path)
        self._own = None

    def entries(self):
        if not self.root.is_dir():
            raise DeliveryFenced('External delivery ledger is unavailable; restoration status cannot be established')
        problem = permission_problem(self.root.stat().st_mode, os.name == 'nt')
        if problem:
            raise DeliveryFenced(problem)
        values = []
        for path in sorted(self.root.glob('*.json')):
            try:
                value = json.loads(_transient(lambda: path.read_text(encoding='utf-8')))
                values.append((str(value['token']), int(value['seq'])))
                writer = value.get('host')
            except FileNotFoundError:
                continue  # Retired by an activation between listing and reading.
            except (OSError, ValueError, KeyError, TypeError):
                raise DeliveryFenced('External delivery ledger entry is unreadable; restoration status cannot be established') from None
            if writer is not None and writer != HOST:
                # Multi-host send coordination is not demonstrated; refuse rather than assume it.
                raise DeliveryFenced('External delivery ledger was written by another host; run send-capable workers on one host')
        if not values:
            raise DeliveryFenced('External delivery ledger is empty; activate a recovery generation to anchor it')
        return values

    def _write(self, path, value):
        temporary = path.with_name(path.stem + '.tmp-' + uuid4().hex)
        with open(temporary, 'x', encoding='utf-8') as handle:
            handle.write(json.dumps(value))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            _transient(lambda: os.replace(temporary, path))
        except OSError:
            temporary.unlink(missing_ok=True)
            raise DeliveryFenced('External delivery ledger write failed; no claim was committed') from None
        if os.name != 'nt':  # POSIX: persist the rename itself (NTFS journals metadata; no directory handle fsync)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

    def record(self, token, seq):
        if self._own is None:
            self._own = self.root / ('worker-' + uuid4().hex + '.json')
        self._write(self._own, dict(token=token, seq=seq, host=HOST, recorded_at=datetime.now(timezone.utc).isoformat()))

    def anchor(self, token, seq):
        self.root.mkdir(parents=True, exist_ok=True)
        existing = list(self.root.glob('*.json'))
        if existing:
            retired = self.root / 'retired' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8])
            retired.mkdir(parents=True)
            for path in existing:
                os.replace(path, retired / path.name)
        self._write(self.root / 'anchor.json', dict(token=token, seq=seq, host=HOST, anchored_at=datetime.now(timezone.utc).isoformat()))


_ledgers = {}
HOST = socket.gethostname()


def permission_problem(mode, windows):
    """POSIX: the ledger directory must not be writable by group or others (Windows uses ACLs)."""
    if not windows and stat.S_IMODE(mode) & 0o022:
        return 'External delivery ledger directory is writable by other users; restrict it to the service account'
    return None


def _transient(operation, attempts=50, pause=0.01):
    """Retry a Windows sharing violation (a peer is replacing/reading the same small file).

    POSIX rename is atomic for readers; Windows briefly refuses opening a file that another
    process is replacing, and refuses replacing a file another process has open. Bounded to
    about half a second; anything persistent still fails closed.
    """
    for attempt in range(attempts):
        try:
            return operation()
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(pause)


def ledger_for(settings=None):
    settings = _settings(settings)
    if not settings.delivery_ledger_path:
        if settings.environment == 'production':
            raise DeliveryFenced('Production delivery requires AGAPAY_DELIVERY_LEDGER_PATH (external restore witness)')
        return None
    key = str(Path(settings.delivery_ledger_path).resolve())
    return _ledgers.setdefault(key, Ledger(key))


# --- Claim boundary -----------------------------------------------------------------------

def open_generations(db, *, lock=False):
    query = select(DeliveryGeneration).where(DeliveryGeneration.state != 'SUPERSEDED').order_by(DeliveryGeneration.generation)
    return list(db.scalars(query.with_for_update() if lock else query))


def check_open(db, settings=None):
    """Raise DeliveryFenced unless external delivery may proceed. Read-only."""
    settings = _settings(settings)
    try:
        rows = open_generations(db)
        identity = database_identity(db)
    except SQLAlchemyError:
        db.rollback()
        raise DeliveryFenced('Delivery recovery metadata is unavailable; apply migration 0008 and initialize it') from None
    if not rows:
        raise DeliveryFenced('Delivery recovery generation is not initialized')
    if len(rows) != 1:
        raise DeliveryFenced('More than one open delivery recovery generation; operator review required')
    generation = rows[0]
    if generation.state != 'ACTIVE':
        raise DeliveryFenced(f'Delivery recovery generation {generation.generation} is {generation.state}; '
                             'reconcile held deliveries and activate it')
    if generation.database_identity != identity:
        raise DeliveryFenced('Database identity differs from the one bound at activation (restored or copied database)')
    ledger = ledger_for(settings)
    if ledger is not None and any(token != generation.token for token, _ in ledger.entries()):
        raise DeliveryFenced('Database delivery generation does not match the external ledger (older backup restored?)')
    return generation


@dataclass
class Ticket:
    generation: int
    token: str
    seq: int
    ledger: Ledger | None


def take_ticket(db, settings=None):
    """Inside the claim transaction, BEFORE the delivery row is claimed.

    Locks the ACTIVE generation row (serializing claims) and advances its claim sequence.
    The caller claims the delivery row in the same transaction and then calls witness()
    before committing. Any DeliveryFenced => roll back; nothing reaches a provider.
    """
    generation = check_open(db, settings)
    seq = db.execute(update(DeliveryGeneration)
                     .where(DeliveryGeneration.generation == generation.generation, DeliveryGeneration.state == 'ACTIVE')
                     .values(claim_seq=DeliveryGeneration.claim_seq + 1)
                     .returning(DeliveryGeneration.claim_seq)
                     .execution_options(synchronize_session=False)).scalar()
    if seq is None:
        raise DeliveryFenced('Delivery recovery generation changed during the claim')
    return Ticket(generation.generation, generation.token, int(seq), ledger_for(settings))


def witness(ticket):
    """After the claim UPDATE and BEFORE commit: the external ledger must not be ahead."""
    if ticket.ledger is None:
        return
    entries = ticket.ledger.entries()
    if any(token != ticket.token for token, _ in entries):
        raise DeliveryFenced('Database delivery generation does not match the external ledger (older backup restored?)')
    if ticket.seq <= max(seq for _, seq in entries):
        raise DeliveryFenced('Database claim sequence is at or behind the external ledger (restored or rolled-back database)')
    ticket.ledger.record(ticket.token, ticket.seq)


def still_open(db, ticket):
    """Final re-check immediately before the provider call."""
    return db.scalar(select(DeliveryGeneration.state).where(DeliveryGeneration.generation == ticket.generation)
                     .execution_options(populate_existing=True)) == 'ACTIVE'


# --- Operator workflow ---------------------------------------------------------------------

def _event(db, generation, action, actor_id, **details):
    db.add(DeliveryRecoveryEvent(generation=generation, action=action, actor_id=actor_id, details=details))


def _admin(db, actor_id):
    if actor_id is None:
        raise RecoveryRefused('An active administrator must be recorded for this recovery action')
    user = db.get(User, actor_id, populate_existing=True)
    if user is None or not user.is_active or user.role != 'admin':
        raise RecoveryRefused('An active administrator must be recorded for this recovery action')
    return user


def _reason(reason):
    reason = (reason or '').strip()
    if not 10 <= len(reason) <= 500:
        raise RecoveryRefused('Record a reason of 10 to 500 characters')
    return reason


def _unsettled(kind, model):
    condition = model.state.in_(('PENDING', 'PROCESSING', 'UNKNOWN'))
    if kind == 'operational':
        from app.delivery_models import DeliveryControl
        closed = exists(select(DeliveryControl.delivery_id).where(
            DeliveryControl.delivery_id == model.id,
            DeliveryControl.review_status.in_(('provider_accepted', 'not_accepted', 'closed_no_resend'))))
        condition = (condition | ((model.state == 'FAILED') & model.completed_at.is_(None))) & ~closed
    return condition


def declare(db, *, kind, reason, actor_id=None, source_backup_sha256=None):
    """Open a RECOVERING generation and hold every delivery whose outcome may be unknowable.

    Supersedes the previous generation in the same transaction, so no claim can commit
    under it afterwards. The caller commits. Delivery rows are not modified.
    """
    if kind not in ('restore', 'declared', 'initialize'):
        raise RecoveryRefused('Unknown recovery kind')
    if kind == 'declared':
        _admin(db, actor_id)
    reason = _reason(reason)
    if source_backup_sha256 is not None and not _SHA256.fullmatch(source_backup_sha256):
        raise RecoveryRefused('Backup reference must be a SHA-256 hex digest')
    existing = list(db.scalars(select(DeliveryGeneration).order_by(DeliveryGeneration.generation).with_for_update()))
    for row in existing:
        if row.state != 'SUPERSEDED':
            row.state = 'SUPERSEDED'
    number = (existing[-1].generation if existing else 0) + 1
    generation = DeliveryGeneration(generation=number, token=str(uuid4()), state='RECOVERING', kind=kind, reason=reason,
                                    source_backup_sha256=source_backup_sha256, declared_by=actor_id, claim_seq=0)
    db.add(generation)
    db.flush()
    counts = {}
    for name, model in KINDS.items():
        rows = list(db.scalars(select(model).where(_unsettled(name, model), not_held(name, model.id)).order_by(model.id)))
        for row in rows:
            db.add(DeliveryHold(generation=number, kind=name, delivery_id=str(row.id), original_state=row.state,
                                original_attempts=row.attempts,
                                original_result=getattr(row, 'result_category', None) or getattr(row, 'outcome', None),
                                original_created_at=row.created_at, original_attempted_at=row.attempted_at,
                                reason_code=REASONS[row.state]))
            counts[f'{name}:{row.state}'] = counts.get(f'{name}:{row.state}', 0) + 1
    generation.held_count = sum(counts.values())
    _event(db, number, 'recovery_declared', actor_id, kind=kind, reason=reason, held=counts,
           superseded=[row.generation for row in existing if row.generation != number],
           source_backup_sha256=source_backup_sha256)
    db.flush()
    return generation


def decide(db, hold_id, *, actor_id, decision, evidence_kind, evidence_sha256, reason, expected_version):
    """Close one hold with operator evidence. Never changes the delivery row; never resends."""
    _admin(db, actor_id)
    reason = _reason(reason)
    if decision not in DECISIONS:
        raise RecoveryRefused('Unknown reconciliation decision')
    if evidence_kind not in DECISIONS[decision]:
        raise RecoveryRefused(f'Decision {decision} requires evidence: {", ".join(DECISIONS[decision])}')
    if not _SHA256.fullmatch(evidence_sha256 or ''):
        raise RecoveryRefused('Evidence reference must be a SHA-256 hex digest of the retained evidence')
    changed = db.execute(update(DeliveryHold).where(DeliveryHold.id == hold_id, DeliveryHold.version == expected_version,
                                                     DeliveryHold.decision.is_(None))
                         .values(decision=decision, evidence_kind=evidence_kind, evidence_sha256=evidence_sha256,
                                 decision_reason=reason, decided_by=actor_id, decided_at=utc_now(),
                                 version=DeliveryHold.version + 1)
                         .execution_options(synchronize_session=False))
    hold = db.get(DeliveryHold, hold_id, populate_existing=True)
    if hold is None:
        raise RecoveryRefused('Held delivery not found')
    if changed.rowcount != 1:
        raise RecoveryRefused('Held delivery changed or was already decided; refresh and review')
    _event(db, hold.generation, 'hold_decided', actor_id, hold_id=hold.id, kind=hold.kind, delivery_id=hold.delivery_id,
           decision=decision, evidence_kind=evidence_kind, evidence_sha256=evidence_sha256, reason=reason)
    return hold


def activate(db, *, actor_id, reason, settings=None, allow_undecided=False):
    """Open new-generation delivery. Holds stay closed to resend whatever is decided."""
    settings = _settings(settings)
    _admin(db, actor_id)
    reason = _reason(reason)
    from app.services.privacy_governance import require_released
    try:
        require_released(db)
    except RuntimeError:
        raise RecoveryRefused('Release the restored-data fence first (privacy withdrawals reconciled)') from None
    rows = open_generations(db, lock=True)
    if len(rows) != 1 or rows[0].state != 'RECOVERING':
        raise RecoveryRefused('Exactly one RECOVERING generation is required; declare recovery first')
    generation = rows[0]
    undecided = db.scalar(select(func.count()).select_from(DeliveryHold).where(DeliveryHold.decision.is_(None)))
    if undecided and not allow_undecided:
        raise RecoveryRefused(f'{undecided} held deliveries are undecided; decide them or explicitly defer '
                              '(they stay blocked from resend either way)')
    ledger = ledger_for(settings)
    generation.database_identity = database_identity(db)
    generation.state = 'ACTIVE'
    generation.activated_by = actor_id
    generation.activated_at = utc_now()
    _event(db, generation.generation, 'recovery_activated', actor_id, reason=reason, undecided_holds=undecided,
           deferred_reconciliation=bool(undecided), ledger='anchored' if ledger else 'not_configured',
           database_identity_bound=generation.database_identity is not None)
    db.flush()
    if ledger is not None:
        ledger.anchor(generation.token, generation.claim_seq)  # Before commit: a failure leaves it RECOVERING.
    return generation


def initialize_empty(db, settings=None):
    """First generation for a database with no delivery history at all (fresh install/tests).

    Anything else must use declare() + activate() so existing work is held first.
    """
    if db.scalar(select(func.count()).select_from(DeliveryGeneration)):
        raise RecoveryRefused('Delivery recovery is already initialized')
    for model in KINDS.values():
        if db.scalar(select(func.count()).select_from(model)):
            raise RecoveryRefused('Deliveries already exist; declare recovery and activate it instead')
    ledger = ledger_for(settings)
    generation = DeliveryGeneration(generation=1, token=str(uuid4()), state='ACTIVE', kind='initialize',
                                    reason='Initialized on a database with no delivery history', claim_seq=0,
                                    database_identity=database_identity(db), activated_at=utc_now())
    db.add(generation)
    _event(db, 1, 'initialized_empty', None, ledger='anchored' if ledger else 'not_configured')
    db.flush()
    if ledger is not None:
        ledger.anchor(generation.token, 0)
    return generation


def release_restored_data(db, *, actor_id, reason):
    """Release the restored-data (privacy) fence so the API and ingestion can serve.

    Delivery stays fenced: a RECOVERING generation must already hold the restored work.
    """
    from app.privacy_models import RecoveryFence
    from app.services.privacy import evidence
    actor = _admin(db, actor_id)
    reason = _reason(reason)
    fence = db.get(RecoveryFence, 1, with_for_update=True)
    if fence is None or fence.state == 'RELEASED':
        raise RecoveryRefused('No restored-data fence is active')
    rows = open_generations(db)
    if len(rows) != 1 or rows[0].state != 'RECOVERING':
        raise RecoveryRefused('Declare delivery recovery before releasing restored data')
    fence.state = 'RELEASED'
    evidence(db, actor, fence.backup_sha256, 'restore_released', reason=reason,
             attestation='privacy withdrawals reconciled; external delivery remains fenced')
    _event(db, rows[0].generation, 'restored_data_released', actor_id, reason=reason)


def status(db, settings=None):
    settings = _settings(settings)
    try:
        rows = open_generations(db)
    except SQLAlchemyError:
        db.rollback()
        return dict(state='UNAVAILABLE', open=False, reason='Delivery recovery metadata is unavailable', generation=None,
                    held={}, undecided=0, ledger='configured' if settings.delivery_ledger_path else 'not_configured')
    try:
        check_open(db, settings)
        problem = None
    except DeliveryFenced as error:
        problem = str(error)
    current = rows[-1] if rows else None
    counts = {}
    for kind, decision, total in db.execute(select(DeliveryHold.kind, DeliveryHold.decision, func.count())
                                            .group_by(DeliveryHold.kind, DeliveryHold.decision)):
        counts.setdefault(kind, {})[decision or 'undecided'] = total
    return dict(state=current.state if current else 'UNINITIALIZED', open=problem is None, reason=problem,
                generation=current.generation if current else None, kind=current.kind if current else None,
                declared_at=utc(current.declared_at).isoformat() if current else None,
                activated_at=utc(current.activated_at).isoformat() if current and current.activated_at else None,
                held=counts, undecided=sum(v.get('undecided', 0) for v in counts.values()),
                ledger='configured' if settings.delivery_ledger_path else 'not_configured',
                database_identity_bound=bool(current and current.database_identity),
                notice='Held deliveries are never resent automatically. Provider acceptance does not prove phone display.')


def hold_view(hold):
    return dict(id=hold.id, generation=hold.generation, kind=hold.kind, delivery_id=hold.delivery_id,
                original_state=hold.original_state, original_attempts=hold.original_attempts,
                original_result=hold.original_result, original_created_at=utc(hold.original_created_at).isoformat(),
                original_attempted_at=utc(hold.original_attempted_at).isoformat() if hold.original_attempted_at else None,
                reason_code=hold.reason_code, explanation=EXPLANATIONS[hold.reason_code], held_at=utc(hold.held_at).isoformat(),
                version=hold.version, decision=hold.decision, evidence_kind=hold.evidence_kind,
                evidence_sha256=hold.evidence_sha256, decision_reason=hold.decision_reason, decided_by=hold.decided_by,
                decided_at=utc(hold.decided_at).isoformat() if hold.decided_at else None, resend='never')


def list_holds(db, *, undecided_only=False, before_id=None, limit=50):
    query = select(DeliveryHold).order_by(DeliveryHold.id.desc()).limit(limit)
    if undecided_only:
        query = query.where(DeliveryHold.decision.is_(None))
    if before_id:
        query = query.where(DeliveryHold.id < before_id)
    return [hold_view(hold) for hold in db.scalars(query)]
