"""Explicit rain maintenance. Never auto-archives or overwrites a restore target."""
import argparse,sqlite3,json,shutil
from contextlib import closing
from pathlib import Path
from app.services.rain_gauge_service import RainGaugeStore
from app.services.rain_rollups import upgrade
from app.services.rain_archive import archive_batch,verify,backup,verify_bundle


def main():
    from app.config import get_settings
    settings=get_settings()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['upgrade','archive','verify','backup','verify-backup','restore'])
    parser.add_argument('--path',required=True,type=Path)
    parser.add_argument('--destination',type=Path)
    parser.add_argument('--retention-days',type=int,default=settings.rain_raw_retention_days)
    parser.add_argument('--limit',type=int,default=settings.rain_archive_batch)
    args=parser.parse_args()
    if args.action=='upgrade':
        if not args.path.is_file():raise ValueError('Existing journal required; take a backup and stop writers first')
        with closing(sqlite3.connect(args.path)) as db:
            db.row_factory=sqlite3.Row;upgrade(db)
        print('Rain journal upgraded; original rows preserved');return
    if args.action in ('verify-backup','restore'):
        result=verify_bundle(args.path)
        if args.action=='restore':
            if not args.destination or args.destination.exists():raise ValueError('Restore destination must be new')
            shutil.copytree(args.path,args.destination);result=verify_bundle(args.destination)
        print(json.dumps(result));return
    store=RainGaugeStore(args.path,read_only=args.action!='archive',raw_retention_days=args.retention_days)
    if args.action=='archive':
        result=archive_batch(store,args.destination or Path(settings.rain_archive_directory),limit=args.limit)
    elif args.action=='backup':
        if not args.destination:raise ValueError('New backup destination required')
        result=backup(store,args.destination)
    else:result=verify(store)
    print(json.dumps(result))


if __name__=='__main__':main()
