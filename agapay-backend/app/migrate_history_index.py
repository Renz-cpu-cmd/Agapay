"""Add only the measured-time history index; preserve all application rows."""
import argparse
from sqlalchemy import Index, inspect
from app.database import engine
from app.models import Telemetry

INDEX = next(index for index in Telemetry.__table__.indexes if index.name == "ix_telemetry_station_measured_id")


def migrate(bind, *, apply=False):
    inspector = inspect(bind)
    if not inspector.has_table("telemetry") or "measured_at" not in {column["name"] for column in inspector.get_columns("telemetry")}:
        raise ValueError("Apply measured-time telemetry schema prerequisites first")
    missing = INDEX.name not in {index["name"] for index in inspector.get_indexes("telemetry")}
    if apply and missing:
        INDEX.create(bind, checkfirst=True)
    return missing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print("Index missing: " + str(migrate(engine, apply=args.apply)))
