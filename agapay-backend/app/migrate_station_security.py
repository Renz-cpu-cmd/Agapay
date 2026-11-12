"""Add only F01/F02 security tables; never reset or seed application data."""
import argparse

from sqlalchemy import inspect

from app.database import engine
from app.models import StationAuditEvent, StationCredential, StationIdentity, StationIngressBudget

TABLES = [StationIdentity.__table__, StationCredential.__table__,
          StationAuditEvent.__table__, StationIngressBudget.__table__]


def migrate(bind, *, apply: bool = False):
    inspector = inspect(bind)
    if not all(inspector.has_table(name) for name in ("stations", "users")):
        raise ValueError("Initialize the core application schema first; this command never seeds data.")
    missing = [table.name for table in TABLES if not inspector.has_table(table.name)]
    if apply:
        # Existing tables/columns/rows are left untouched. Repeating this is safe.
        for table in TABLES:
            table.create(bind, checkfirst=True)
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create missing security tables; default checks only")
    args = parser.parse_args()
    try:
        missing = migrate(engine, apply=args.apply)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print(("Created: " if args.apply else "Missing: ") + (", ".join(missing) or "none"))
    print("Station readings, accounts, alerts and notification rows were not changed.")


if __name__ == "__main__":
    main()
