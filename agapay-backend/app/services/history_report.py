"""Bounded, reproducible measured-time report; no receipt-time backfill or interpolation."""
from datetime import timedelta, timezone
from math import ceil, isfinite
from fastapi import HTTPException
from sqlalchemy import func, select
from app.governance_models import HazardDecision
from app.models import Alert, Station, Telemetry, TelemetryProvenance, utc_now
from app.services.station_security import utc

MAX_ROWS = 100_000
MAX_POINTS = 20_000
MAX_STATIONS = 20


def build_history_report(db, *, start_at=None, end_at=None, station_ids=None, event_id=None,
                         timezone_name="Asia/Manila", bucket_seconds=60, now=None):
    checked = utc(now or utc_now())
    event = db.get(Alert, event_id) if event_id else None
    if event_id and not event:
        raise HTTPException(404, "Sensor episode not found")
    selected_ids = list(dict.fromkeys(station_ids or []))
    if event:
        if selected_ids and selected_ids != [event.station_id]:
            raise HTTPException(422, "An event report must select that episode's station")
        selected_ids = [event.station_id]
        begin, finish = utc(event.triggered_at), utc(event.resolved_at) if event.resolved_at else checked
        start_at = max(utc(start_at), begin) if start_at else begin
        end_at = min(utc(end_at), finish) if end_at else finish
    if start_at is None or end_at is None:
        raise HTTPException(422, "Choose an explicit start/end range or sensor event ID")
    start, end = utc(start_at), utc(end_at)
    if not 0 < (end-start).total_seconds() <= 7*86400 or end > checked + timedelta(seconds=5):
        raise HTTPException(422, "Report range must be positive, at most seven days, and not in the future")
    if timezone_name not in ("UTC", "Asia/Manila") or bucket_seconds not in (30,60,300,900,3600):
        raise HTTPException(422, "Unsupported timezone or bucket size")
    station_query = select(Station).order_by(Station.station_id)
    if selected_ids:
        station_query = station_query.where(Station.station_id.in_(selected_ids))
    stations = list(db.scalars(station_query.limit(MAX_STATIONS+1)))
    if len(stations) > MAX_STATIONS or len(selected_ids) > MAX_STATIONS:
        raise HTTPException(422, "Select at most twenty stations")
    if selected_ids and {station.station_id for station in stations} != set(selected_ids):
        raise HTTPException(404, "Unknown station filter")
    count = ceil((end-start).total_seconds()/bucket_seconds)
    if count*max(1,len(stations)) > MAX_POINTS:
        raise HTTPException(422, "Chart budget exceeded; choose a larger bucket or fewer stations")
    ids = [station.station_id for station in stations]
    by_station = {}
    for station in stations:
        buckets = []
        for index in range(count):
            begin = start + timedelta(seconds=index*bucket_seconds)
            buckets.append(dict(bucket_start=begin, bucket_end=min(end, begin+timedelta(seconds=bucket_seconds)),
                mean_depth_cm=None, minimum_depth_cm=None, maximum_depth_cm=None,
                sample_count=0, valid_count=0, invalid_count=0, review_count=0, unverified_count=0,
                first_measured_at=None, last_measured_at=None, quality="missing", sources={}, source_details={}, _sum=0.0))
        by_station[station.station_id] = dict(station_id=station.station_id, station_name=station.station_name,
            unit="cm", minimum_depth_cm=None, maximum_depth_cm=None, mean_depth_cm=None,
            sample_count=0, valid_count=0, invalid_count=0, review_count=0, unverified_count=0,
            covered_buckets=0, expected_buckets=count, sources={}, source_details={}, buckets=buckets, _sum=0.0)
    query = select(Telemetry, TelemetryProvenance, HazardDecision).outerjoin(
        TelemetryProvenance, TelemetryProvenance.telemetry_id == Telemetry.id).outerjoin(
        HazardDecision, HazardDecision.telemetry_id == Telemetry.id).where(
        Telemetry.station_id.in_(ids), Telemetry.measured_at >= start, Telemetry.measured_at <= end,
        Telemetry.received_at <= checked).order_by(Telemetry.measured_at, Telemetry.id).limit(MAX_ROWS+1)
    total = 0
    for sample, provenance, decision in db.execute(query.execution_options(yield_per=500)):
        total += 1
        if total > MAX_ROWS:
            raise HTTPException(422, "Report sample budget exceeded; narrow the time or station scope. No partial report was returned")
        item = by_station[sample.station_id]
        at = utc(sample.measured_at)
        index = min(count-1, int((at-start).total_seconds()//bucket_seconds))
        bucket = item["buckets"][index]
        source = provenance.source_class if provenance else "unverified"
        source_detail = f"{source}|{provenance.ingress_transport}|{provenance.ingress_identity}|registry-v{provenance.registry_version}" if provenance else "unverified|legacy identity unavailable"
        trusted = bool(provenance and provenance.source_class == "physical_device" and provenance.stream == "operational")
        quality = "invalid" if sample.sensor_quality != "valid" or sample.water_depth_cm is None or not isfinite(sample.water_depth_cm) else "review" if (decision and decision.review_required) or sample.disposition in ("configuration_mismatch","exercise_local_outputs","journal_configuration_mismatch","journal_exercise_local_outputs") else "unverified" if not trusted else "valid"
        for target in (item, bucket):
            target["sample_count"] += 1
            target[quality+"_count"] += 1
            target["sources"][source] = target["sources"].get(source,0)+1
            target["source_details"][source_detail] = target["source_details"].get(source_detail,0)+1
            if quality == "valid":
                value = sample.water_depth_cm
                target["_sum"] += value
                target["minimum_depth_cm"] = min(target["minimum_depth_cm"],value) if target["minimum_depth_cm"] is not None else value
                target["maximum_depth_cm"] = max(target["maximum_depth_cm"],value) if target["maximum_depth_cm"] is not None else value
        bucket["first_measured_at"] = bucket["first_measured_at"] or at
        bucket["last_measured_at"] = at
    for item in by_station.values():
        item["mean_depth_cm"] = item.pop("_sum")/item["valid_count"] if item["valid_count"] else None
        item.pop("_sum",None)
        for bucket in item["buckets"]:
            bucket["mean_depth_cm"] = bucket.pop("_sum")/bucket["valid_count"] if bucket["valid_count"] else None
            bucket.pop("_sum",None)
            bucket["quality"] = "missing" if not bucket["sample_count"] else "valid" if bucket["valid_count"] == bucket["sample_count"] else "mixed" if bucket["valid_count"] else "unavailable"
        item["covered_buckets"] = sum(bucket["valid_count"] > 0 for bucket in item["buckets"])
    unsynchronized = db.scalar(select(func.count()).select_from(Telemetry).where(Telemetry.station_id.in_(ids),
        Telemetry.measured_at.is_(None), Telemetry.received_at >= start, Telemetry.received_at <= min(end,checked)))
    local = timezone(timedelta(hours=8)) if timezone_name == "Asia/Manila" else timezone.utc
    return dict(checked_at=checked, scope=dict(start_at=start, end_at=end,
        start_local=start.astimezone(local).isoformat(), end_local=end.astimezone(local).isoformat(),
        timezone=timezone_name, station_ids=ids, event_id=event.id if event else None,
        event_status=event.status if event else None, event_started_at=utc(event.triggered_at) if event else None,
        event_resolved_at=utc(event.resolved_at) if event and event.resolved_at else None,
        bucket_seconds=bucket_seconds, boundary="inclusive start/end; final bucket includes the upper boundary",
        timestamp_basis="device measured time; unsynchronized receipt-only rows excluded",
        aggregation="arithmetic mean of valid registry-physical operational samples per bucket anchored at selected start; exact extrema over all qualifying samples; no interpolation",
        coverage_basis="buckets containing qualifying samples / expected buckets; not proof of continuous measurement",
        rainfall_scope="water-depth report only; no rainfall total inferred from water telemetry",
        rows_scanned=total, unsynchronized_rows_excluded=unsynchronized), stations=list(by_station.values()))
