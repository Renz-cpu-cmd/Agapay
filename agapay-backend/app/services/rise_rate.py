"""Bounded robust measured-time trend; provisional presentation thresholds."""
from datetime import timedelta
from math import ceil, floor, isfinite
from statistics import median
from app.services.station_security import utc

WINDOW_SECONDS = 300
MAX_SAMPLES = 1200
BIN_SECONDS = 10
MIN_SPAN_SECONDS = 30
MAX_GAP_SECONDS = 60
MIN_COVERAGE = .8


def estimate_rise(rows, now, *, stale_after_seconds=30, review_ids=()):
    result = dict(trend="unknown", rise_rate_cm_per_minute=None, rise_rate_lower=None,
        rise_rate_upper=None, trend_window_start=None, trend_window_end=None,
        trend_sample_count=0, trend_bin_count=0, trend_coverage=0.0,
        trend_reason="Insufficient valid measurement timing/coverage",
        trend_method="Median pairwise slope over cadence-adaptive 10-60-second median bins; central 80% slope range")
    if len(rows) > MAX_SAMPLES:
        return {**result, "trend_reason": "Trend window sample budget exceeded"}
    now = utc(now)
    rows = sorted(rows, key=lambda row: (utc(row.measured_at or row.recorded_at), row.id or 0))
    segment = []
    for row in rows:
        at = utc(row.measured_at)
        valid = (at is not None and now - timedelta(seconds=WINDOW_SECONDS) <= at <= now
                 and row.sensor_quality == "valid" and row.water_depth_cm is not None
                 and isfinite(row.water_depth_cm) and row.id not in review_ids)
        if not valid:
            segment = []
            continue
        if segment:
            previous = segment[-1]
            gap = (at - utc(previous.measured_at)).total_seconds()
            if gap <= 0 or gap > MAX_GAP_SECONDS or (row.config_version, row.boot_id, row.source_id) != (previous.config_version, previous.boot_id, previous.source_id):
                segment = []
        segment.append(row)
    if not segment or not rows or segment[-1].id != rows[-1].id:
        return {**result, "trend_reason": "Latest observation invalid, under review, or outside the measured-time window"}
    first, last = utc(segment[0].measured_at), utc(segment[-1].measured_at)
    result.update(trend_sample_count=len(segment), trend_window_start=first, trend_window_end=last)
    if (now - last).total_seconds() > stale_after_seconds:
        return {**result, "trend_reason": "Latest measurement stale; current trend unknown"}
    gaps = [(utc(b.measured_at)-utc(a.measured_at)).total_seconds() for a,b in zip(segment,segment[1:])]
    bin_seconds = max(BIN_SECONDS,min(MAX_GAP_SECONDS,ceil(median(gaps)))) if gaps else BIN_SECONDS
    bins = {}
    for row in segment:
        bins.setdefault(floor(utc(row.measured_at).timestamp() / bin_seconds), []).append(row)
    coverage = len(bins) / (max(bins) - min(bins) + 1)
    result.update(trend_bin_count=len(bins), trend_coverage=coverage)
    if len(bins) < 3 or (last-first).total_seconds() < MIN_SPAN_SECONDS or coverage < MIN_COVERAGE:
        return result
    points = [(median(utc(row.measured_at).timestamp() for row in group), median(row.water_depth_cm for row in group)) for group in bins.values()]
    slopes = sorted((y2-y1) * 60 / (t2-t1) for i, (t1,y1) in enumerate(points) for t2,y2 in points[i+1:] if t2 > t1)
    rate = median(slopes)
    low, high = slopes[floor((len(slopes)-1)*.1)], slopes[floor((len(slopes)-1)*.9)]
    trend = ("rising_rapidly" if low >= 4-1e-6 else "rising" if low >= .5-1e-6 else "falling" if high <= -.5+1e-6
             else "stable" if low > -.5 and high < .5 else "unknown")
    result.update(trend=trend, rise_rate_cm_per_minute=rate, rise_rate_lower=low, rise_rate_upper=high,
        trend_reason="Covered measured-time window; thresholds 0.5/4 cm per minute" if trend != "unknown" else "Slope uncertainty crosses a classification boundary")
    return result
