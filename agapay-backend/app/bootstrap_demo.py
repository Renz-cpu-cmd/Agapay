"""Explicit development-only demo bootstrap; never called by API startup."""
import argparse
from app.config import get_settings
from app.database import engine, SessionLocal
from app.migrations import require_current
from app.seed import seed_demo_station


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if get_settings().environment != 'development':
        raise SystemExit('Demo bootstrap is permitted only in development')
    require_current(engine)
    if not args.apply:
        print('Review app/seed.py; --apply explicitly creates/updates demo station metadata')
        return
    with SessionLocal() as db:
        seed_demo_station(db)
    print('Development demo station bootstrapped explicitly')


if __name__ == '__main__':
    main()
