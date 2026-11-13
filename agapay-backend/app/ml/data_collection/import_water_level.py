"""Import officially acquired records without converting gauge level to depth."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
from .build_manifest import build_manifest, run_id, write_json
from .config import DATA_ROOT, SOURCES, create_layout, safe_label
from .validate_dataset import utc_timestamp, validate_dataset


def import_water_level(path: Path, metadata: dict, root: Path = DATA_ROOT, *,
                       time_column: str = "timestamp", level_column: str = "water_level",
                       quality_column: str | None = None, unit_column: str | None = None,
                       station_column: str | None = None, sheet: str | int = 0) -> dict:
    required = ("station_id", "source", "latitude", "longitude", "timezone", "reference_datum",
                "measurement_kind", "units", "interval_seconds", "acquisition_reference", "license")
    if any(key not in metadata for key in required):
        raise ValueError(f"Metadata requires: {', '.join(required)}")
    station = safe_label(metadata["station_id"])
    source = metadata["source"]
    if source not in SOURCES or source in ("open_meteo", "nasa_gpm"):
        raise ValueError("Water-level source must be philsensors, pagasa or agapay_esp32")
    if metadata["units"].get("water_level") not in ("m", "cm", "mm"):
        raise ValueError("Explicit water_level unit must be m, cm or mm")
    if metadata["measurement_kind"] not in ("gauge_level", "water_surface_elevation", "local_depth"):
        raise ValueError("Unknown measurement_kind")
    if not metadata["reference_datum"] or not metadata["acquisition_reference"] or not metadata["license"]:
        raise ValueError("Datum, acquisition reference and license must be documented (use 'unknown' if genuinely unknown)")
    ZoneInfo(metadata["timezone"])
    if path.suffix.lower() not in (".csv", ".xlsx", ".xls"):
        raise ValueError("Supply a CSV, XLSX or XLS file; PDF and macros are unsupported")
    create_layout(root)
    identifier = run_id(station)
    raw_dir = root / "raw" / source / identifier
    raw_dir.mkdir()
    raw_path = raw_dir / f"original{path.suffix.lower()}"
    with raw_path.open("xb") as handle:
        handle.write(path.read_bytes())
    write_json(raw_dir / "supplied_metadata.json", metadata)
    # Parse the retained copy so provenance matches the bytes actually imported.
    supplied = pd.read_csv(raw_path, dtype=str, keep_default_na=False) if path.suffix.lower() == ".csv" else pd.read_excel(raw_path, sheet_name=sheet, dtype=str, keep_default_na=False)
    for column in (time_column, level_column, quality_column, unit_column, station_column):
        if column and column not in supplied:
            raise ValueError(f"Source column is missing: {column}. Raw file has been retained at {raw_path}")
    frame = pd.DataFrame({"timestamp_original": supplied[time_column], "water_level": supplied[level_column],
                          "water_level_raw": supplied[level_column]})
    times = frame.timestamp_original.map(lambda value: utc_timestamp(value, metadata["timezone"]))
    frame.insert(0, "timestamp_utc", times.map(lambda value: None if pd.isna(value) else value.isoformat()))
    frame["station_id"] = supplied[station_column] if station_column else station
    frame["dataset_source"] = source
    frame["water_level_unit"] = supplied[unit_column] if unit_column else metadata["units"]["water_level"]
    frame["quality_flag"] = supplied[quality_column] if quality_column else "unknown"
    frame["reference_datum"] = metadata["reference_datum"]
    frame["measurement_kind"] = metadata["measurement_kind"]
    metadata = {**metadata, "dataset_id": identifier, "original_timezone": metadata["timezone"], "timezone": "UTC",
                "source_filename": path.name,
                "imported_at_utc": datetime.now(timezone.utc).isoformat(),
                "column_mapping": {"timestamp": time_column, "level": level_column, "quality": quality_column,
                                   "unit": unit_column, "station": station_column, "sheet": sheet}}
    report = validate_dataset(frame, metadata)
    csv_path, report_path, manifest_path = (root / folder / f"{identifier}.{extension}" for folder, extension in
                                            (("processed", "csv"), ("reports", "json"), ("metadata", "json")))
    frame.to_csv(csv_path, index=False, mode="x")
    write_json(report_path, report)
    build_manifest(manifest_path, {**metadata, "record_count": len(frame), "collection_status": "imported" if report["valid"] else "validation_failed"},
                   [raw_path, raw_dir / "supplied_metadata.json"], csv_path, report_path)
    return {"csv": str(csv_path), "report": str(report_path), "manifest": str(manifest_path), "record_count": len(frame), "valid": report["valid"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--time-column", default="timestamp")
    parser.add_argument("--level-column", default="water_level")
    parser.add_argument("--quality-column")
    parser.add_argument("--unit-column")
    parser.add_argument("--station-column")
    parser.add_argument("--sheet", default="0", help="Sheet index (zero based) or name")
    args = parser.parse_args()
    try:
        result = import_water_level(args.file, json.loads(args.metadata.read_text(encoding="utf-8")), args.data_root,
                                    time_column=args.time_column, level_column=args.level_column,
                                    quality_column=args.quality_column, unit_column=args.unit_column,
                                    station_column=args.station_column, sheet=int(args.sheet) if args.sheet.isdecimal() else args.sheet)
    except (ValueError, OSError, KeyError, TypeError, ImportError) as error:
        parser.exit(1, f"Import failed: {error}\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
