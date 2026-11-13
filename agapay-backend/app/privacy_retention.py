"""Offline privacy retention. Dry-run is default; stop writers before explicit apply."""
import argparse
import json
from app.config import get_settings
from app.database import SessionLocal, engine
from app.migrations import require_current
from app.services.privacy import retain
from app.services.privacy_governance import approved_record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-with-writers-stopped', action='store_true')
    parser.add_argument('--limit', type=int, default=100, choices=range(1, 501))
    args = parser.parse_args()
    require_current(engine)
    if args.apply_with_writers_stopped and get_settings().environment == 'production':
        approved_record(get_settings().service_governance_path)
    with SessionLocal() as db:
        print(json.dumps(retain(db, apply=args.apply_with_writers_stopped, limit=args.limit), default=str, indent=2))


if __name__ == '__main__': main()
