"""Download documented hourly ERA5 data, preserving exact HTTP response bytes."""
import argparse
from datetime import date, datetime, time as dt_time, timezone
import json
import logging
from pathlib import Path
import time
import httpx
import pandas as pd
from .build_manifest import build_manifest, run_id, write_json
from .config import ARCHIVE_URL, DATA_ROOT, VARIABLES, RainfallConfig, create_layout
from .validate_dataset import validate_dataset

log = logging.getLogger(__name__)


def fetch(client: httpx.Client, params: dict, attempts: int, sleep=time.sleep) -> httpx.Response:
    for attempt in range(attempts):
        try:
            response = client.get(ARCHIVE_URL, params=params)
            response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.HTTPStatusError) as error:
            retryable = not isinstance(error, httpx.HTTPStatusError) or error.response.status_code in (429, 500, 502, 503, 504)
            if not retryable or attempt == attempts - 1:
                status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else type(error).__name__
                raise RuntimeError(f"Open-Meteo request failed ({status}) for {params['start_date']} through {params['end_date']}") from error
            delay = min(2 ** attempt, 30)
            if isinstance(error, httpx.HTTPStatusError):
                try:
                    delay = min(max(delay, float(error.response.headers.get('Retry-After', delay))), 60)
                except ValueError:
                    pass
            log.warning("Transient download failure; attempt %d/%d, retry in %.1fs", attempt + 1, attempts, delay)
            sleep(delay)
    raise RuntimeError("No request attempts configured")


def normalize(payload: dict, station_id: str) -> pd.DataFrame:
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("API returned an error or unsupported response structure")
    if payload.get("utc_offset_seconds") != 0 or payload.get("timezone") not in ("GMT", "UTC", "Etc/GMT", "Etc/UTC"):
        raise ValueError("Expected an explicitly requested UTC API response")
    hourly = payload.get("hourly", {})
    timestamps = hourly.get("time")
    if not isinstance(timestamps, list) or not timestamps:
        raise ValueError("API response has no hourly timestamps")
    columns = {"timestamp_original": timestamps}
    for variable, (column, expected_unit) in VARIABLES.items():
        values = hourly.get(variable)
        if not isinstance(values, list) or len(values) != len(timestamps):
            raise ValueError(f"Missing or unequal hourly array: {variable}")
        if payload.get("hourly_units", {}).get(variable) != expected_unit:
            raise ValueError(f"Unexpected unit for {variable}; expected {expected_unit}")
        columns[column] = values
    frame = pd.DataFrame(columns)
    times = pd.to_datetime(frame.timestamp_original, errors="coerce", format="mixed", utc=True)
    frame.insert(0, "timestamp_utc", times.map(lambda t: None if pd.isna(t) else t.isoformat()))
    frame["station_id"] = station_id
    frame["dataset_source"] = "open_meteo_era5"
    frame["rainfall_interval_seconds"] = 3600
    return frame


def collect(config: RainfallConfig, client: httpx.Client | None = None) -> dict:
    if client is None:
        with httpx.Client(timeout=config.timeout, follow_redirects=False) as owned:
            return collect(config, owned)
    create_layout(config.root)
    identifier = run_id(config.location_id)
    raw_dir = config.root / "raw" / "open_meteo" / identifier
    raw_dir.mkdir()
    raw_paths, batches, frames = [], [], []
    try:
        for start, end in config.batches():
            params = {"latitude": config.latitude, "longitude": config.longitude,
                      "start_date": start.isoformat(), "end_date": end.isoformat(),
                      "hourly": ",".join(VARIABLES), "models": "era5", "timezone": "UTC",
                      "temperature_unit": "celsius", "precipitation_unit": "mm", "timeformat": "iso8601"}
            log.info("Collecting %s through %s", start, end)
            response = fetch(client, params, config.attempts)
            raw_path = raw_dir / f"{start}_{end}.json"
            with raw_path.open("xb") as handle:
                handle.write(response.content)
            raw_paths.append(raw_path)
            payload = response.json()
            batches.append({"requested_parameters": params, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                            "url": str(response.request.url), "http_status": response.status_code,
                            "response_metadata": {k: v for k, v in payload.items() if k not in ("hourly",)}})
            frames.append(normalize(payload, config.location_id))
        frame = pd.concat(frames, ignore_index=True)
        csv_path = config.root / "processed" / f"{identifier}.csv"
        frame.to_csv(csv_path, index=False, mode="x")
        metadata = {"dataset_id": identifier, "station_id": config.location_id, "source": "open_meteo_era5",
                    "data_kind": "gridded_reanalysis", "station_confirmed": False,
                    "latitude": config.latitude, "longitude": config.longitude, "timezone": "UTC",
                    "original_timezone": "UTC", "interval_seconds": 3600,
                    "expected_start": datetime.combine(config.start, dt_time(0), timezone.utc).isoformat(),
                    "expected_end": datetime.combine(config.end, dt_time(23), timezone.utc).isoformat(),
                    "units": {column: unit for column, unit in VARIABLES.values()},
                    "jump_thresholds": {"precipitation_mm": 100, "rainfall_mm": 100, "temperature_c": 15},
                    "timestamp_semantics": "rain and precipitation are preceding-hour sums; temperature/humidity instantaneous",
                    "license": "CC BY 4.0 data attribution; free API non-commercial terms apply",
                    "documentation": "https://open-meteo.com/en/docs/historical-weather-api", "batches": batches}
        report = validate_dataset(frame, metadata)
        report_path = config.root / "reports" / f"{identifier}.json"
        write_json(report_path, report)
        manifest_path = config.root / "metadata" / f"{identifier}.json"
        manifest = build_manifest(manifest_path, {**metadata, "record_count": len(frame), "collection_status": "complete" if report["valid"] else "validation_failed"}, raw_paths, csv_path, report_path)
        return {"csv": str(csv_path), "manifest": str(manifest_path), "report": str(report_path),
                "record_count": len(frame), "valid": report["valid"], "dataset_id": manifest["dataset_id"]}
    except Exception as error:
        write_json(config.root / "reports" / f"{identifier}_failure.json", {
            "dataset_id": identifier, "collection_status": "failed", "error_type": type(error).__name__,
            "error": str(error), "retained_raw_files": [str(p) for p in raw_paths], "completed_batches": batches,
            "requested_start": str(config.start), "requested_end": str(config.end),
            "note": "Partial source responses retained. No substitute observations generated."})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latitude", type=float, default=15.97430)
    parser.add_argument("--longitude", type=float, default=120.56906)
    parser.add_argument("--location-id", default="urdaneta_example")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2020, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--batch-days", type=int, default=366)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        result = collect(RainfallConfig(args.latitude, args.longitude, args.location_id, args.start, args.end,
                                       args.batch_days, args.timeout, args.attempts, args.data_root))
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"Collection failed: {error}\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
