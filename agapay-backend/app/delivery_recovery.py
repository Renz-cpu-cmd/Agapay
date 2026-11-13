"""Offline operator tool for restored-delivery recovery (R2 P0). See docs/delivery-recovery.md.

Run on the worker host (it owns AGAPAY_DELIVERY_LEDGER_PATH) with send-capable workers
stopped. Every mutating command records an active administrator id and a reason.

  python -m app.delivery_recovery status
  python -m app.delivery_recovery holds [--undecided]
  python -m app.delivery_recovery initialize                       # empty database only
  python -m app.delivery_recovery declare --admin-id N --reason "..." --workers-stopped
  python -m app.delivery_recovery decide --admin-id N --hold-id H --expected-version V \\
        --decision not_delivered --evidence-kind provider_record --evidence-sha256 <sha256> --reason "..."
  python -m app.delivery_recovery release-restored-data --admin-id N --reason "..."
  python -m app.delivery_recovery activate --admin-id N --reason "..." --workers-stopped [--defer-reconciliation]

No command re-queues or resends a held delivery. Output never includes tokens or secrets.
"""
import argparse
import json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    listing = commands.add_parser('holds')
    listing.add_argument('--undecided', action='store_true')
    listing.add_argument('--limit', type=int, default=100, choices=range(1, 501), metavar='1-500')
    commands.add_parser('initialize')
    for name in ('declare', 'decide', 'release-restored-data', 'activate'):
        command = commands.add_parser(name)
        command.add_argument('--admin-id', type=int, required=True)
        command.add_argument('--reason', required=True)
        if name in ('declare', 'activate'):
            command.add_argument('--workers-stopped', action='store_true')
        if name == 'activate':
            command.add_argument('--defer-reconciliation', action='store_true',
                                 help='Open new-generation delivery while some holds are undecided (they stay blocked)')
        if name == 'decide':
            command.add_argument('--hold-id', type=int, required=True)
            command.add_argument('--expected-version', type=int, required=True)
            command.add_argument('--decision', required=True, choices=('provider_accepted', 'not_delivered', 'outcome_unknown', 'superseded'))
            command.add_argument('--evidence-kind', required=True, choices=('provider_record', 'no_provider_record', 'operator_review'))
            command.add_argument('--evidence-sha256', required=True)
    args = parser.parse_args(argv)
    if args.command in ('declare', 'activate') and not args.workers_stopped:
        parser.error(f'{args.command} requires --workers-stopped (stop notification and exercise workers first)')
    from app.database import SessionLocal
    from app.migrations import require_current
    from app.database import engine
    from app.services import delivery_recovery as recovery
    require_current(engine)
    with SessionLocal() as db:
        try:
            if args.command == 'status':
                result = recovery.status(db)
            elif args.command == 'holds':
                result = recovery.list_holds(db, undecided_only=args.undecided, limit=args.limit)
            elif args.command == 'initialize':
                result = dict(generation=recovery.initialize_empty(db).generation, state='ACTIVE')
            elif args.command == 'declare':
                generation = recovery.declare(db, kind='declared', reason=args.reason, actor_id=args.admin_id)
                result = dict(generation=generation.generation, state=generation.state, held=generation.held_count)
            elif args.command == 'decide':
                result = recovery.hold_view(recovery.decide(
                    db, args.hold_id, actor_id=args.admin_id, decision=args.decision, evidence_kind=args.evidence_kind,
                    evidence_sha256=args.evidence_sha256, reason=args.reason, expected_version=args.expected_version))
            elif args.command == 'release-restored-data':
                recovery.release_restored_data(db, actor_id=args.admin_id, reason=args.reason)
                result = dict(restored_data='RELEASED', external_delivery='still fenced until activation')
            else:
                generation = recovery.activate(db, actor_id=args.admin_id, reason=args.reason,
                                               allow_undecided=args.defer_reconciliation)
                result = dict(generation=generation.generation, state=generation.state)
            db.commit()
        except (recovery.RecoveryRefused, recovery.DeliveryFenced) as error:
            db.rollback()
            raise SystemExit(f'Refused: {error}') from None
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
