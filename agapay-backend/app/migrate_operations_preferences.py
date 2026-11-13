"""Create lifecycle/preference tables only; preserve every existing row and subscription."""
import argparse
from sqlalchemy import inspect
from app.database import engine
from app.operations_models import TABLES
from app import governance_models


def migrate(bind,*,apply=False):
    inspector=inspect(bind)
    if any(not inspector.has_table(name) for name in ('stations','users','notification_events','verified_areas')):
        raise ValueError('Apply station, notification and governance schema prerequisites first')
    missing=[t.name for t in TABLES if not inspector.has_table(t.name)]
    if apply:
        for table in TABLES:table.create(bind,checkfirst=True)
    return missing


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(migrate(engine,apply=args.apply))
