"""Preserve telemetry IDs/FKs while enabling boot-scoped uniqueness (F03/F04).

Stop all application writers and take a database backup before --apply.
Default mode inspects only. Existing alerts/outbox/stations are never rewritten.
"""
import argparse

from sqlalchemy import MetaData, inspect
from sqlalchemy.schema import CreateTable

from app.database import engine
from app.models import StationTelemetryState, Telemetry, TelemetryBoot

NEW_COLUMNS = {"boot_id", "boot_sequence", "schema_version", "config_version", "source_id",
               "firmware_version", "measured_at", "received_at", "eligible_for_current", "disposition"}
LEGACY_COLUMNS = {"id", "station_id", "sequence_no", "water_depth_cm", "rainfall_mm",
                  "sensor_quality", "device_uptime_ms", "recorded_at"}


def needs_upgrade(bind):
    inspector = inspect(bind)
    if not inspector.has_table("telemetry"):
        return True
    columns = {c["name"] for c in inspector.get_columns("telemetry")}
    uniques = {tuple(c["column_names"]) for c in inspector.get_unique_constraints("telemetry")}
    return (not NEW_COLUMNS.issubset(columns)
            or ("station_id", "config_version", "boot_id", "sequence_no") not in uniques
            or ("station_id", "sequence_no") in uniques)


def require_ordering_schema(bind):
    if needs_upgrade(bind):
        raise RuntimeError("Telemetry ordering schema is outdated. Stop writers, back up the database, "
                           "then run python -m app.migrate_telemetry_ordering --apply.")


def migrate(bind, *, apply=False):
    inspector = inspect(bind)
    if not inspector.has_table("stations") or not inspector.has_table("telemetry"):
        raise ValueError("Initialize the core schema first; this migration never seeds data.")
    upgrade = needs_upgrade(bind)
    missing_tables = [t.name for t in (TelemetryBoot.__table__, StationTelemetryState.__table__)
                      if not inspector.has_table(t.name)]
    if not apply:
        return upgrade, missing_tables
    if upgrade:
        columns = {c["name"] for c in inspector.get_columns("telemetry")}
        if columns != LEGACY_COLUMNS:
            raise ValueError("Unexpected/partial telemetry schema; review it before migration.")
        if bind.dialect.name != "sqlite":
            raise ValueError("This preservation migration supports the project's SQLite database only.")
        # SQLite cannot drop an inline UNIQUE constraint. Build/copy/swap within
        # one explicit transaction, keeping IDs and every inbound reference.
        # Do not rename the old table (SQLite would rewrite inbound FK targets).
        with bind.connect() as connection:
            fk_enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
            connection.commit()
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
            try:
                connection.exec_driver_sql("BEGIN EXCLUSIVE")
                if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone() is not None:
                    raise ValueError("Existing foreign-key violations require review before migration.")
                # Re-read inside the exclusive lock; another migration may have finished.
                if needs_upgrade(connection):
                    before = connection.exec_driver_sql("SELECT COUNT(*) FROM telemetry").scalar()
                    triggers = connection.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='telemetry'"
                    ).fetchall()
                    extra_indexes = [i for i in inspect(connection).get_indexes("telemetry")
                                     if i["name"] not in {i.name for i in Telemetry.__table__.indexes}]
                    if triggers or extra_indexes:
                        raise ValueError("Custom telemetry triggers/indexes require a reviewed migration.")
                    metadata = MetaData()
                    # Resolve the stations FK when compiling the copied table.
                    Telemetry.__table__.metadata.tables["stations"].to_metadata(metadata)
                    target = Telemetry.__table__.to_metadata(metadata, name="telemetry_ordering_upgrade")
                    connection.execute(CreateTable(target))
                    names = ", ".join(sorted(LEGACY_COLUMNS))
                    connection.exec_driver_sql(
                        f"INSERT INTO telemetry_ordering_upgrade ({names}, received_at) "
                        f"SELECT {names}, recorded_at FROM telemetry")
                    after = connection.exec_driver_sql("SELECT COUNT(*) FROM telemetry_ordering_upgrade").scalar()
                    if before != after:
                        raise ValueError("Telemetry row count changed during migration")
                    connection.exec_driver_sql("DROP TABLE telemetry")
                    connection.exec_driver_sql("ALTER TABLE telemetry_ordering_upgrade RENAME TO telemetry")
                    for index in Telemetry.__table__.indexes:
                        index.create(connection)
                    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone() is not None:
                        raise ValueError("Foreign-key verification failed; migration rolled back")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.exec_driver_sql(f"PRAGMA foreign_keys={int(bool(fk_enabled))}")
                connection.commit()
    for table in (TelemetryBoot.__table__, StationTelemetryState.__table__):
        table.create(bind, checkfirst=True)
    return upgrade, missing_tables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changed, tables = migrate(engine, apply=args.apply)
    print(f"Telemetry upgrade {'applied' if args.apply else 'required'}: {changed}; "
          f"{'created' if args.apply else 'missing'} tables: {', '.join(tables) or 'none'}")


if __name__ == "__main__":
    main()
