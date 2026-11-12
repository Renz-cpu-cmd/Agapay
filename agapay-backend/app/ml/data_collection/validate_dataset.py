"""Non-destructive checks; findings are retained, never repaired silently."""
import argparse
import json
from pathlib import Path
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import numpy as np
import pandas as pd
from .build_manifest import write_json


def utc_timestamp(value, timezone_name: str) -> pd.Timestamp:
    if pd.isna(value) or str(value).strip() == "":
        return pd.NaT
    # Reject ambiguous locale dates rather than guessing day/month order.
    if isinstance(value, str) and not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", value.strip()):
        return pd.NaT
    try:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize(timezone_name, ambiguous="raise", nonexistent="raise")
        return timestamp.tz_convert("UTC")
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def validate_dataset(frame: pd.DataFrame, metadata: dict) -> dict:
    issues: list[dict] = []

    def flag(code: str, severity: str, rows=None, detail: str = "") -> None:
        selected = [] if rows is None else list(rows)
        issues.append({"code": code, "severity": severity, "count": len(selected),
                       "rows_sample": [int(i) + 2 for i in selected[:25]], "detail": detail})

    if frame.empty:
        flag("empty_dataset", "error")
    for key in ("station_id", "source", "timezone", "latitude", "longitude", "units", "interval_seconds"):
        if key not in metadata or metadata[key] is None or metadata[key] == "":
            flag("missing_metadata", "error", detail=key)
    for key, bound in (("latitude", 90), ("longitude", 180)):
        try:
            value = float(metadata[key])
            if not math.isfinite(value) or abs(value) > bound:
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            flag("invalid_geography", "error", detail=key)
    try:
        ZoneInfo(metadata.get("timezone", ""))
        if metadata.get("timezone") not in ("UTC", "Etc/UTC", "GMT", "Etc/GMT"):
            flag("timezone_inconsistency", "error", detail="Normalized metadata timezone must be UTC")
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        flag("timezone_inconsistency", "error", detail="Unknown metadata timezone")
    for column, key in (("station_id", "station_id"), ("dataset_source", "source")):
        if column not in frame:
            flag("missing_column", "error", detail=column)
        else:
            flag_rows = frame.index[frame[column].isna() | frame[column].ne(metadata.get(key))]
            if len(flag_rows):
                flag("identity_mismatch", "error", flag_rows, column)
    if "timestamp_utc" not in frame:
        flag("missing_column", "error", detail="timestamp_utc")
        return {"rows": len(frame), "valid": False, "issues": issues}
    times = pd.to_datetime(frame.timestamp_utc, errors="coerce", utc=True, format="mixed")
    bad = frame.index[times.isna()]
    if len(bad):
        flag("missing_or_malformed_timestamp", "error", bad)
    # Normalized CSVs must explicitly carry UTC, rather than implicit local dates.
    timezone_bad = frame.index[~frame.timestamp_utc.fillna("").astype(str).str.contains(r"(?:Z|\+00:00)$", regex=True)]
    if len(timezone_bad):
        flag("timezone_inconsistency", "error", timezone_bad)
    duplicates = frame.index[times.notna() & times.duplicated(keep=False)]
    if len(duplicates):
        flag("duplicate_timestamp", "error", duplicates)
    if not times.dropna().is_monotonic_increasing:
        flag("chronological_order", "error")
    interval = metadata.get("interval_seconds")
    if isinstance(interval, (int, float)) and interval > 0:
        ordered = times.dropna().sort_values().drop_duplicates()
        deltas = ordered.diff().dt.total_seconds()
        irregular = deltas.index[deltas.notna() & deltas.ne(interval)]
        if len(irregular):
            flag("irregular_interval", "warning", irregular)
        if len(ordered):
            try:
                start = pd.to_datetime(metadata.get("expected_start") or ordered.iloc[0], utc=True)
                end = pd.to_datetime(metadata.get("expected_end") or ordered.iloc[-1], utc=True)
                if pd.isna(start) or pd.isna(end) or end < start:
                    raise ValueError("Invalid coverage bounds")
                expected = pd.date_range(start, end, freq=pd.Timedelta(seconds=interval))
                missing = expected.difference(pd.DatetimeIndex(ordered))
                if len(missing):
                    flag("missing_timestamps", "error", detail=f"{len(missing)} absent slots; first: {missing[0]}")
                if ordered.iloc[0] != start or ordered.iloc[-1] != end:
                    flag("coverage_mismatch", "warning", detail=f"expected {start} through {end}")
            except (ValueError, TypeError, OverflowError):
                flag("invalid_coverage_metadata", "error")
    else:
        flag("unknown_interval", "warning")
    units = metadata.get("units", {})
    allowed = {"precipitation_mm": "mm", "rainfall_mm": "mm", "temperature_c": "°C", "relative_humidity_pct": "%"}
    for column, unit in units.items():
        if column not in frame:
            flag("missing_column", "error", detail=column)
            continue
        if (column in allowed and unit != allowed[column]) or (column == "water_level" and unit not in ("m", "cm", "mm")):
            flag("inconsistent_units", "error", detail=f"{column}: {unit}")
        numeric = pd.to_numeric(frame[column], errors="coerce")
        missing = frame.index[frame[column].isna() | frame[column].astype(str).str.strip().eq("")]
        if len(missing):
            flag("missing_measurement", "warning", missing, column)
        invalid = frame.index[(~np.isfinite(numeric)) & ~frame.index.isin(missing)]
        if len(invalid):
            flag("invalid_numeric", "error", invalid, column)
        suspicious = numeric.lt(0) if column in ("precipitation_mm", "rainfall_mm") else pd.Series(False, index=frame.index)
        if column == "relative_humidity_pct":
            suspicious |= numeric.lt(0) | numeric.gt(100)
        if suspicious.any():
            flag("suspicious_range", "warning", frame.index[suspicious], column)
        jump = metadata.get("jump_thresholds", {}).get(column)
        if jump is not None:
            sorted_values = numeric.loc[times.sort_values().index]
            jumps = sorted_values.diff().abs().gt(jump)
            if jumps.any():
                flag("large_jump", "warning", sorted_values.index[jumps], f"{column}: threshold {jump} {unit}")
    if "water_level" in frame:
        for key in ("reference_datum", "measurement_kind"):
            if not metadata.get(key):
                flag("missing_water_reference", "error", detail=key)
            elif metadata[key] == "unknown":
                flag("unresolved_water_reference", "warning", detail=key)
            if key in frame and not frame[key].eq(metadata.get(key)).all():
                flag("water_reference_mismatch", "error", detail=key)
        if "water_level_unit" not in frame or not frame.water_level_unit.eq(units.get("water_level")).all():
            flag("inconsistent_units", "error", detail="water_level_unit")
        if "quality_flag" not in frame or frame.quality_flag.fillna("").isin(("", "unknown")).any():
            flag("missing_quality_flag", "warning")
    return {"rows": len(frame), "valid": not any(i["severity"] == "error" for i in issues),
            "observed_start_utc": None if times.dropna().empty else times.min().isoformat(),
            "observed_end_utc": None if times.dropna().empty else times.max().isoformat(),
            "issues": issues, "policy": "Flag only; no deletion or interpolation. Row samples are CSV line numbers."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate_dataset(pd.read_csv(args.csv), json.loads(args.metadata.read_text(encoding="utf-8")))
    write_json(args.output, report)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
