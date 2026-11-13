"""Create additive F09-F11 tables. Never infer subscriptions or public authority."""
import argparse
from sqlalchemy import inspect
from app.database import engine
from app.governance_models import TABLES


def migrate(bind, *, apply=False):
    inspector = inspect(bind)
    if not all(inspector.has_table(name) for name in ("stations", "telemetry", "alerts", "users", "notification_events", "notification_deliveries")):
        raise ValueError("Initialize core alert and notification tables first")
    missing = [table.name for table in TABLES if not inspector.has_table(table.name)]
    if apply:
        for table in TABLES:
            table.create(bind, checkfirst=True)
    return missing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(("Created: " if args.apply else "Missing: ") + (", ".join(migrate(engine, apply=args.apply)) or "none"))
    print("No residents subscribed, authority granted, official notice issued or external notification sent.")
