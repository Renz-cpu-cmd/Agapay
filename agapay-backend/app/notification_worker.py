"""Explicit bounded worker: python -m app.notification_worker --limit 50."""
import argparse
import logging

from app.config import get_settings
from app.services.notification_provider import configured_provider
from app.services.notification_service import process_pending


def main():
    parser = argparse.ArgumentParser(description="Process one notification batch (disabled by default).")
    parser.add_argument("--limit", type=int, default=50, choices=range(1, 101), metavar="1..100")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        provider = configured_provider(get_settings())
    except ValueError as exc:
        parser.error(str(exc))
    logging.info("Notification batch processed=%s provider=%s",
                 process_pending(provider, limit=args.limit), provider.mode)


if __name__ == "__main__":
    main()
