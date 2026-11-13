from datetime import datetime, timezone, timedelta
from collections import defaultdict
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.services.channel_health import station_channels
from app.services.rise_rate import estimate_rise, MAX_SAMPLES, WINDOW_SECONDS
from app.governance_models import HazardDecision, HazardPolicy
from app.models import Alert, Station, StationIdentity, Telemetry, TelemetryProvenance
from app.operations_models import StationOperation
from app.monitoring_schemas import LivePosition, MonitoringSample, MonitoringSnapshot, MonitoringStation
from app.services.alert_classifier import classify_depth
from app.services.ingress_provenance import provenance_fields


def _utc(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _age(now, value):
    return max(0, int((now - _utc(value)).total_seconds())) if value is not None else None



def registry_location(station, identity):
    """R1: the registry is the only source of a station position. Never substitute a
    demo, planned or bundled point. A missing or invalid pair is returned as None."""
    from math import isfinite
    lat, lon = station.latitude, station.longitude
    if lat is None and lon is None:
        return None, None, "missing"
    if (lat is None or lon is None or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
            or not isfinite(lat) or not isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180):
        return None, None, "invalid"
    verified = bool(identity and identity.coordinates_verified)
    return float(lat), float(lon), "verified" if verified else "unverified"


class _Prefetch:
    """Set-based reads for one snapshot (R2): a fixed number of queries for any number of
    stations instead of ~15 per station. Each per-station value is selected with exactly the
    filter and ORDER BY the per-station query used, via ROW_NUMBER() OVER (PARTITION BY
    station_id ...), which SQLite and PostgreSQL both support."""

    def __init__(self, db, station_ids, *, history_limit, checked_at):
        from app.device_config import StationConfiguration
        self.ids = list(station_ids)
        eligible = (Telemetry.eligible_for_current.is_(True),)
        recent_first = (desc(Telemetry.recorded_at), desc(Telemetry.id))
        self.readings = self._top(db, Telemetry, eligible, recent_first, history_limit)
        self.valid = self._top(db, Telemetry, eligible + (Telemetry.sensor_quality == "valid", Telemetry.water_depth_cm.is_not(None)),
                               recent_first, 2)
        self.last_received = self._top(db, Telemetry, (Telemetry.disposition.in_(("current", "configuration_mismatch", "exercise_local_outputs")),),
                                       (Telemetry.measured_at.desc(), Telemetry.id.desc()), 1)
        self.trend = self._top(db, Telemetry, eligible + (Telemetry.recorded_at >= checked_at - timedelta(seconds=WINDOW_SECONDS),),
                               recent_first, MAX_SAMPLES + 1)
        self.configs = {sid: rows[0] for sid, rows in self._top(
            db, StationConfiguration, (), (StationConfiguration.revision.desc(),), 1).items()}
        latest_ids = [rows[0].id for rows in self.readings.values()]
        valid_ids = [rows[0].id for rows in self.valid.values()]
        self.provenance = self._by_key(db, TelemetryProvenance, TelemetryProvenance.telemetry_id, set(latest_ids + valid_ids))
        self.decisions = self._by_key(db, HazardDecision, HazardDecision.telemetry_id, set(latest_ids))
        # Review flags inside the trend window, by join (not a 1200-per-station IN list);
        # intersected with each station's trend rows by the caller.
        self.review_ids = set(db.scalars(select(HazardDecision.telemetry_id)
            .join(Telemetry, Telemetry.id == HazardDecision.telemetry_id)
            .where(Telemetry.station_id.in_(self.ids), HazardDecision.review_required.is_(True),
                   Telemetry.recorded_at >= checked_at - timedelta(seconds=WINDOW_SECONDS)))) if self.ids else set()
        self.identities = self._by_key(db, StationIdentity, StationIdentity.station_id, self.ids)
        from app.location_models import StationLocationPrecision
        self.location_precision = self._by_key(db, StationLocationPrecision, StationLocationPrecision.station_id, self.ids)
        # Migration 0010: latest operator-phone fix per station and which stations are being tracked now.
        from app.tracking_models import StationTrackedPosition, StationTrackingSession
        self.positions = self._top(db, StationTrackedPosition, (),
                                   (StationTrackedPosition.captured_at.desc(), StationTrackedPosition.id.desc()), 1)
        self.tracking_active = {row.station_id for row in db.scalars(select(StationTrackingSession).where(
            StationTrackingSession.station_id.in_(self.ids), StationTrackingSession.ended_at.is_(None)))
            if _utc(row.expires_at) > checked_at} if self.ids else set()
        self.policies = self._by_key(db, HazardPolicy, HazardPolicy.station_id, self.ids)
        self.operations = self._by_key(db, StationOperation, StationOperation.station_id, self.ids)
        self.episodes = {row.station_id: row for row in db.scalars(select(Alert).where(
            Alert.station_id.in_(self.ids), Alert.status == "ACTIVE"))} if self.ids else {}
        self.mqtt_at = dict(db.execute(select(Telemetry.station_id, func.max(Telemetry.received_at))
            .join(TelemetryProvenance, TelemetryProvenance.telemetry_id == Telemetry.id)
            .where(Telemetry.station_id.in_(self.ids), TelemetryProvenance.ingress_transport == "mqtt",
                   TelemetryProvenance.stream == "operational").group_by(Telemetry.station_id)).all()) if self.ids else {}

    def _top(self, db, model, filters, order, limit):
        if not self.ids:
            return {}
        rank = func.row_number().over(partition_by=model.station_id, order_by=order).label("rank")
        ranked = select(model.id, rank).where(model.station_id.in_(self.ids), *filters).subquery()
        grouped = defaultdict(list)
        for row in db.scalars(select(model).join(ranked, ranked.c.id == model.id)
                              .where(ranked.c.rank <= limit).order_by(model.station_id, ranked.c.rank)):
            grouped[row.station_id].append(row)
        return grouped

    @staticmethod
    def _by_key(db, model, column, keys):
        return {getattr(row, column.key): row for row in db.scalars(select(model).where(column.in_(list(keys))))} if keys else {}


def monitoring_snapshot(db: Session, *, stale_after_seconds: int, history_limit: int,
                        now: datetime | None = None, settings=None, station_ids=None) -> MonitoringSnapshot:
    settings = settings or get_settings()
    checked_at = _utc(now) or datetime.now(timezone.utc)
    result = []
    query=select(Station).order_by(Station.station_id)
    if station_ids is not None:query=query.where(Station.station_id.in_(station_ids))
    stations=list(db.scalars(query.limit(settings.read_model_max_stations+1)))
    if len(stations)>settings.read_model_max_stations or len(stations)*history_limit>settings.read_model_max_points:
        from fastapi import HTTPException
        raise HTTPException(503,'Station/history read-model budget exceeded; select fewer stations or reduce history',headers={'Retry-After':'30'})
    bulk = _Prefetch(db, [station.station_id for station in stations], history_limit=history_limit, checked_at=checked_at)
    for station in stations:
        sid = station.station_id
        readings = bulk.readings.get(sid, [])
        latest = readings[0] if readings else None
        # Independent of the chart window: invalid heartbeats cannot evict the
        # retained valid depth, change its date, or manufacture recovery.
        valid = bulk.valid.get(sid, [])
        last_valid = valid[0] if valid else None
        p = bulk.provenance.get(latest.id) if latest else None
        vp = bulk.provenance.get(last_valid.id) if last_valid else None
        provenance = provenance_fields(p)
        identity = bulk.identities.get(sid)
        from app.device_config import configuration_contract
        from app.services.rainfall_contract import rainfall_product
        config = bulk.configs.get(sid)
        # Report acquisition/configuration meaning in measured order. A delayed
        # retired/stale packet cannot overwrite the current applied-profile view.
        received = bulk.last_received.get(sid, [])
        last_received = received[0] if received else None
        applied=last_received.applied_config_hash if last_received else None
        config_view=configuration_contract(config,applied) if config else dict(status="unconfigured",applied_config_hash=applied,validation_status="unreviewed")
        config_view.update(local_alert_profile=last_received.local_alert_profile if last_received else "unknown",sensor_fault=last_received.sensor_fault if last_received else "unknown")
        configuration_blocked=bool(last_received and (last_received.local_alert_profile!="depth" or (config and applied!=config.config_hash)))
        depth_trusted = bool(vp and vp.source_class == "physical_device" and vp.stream == "operational"
                             and identity and identity.state == "commissioned" and vp.registry_version == identity.version
                             and vp.ingress_identity == identity.device_id)
        if configuration_blocked or config and (not last_valid or last_valid.applied_config_hash!=config.config_hash):
            depth_trusted=False
        decision = bulk.decisions.get(latest.id) if latest else None
        channels = station_channels(db, station, identity, latest, last_valid,
            bool(last_valid and latest and last_valid.id == latest.id and latest.sensor_quality == "valid"
                 and _age(checked_at, last_valid.measured_at) is not None and _age(checked_at, last_valid.measured_at) <= stale_after_seconds),
            depth_trusted, bool(decision and decision.review_required), settings, checked_at, stale_after_seconds=stale_after_seconds,
            prefetched={'config': config, 'mqtt_at': bulk.mqtt_at.get(sid)})
        heartbeat = channels["device_heartbeat"]["observed_at"]
        rain_product=rainfall_product(station.station_id,settings,checked_at,channels['rain_counter'])
        sample_time = _utc(latest.measured_at) if latest else None
        valid_time = _utc(last_valid.measured_at) if last_valid else None
        heartbeat_age, sample_age, depth_age = (_age(checked_at, v) for v in (heartbeat, sample_time, valid_time))
        heartbeat_fresh = heartbeat_age is not None and heartbeat_age <= stale_after_seconds
        depth_recent = depth_age is not None and depth_age <= stale_after_seconds
        depth_fresh = bool(depth_recent and latest and latest.sensor_quality == "valid" and latest.id == last_valid.id and not configuration_blocked)
        depth_status = "missing" if last_valid is None else "stale" if not depth_recent else "fresh" if depth_fresh else "retained"
        connection = station.status if station.status in ("inactive", "maintenance") else (
            "no_data" if latest is None else "online" if heartbeat_fresh else "offline")
        episode = bulk.episodes.get(sid)
        observation_tier = classify_depth(station, last_valid.water_depth_cm if last_valid else None)
        tier = episode.current_severity if episode else observation_tier
        hazard = ("observed" if depth_fresh and observation_tier == episode.current_severity and not (decision and decision.review_required) else "unresolved") if episode else (
            "observed" if depth_fresh and tier not in (None, "NORMAL") else "none" if depth_fresh else "unknown")
        if episode and station.status!='active':hazard='unresolved'
        from app.services.station_lifecycle import contract as lifecycle_contract
        source = "none" if latest is None else {"physical_device": "device", "simulator": "simulator"}.get(provenance["source_class"], "unverified")
        trend_rows = bulk.trend.get(sid, [])
        review_ids = {r.id for r in trend_rows} & bulk.review_ids
        trend = estimate_rise(trend_rows, checked_at, stale_after_seconds=stale_after_seconds, review_ids=review_ids)
        if not depth_trusted:
            trend.update(trend="unknown",rise_rate_cm_per_minute=None,rise_rate_lower=None,rise_rate_upper=None,
                         trend_reason="Unverified depth source; operational rate unknown")
        latitude, longitude, coordinate_status = registry_location(station, identity)
        # Precision is reported only for a mappable pair; it never creates or moves a pin (R1).
        precision = bulk.location_precision.get(sid) if latitude is not None else None
        live = None
        fixes = bulk.positions.get(sid)
        if fixes:
            from app.tracking_models import LIVE_FRESH_SECONDS
            fix, active = fixes[0], sid in bulk.tracking_active
            age = max(0, int((checked_at - _utc(fix.captured_at)).total_seconds()))
            live = LivePosition(latitude=fix.latitude, longitude=fix.longitude, accuracy_m=fix.accuracy_m,
                                captured_at=_utc(fix.captured_at), age_seconds=age, tracking_active=active,
                                fresh=active and age <= LIVE_FRESH_SECONDS)
        result.append(MonitoringStation(
            station_id=station.station_id, station_name=station.station_name, barangay=station.barangay,
            municipality=station.municipality, latitude=latitude, longitude=longitude,
            coordinate_status=coordinate_status,
            coordinate_precision_m=precision.precision_m if precision else None,
            coordinate_basis=precision.basis if precision else None,
            live_position=live,
            administrative_status=station.status, connection_status=connection, is_online=connection == "online",
            is_stale=depth_status in ("stale", "retained"),
            # Compatibility aliases now date the retained value, not the heartbeat.
            age_seconds=depth_age, observed_at=valid_time, last_ping=heartbeat,
            heartbeat_at=heartbeat, heartbeat_age_seconds=heartbeat_age, heartbeat_fresh=heartbeat_fresh,
            latest_sample_at=sample_time, latest_sample_age_seconds=sample_age,
            last_valid_depth_at=valid_time, depth_age_seconds=depth_age, depth_fresh=depth_fresh, depth_status=depth_status,
            rainfall_observed_at=rain_product.get('observed_at'), rainfall_age_seconds=int(rain_product['age_seconds']) if rain_product.get('age_seconds') is not None else None,
            rainfall_fresh=rain_product['rainfall_mm'] is not None,
            hazard_state=hazard, active_hazard_tier=episode.current_severity if episode else None,
            active_alert_id=episode.id if episode else None,
            observation_tier=observation_tier, hazard_policy_state="station_reviewed" if sid in bulk.policies else "provisional",
            hazard_decision=decision.reason if decision else None, hazard_review_required=decision.review_required if decision else False,
            alert_tier=tier, channel_health=channels,lifecycle=lifecycle_contract(db,station,identity=identity,operation=bulk.operations.get(sid),configuration=config), **trend,
            current_depth_cm=last_valid.water_depth_cm if last_valid else None,
            latest_depth_cm=latest.water_depth_cm if latest else None,
            latest_rainfall_mm=rain_product['rainfall_mm'],rainfall_product=rain_product,configuration=config_view,
            sensor_quality=latest.sensor_quality if latest else None,
            firmware_version=latest.firmware_version if latest else station.firmware_version,
            source=source, source_class=provenance["source_class"], source_trusted=provenance["source_trusted"],
            depth_source_class=vp.source_class if vp else "unverified", depth_source_trusted=depth_trusted,
            depth_source_id=vp.ingress_identity if vp else None,
            threshold_advisory_cm=station.threshold_advisory_cm, threshold_warning_cm=station.threshold_warning_cm,
            threshold_evacuate_cm=station.threshold_evacuate_cm,
            history=[MonitoringSample(sequence_no=r.sequence_no, water_depth_cm=r.water_depth_cm,
                rainfall_mm=None, sensor_quality=r.sensor_quality, device_uptime_ms=r.device_uptime_ms,
                recorded_at=r.recorded_at, measured_at=_utc(r.measured_at) if r.measured_at else None,
                received_at=_utc(r.received_at)) for r in reversed(readings)]))
    return MonitoringSnapshot(checked_at=checked_at, stale_after_seconds=stale_after_seconds, stations=result)
