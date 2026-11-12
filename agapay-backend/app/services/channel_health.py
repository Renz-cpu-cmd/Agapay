from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3
from urllib.parse import quote
from sqlalchemy import select
from app.models import StationCredential, Telemetry, TelemetryProvenance
from app.services.broker_health import snapshot as broker_snapshot
from app.services.station_security import utc


def channel(state, reason, at=None, now=None, **fields):
    age = max(0, (utc(now)-utc(at)).total_seconds()) if at and now else None
    return dict(state=state, reason=reason, observed_at=at, age_seconds=age, **fields)


def rain_health(db, station, identity, settings, now, *, config=None, config_loaded=False):
    from app.device_config import current_configuration
    if not config_loaded:
        config=current_configuration(db,station.station_id)
    calibration = settings.rain_gauge_calibrations.get(station.station_id)
    if config:
        calibration=config.installation['rain_mm_per_tip']
    if not settings.rain_gauge_enabled:
        return channel("disabled", "Independent rain journal is disabled", value=None, unit="tips")
    path = Path(settings.rain_gauge_store_path)
    if not path.is_file():
        return channel("no_data", "No independent rain journal received", value=None, unit="tips")
    try:
        with closing(sqlite3.connect(f"file:{quote(path.resolve().as_posix())}?mode=ro", uri=True, timeout=1)) as store:
            from app.services.rain_rollups import require_current
            require_current(store)
            store.row_factory = sqlite3.Row
            row = store.execute("""SELECT e.count,e.mm,e.mm_per_tip,e.received,e.payload,p.* FROM events e
                LEFT JOIN ingress_provenance p ON p.event_id=e.id
                WHERE e.station=? AND e.source='physical_rain_gauge' ORDER BY e.id DESC LIMIT 1""", (station.station_id,)).fetchone()
    except (sqlite3.Error, OSError, ValueError):
        return channel("unknown", "Independent rain journal is unavailable or lacks provenance", value=None, unit="tips")
    if row is None:
        return channel("no_data", "No independent physical rain-counter sample received", value=None, unit="tips")
    try:
        at = datetime.fromisoformat(row["received"])
    except (ValueError, TypeError):
        return channel("unknown", "Rain journal observation time is invalid", value=None, unit="tips")
    credential = db.get(StationCredential, row["credential_id"]) if row["credential_id"] else None
    trusted = bool(identity and identity.state == "commissioned" and row["registry_version"] == identity.version
        and row["ingress_identity"] == identity.device_id and row["source_class"] == "physical_device"
        and row["stream"] == "operational" and credential and credential.revoked_at is None and utc(credential.expires_at) > utc(now))
    age = (utc(now)-utc(at)).total_seconds()
    import json
    version=json.loads(row['payload']).get('calibration_version','legacy-unversioned')
    state = "unverified" if not trusted else "invalid" if calibration is None or abs(row["mm_per_tip"]-calibration) > .00001 or (config and version!=config.config_hash) else "healthy" if 0 <= age <= 30 else "stale"
    return channel(state, "Independent rain counter received; zero tips is valid, mechanical operation/calibration not proven" if state == "healthy" else "Independent rain counter stale, unverified, or calibration configuration mismatched",
        at, now, value=row["count"], unit="tips", increment_mm=row["mm"], mm_per_tip=row["mm_per_tip"],
        source_trusted=trusted, ingress_transport=row["ingress_transport"])


def station_channels(db, station, identity, latest, last_valid, depth_fresh, depth_trusted, review, settings, now, *, stale_after_seconds=30,
                     prefetched=None):
    """``prefetched`` (monitoring bulk read): {'config': row|None, 'mqtt_at': datetime|None}."""
    from app.device_config import current_configuration
    config=prefetched['config'] if prefetched is not None else current_configuration(db,station.station_id)
    rain = rain_health(db, station, identity, settings, now, config=config, config_loaded=True)
    water_at = utc(latest.received_at) if latest else None
    rain_at = utc(rain["observed_at"]) if rain.get("source_trusted") else None
    heartbeat = max((at for at in (water_at, rain_at) if at is not None), default=None)
    hb_fresh = heartbeat is not None and 0 <= (utc(now)-heartbeat).total_seconds() <= stale_after_seconds
    water_state = "no_data" if latest is None else "invalid" if latest.sensor_quality != "valid" or review else "unverified" if not depth_trusted else "healthy" if depth_fresh else "stale"
    mqtt_at = prefetched['mqtt_at'] if prefetched is not None else db.scalar(select(Telemetry.received_at).join(TelemetryProvenance, TelemetryProvenance.telemetry_id == Telemetry.id).where(
        Telemetry.station_id == station.station_id, TelemetryProvenance.ingress_transport == "mqtt",
        TelemetryProvenance.stream == "operational").order_by(Telemetry.received_at.desc()).limit(1))
    if rain_at and rain.get("ingress_transport") == "mqtt":
        mqtt_at = max((utc(at) for at in (mqtt_at, rain_at) if at is not None))
    broker = broker_snapshot(settings.mqtt_enabled, shared_path=settings.mqtt_status_path if settings.mqtt_external_subscriber else "", now=now)
    broker_state = "disabled" if not settings.mqtt_enabled else "disconnected" if broker["state"] == "disconnected" else "healthy" if mqtt_at and (utc(now)-utc(mqtt_at)).total_seconds() <= 30 else "stale" if mqtt_at else "no_data"
    return dict(
        device_heartbeat=channel("healthy" if hb_fresh else "stale" if heartbeat else "no_data", "Latest water or authenticated rain receipt; independent of water validity", heartbeat, now),
        water_sensor=channel(water_state, "Latest water sample quality and measurement freshness; retained values keep their original time", last_valid.measured_at if last_valid else None, now,
            value=last_valid.water_depth_cm if last_valid else None, unit="cm"),
        rain_counter=rain,
        broker_ingestion=channel(broker_state, "Last accepted operational MQTT receipt; HTTP traffic is not broker evidence", mqtt_at, now, connection_state=broker["state"], connection_observed_at=broker["observed_at"], observer_scope=broker["scope"]),
        calibration=dict(state="documented" if identity and identity.calibration_note else "unconfigured",
            reason="Commissioning documentation/configuration is not physical calibration attestation",
            water_note=config.evidence if config else identity.calibration_note if identity else None, reference_datum=config.installation['datum'] if config else identity.reference_datum if identity else None,
            rain_configured_mm_per_tip=config.installation['rain_mm_per_tip'] if config else settings.rain_gauge_calibrations.get(station.station_id), physical_validation="pending"),
    )
