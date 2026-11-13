"""Explicit offline registration; never approves, publishes or seeds a model."""
import argparse,json
from pathlib import Path
from app.database import SessionLocal
from app.models import User
from app.services.forecast_registry import register
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',required=True,type=Path);parser.add_argument('--admin-id',required=True,type=int);args=parser.parse_args()
    if args.bundle.stat().st_size>4*1024*1024:raise ValueError('Bundle exceeds 4 MiB')
    with SessionLocal() as db:
        user=db.get(User,args.admin_id)
        if not user:raise ValueError('Unknown administrator')
        print('Registered draft model:',register(db,user,json.loads(args.bundle.read_text(encoding='utf-8'))))
if __name__=='__main__':main()
