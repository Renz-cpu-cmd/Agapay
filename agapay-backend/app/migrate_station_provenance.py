"""Add F05 provenance/exercise tables only; never infer trust from existing data."""
import argparse
from sqlalchemy import inspect
from app.database import engine
from app.migrate_telemetry_ordering import require_ordering_schema
from app.models import ExerciseTelemetry, StationSourceRegistry, TelemetryProvenance

TABLES = [StationSourceRegistry.__table__, TelemetryProvenance.__table__, ExerciseTelemetry.__table__]


def migrate(bind, *, apply=False):
    inspector = inspect(bind)
    if not all(inspector.has_table(t) for t in ("station_identities", "station_credentials", "telemetry")):
        raise ValueError("Apply F01/F02 and F03/F04 schema prerequisites first")
    require_ordering_schema(bind)
    missing = [t.name for t in TABLES if not inspector.has_table(t.name)]
    if apply:
        for table in TABLES:
            table.create(bind, checkfirst=True)
    return missing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(("Created: " if args.apply else "Missing: ") + (", ".join(migrate(engine, apply=args.apply)) or "none"))
    print("No source was automatically trusted. Recommission reviewed identities and replace old credentials.")
