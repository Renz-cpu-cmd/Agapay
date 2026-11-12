"""Preserve records and references while adding v3 rainfall/configuration metadata.

Stop writers and back up the database before --apply. Default mode inspects only.
"""
import argparse
from sqlalchemy import MetaData,inspect
from sqlalchemy.schema import CreateTable
from app.database import engine
from app.models import Telemetry
from app.device_config import StationConfiguration

NEW={"rainfall_interval","applied_config_hash","sensor_fault","local_alert_profile"}


def needs_upgrade(bind):
    inspector=inspect(bind)
    if not inspector.has_table("telemetry"):
        return True
    columns={c['name']:c for c in inspector.get_columns("telemetry")}
    return not NEW.issubset(columns) or not columns['rainfall_mm']['nullable']


def migrate(bind,*,apply=False):
    from app.migrate_telemetry_ordering import require_ordering_schema
    require_ordering_schema(bind)
    needed=needs_upgrade(bind)
    if not apply:
        return needed,not inspect(bind).has_table(StationConfiguration.__tablename__)
    if needed:
        if bind.dialect.name!="sqlite":
            raise ValueError("Use a reviewed dialect-specific migration; this preservation migration supports SQLite")
        with bind.connect() as connection:
            enabled=connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
            connection.commit()
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
            try:
                connection.exec_driver_sql("BEGIN EXCLUSIVE")
                if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("Existing foreign-key violations require review")
                if needs_upgrade(connection):
                    columns={c['name'] for c in inspect(connection).get_columns("telemetry")}
                    expected=set(Telemetry.__table__.columns.keys())
                    if columns != expected-NEW:
                        raise ValueError("Unexpected/partial telemetry schema; review before migration")
                    indexes=inspect(connection).get_indexes("telemetry")
                    if any(i['name'] not in {i.name for i in Telemetry.__table__.indexes} for i in indexes) or connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='telemetry'").fetchone():
                        raise ValueError("Custom telemetry indexes/triggers need a reviewed migration")
                    metadata=MetaData()
                    Telemetry.__table__.metadata.tables['stations'].to_metadata(metadata)
                    target=Telemetry.__table__.to_metadata(metadata,name="telemetry_interval_upgrade")
                    connection.execute(CreateTable(target))
                    names=", ".join(sorted(columns))
                    connection.exec_driver_sql(f"INSERT INTO telemetry_interval_upgrade ({names}) SELECT {names} FROM telemetry")
                    before=connection.exec_driver_sql("SELECT COUNT(*) FROM telemetry").scalar()
                    after=connection.exec_driver_sql("SELECT COUNT(*) FROM telemetry_interval_upgrade").scalar()
                    if before!=after:
                        raise ValueError("Row count mismatch; migration rolled back")
                    connection.exec_driver_sql("DROP TABLE telemetry")
                    connection.exec_driver_sql("ALTER TABLE telemetry_interval_upgrade RENAME TO telemetry")
                    for index in Telemetry.__table__.indexes:
                        index.create(connection)
                    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
                        raise ValueError("Foreign-key verification failed")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.exec_driver_sql(f"PRAGMA foreign_keys={int(bool(enabled))}")
                connection.commit()
    StationConfiguration.__table__.create(bind,checkfirst=True)
    return needed,False


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    print(migrate(engine,apply=args.apply))
