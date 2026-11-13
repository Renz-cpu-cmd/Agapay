"""All observations here are synthetic test fixtures, never collected datasets."""
from datetime import date
import json
from pathlib import Path
import httpx
import pandas as pd
import pytest
from app.ml.data_collection.build_manifest import file_record, write_json
from app.ml.data_collection.collect_rainfall import collect, fetch, normalize
from app.ml.data_collection.config import RainfallConfig, VARIABLES, DATA_ROOT
from app.ml.data_collection.import_water_level import import_water_level
from app.ml.data_collection.validate_dataset import validate_dataset, utc_timestamp


def payload(times=None):
    times = times or [f"2020-01-01T{h:02}:00" for h in range(24)]
    return {"latitude": 16.0, "longitude": 120.5, "utc_offset_seconds": 0, "timezone": "GMT",
            "hourly_units": {v: unit for v, (_, unit) in VARIABLES.items()},
            "hourly": {"time": times, **{v: [1.0] * len(times) for v in VARIABLES}}}


def water_metadata():
    return {"station_id": "TEST_ONLY", "source": "pagasa", "latitude": 16, "longitude": 120,
            "timezone": "Asia/Manila", "reference_datum": "fixture gauge zero", "measurement_kind": "gauge_level",
            "units": {"water_level": "m"}, "interval_seconds": 1800, "acquisition_reference": "synthetic test only",
            "license": "test fixture", "jump_thresholds": {"water_level": 2}}


def test_default_root_and_batches():
    assert DATA_ROOT.name == "data" and DATA_ROOT.parent.name == "Agapay"
    config = RainfallConfig(start=date(2020, 12, 31), end=date(2021, 1, 2), batch_days=2)
    assert list(config.batches()) == [(date(2020, 12, 31), date(2021, 1, 1)), (date(2021, 1, 2), date(2021, 1, 2))]


def test_collection_preserves_source_provenance_and_no_overwrite(tmp_path):
    original = json.dumps(payload(), separators=(",", ":")).encode()
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=original)
    config = RainfallConfig(start=date(2020, 1, 1), end=date(2020, 1, 1), root=tmp_path)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first, second = collect(config, client), collect(config, client)
    assert first["record_count"] == 24 and first["valid"]
    assert first["csv"] != second["csv"]
    manifest = json.loads(Path(first["manifest"]).read_text())
    raw = Path(manifest["raw_files"][0]["path"])
    assert raw.read_bytes() == original
    assert file_record(raw)["sha256"] == manifest["raw_files"][0]["sha256"]
    assert requests[0].url.params["models"] == "era5"
    assert requests[0].url.params["timezone"] == "UTC"
    csv = pd.read_csv(first["csv"])
    assert csv.rainfall_mm.sum() == 24 and csv.precipitation_mm.sum() == 24


@pytest.mark.parametrize("status,retries", [(429, 3), (503, 3), (400, 1), (403, 1)])
def test_retry_policy(status, retries):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="Open-Meteo request failed"):
            fetch(client, {"start_date": "2020-01-01", "end_date": "2020-01-01"}, 3, sleep=lambda _: None)
    assert len(calls) == retries


def test_network_retry_recovers():
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("fixture", request=request)
        return httpx.Response(200, json=payload())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch(client, {"start_date": "x", "end_date": "y"}, 3, sleep=lambda _: None).status_code == 200
    assert len(calls) == 2


@pytest.mark.parametrize("defect", ["unit", "length", "timezone", "empty"])
def test_malformed_response(defect):
    data = payload()
    if defect == "unit": data["hourly_units"]["rain"] = "inch"
    if defect == "length": data["hourly"]["rain"] = []
    if defect == "timezone": data["utc_offset_seconds"] = 28800
    if defect == "empty": data["hourly"]["time"] = []
    with pytest.raises(ValueError):
        normalize(data, "TEST_ONLY")


def test_failed_normalization_retains_raw(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"error": True}))) as client:
        with pytest.raises(ValueError):
            collect(RainfallConfig(start=date(2020, 1, 1), end=date(2020, 1, 1), root=tmp_path), client)
    assert len(list((tmp_path / "raw").rglob("*.json"))) == 1
    assert len(list((tmp_path / "reports").glob("*_failure.json"))) == 1
    assert not list((tmp_path / "processed").glob("*.csv"))


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_import_preserves_gauge_semantics_and_timezone(tmp_path, extension):
    supplied = pd.DataFrame({"when": ["2020-01-01 08:00", "2020-01-01 08:30"], "level": ["-1.2", "2.4"], "flag": ["good", "suspect"]})
    source = tmp_path / f"fixture.{extension}"
    if extension == "csv": supplied.to_csv(source, index=False)
    else: supplied.to_excel(source, index=False)
    result = import_water_level(source, water_metadata(), tmp_path / "output", time_column="when", level_column="level", quality_column="flag")
    frame = pd.read_csv(result["csv"])
    assert frame.timestamp_utc.iloc[0] == "2020-01-01T00:00:00+00:00"
    assert frame.water_level.iloc[0] == -1.2
    assert frame.quality_flag.iloc[1] == "suspect"
    assert frame.reference_datum.iloc[0] == "fixture gauge zero"
    assert "water_depth_cm" not in frame
    report = json.loads(Path(result["report"]).read_text())
    assert "large_jump" in {i["code"] for i in report["issues"]}
    manifest = json.loads(Path(result["manifest"]).read_text())
    assert Path(manifest["raw_files"][0]["path"]).read_bytes() == source.read_bytes()


def test_import_flags_unit_station_and_malformed_values(tmp_path):
    path = tmp_path / "fixture.csv"
    path.write_text("timestamp,water_level,unit,station\nbad,nonsense,cm,OTHER\n2020-01-01 08:00,inf,m,TEST_ONLY\n", encoding="utf-8")
    result = import_water_level(path, water_metadata(), tmp_path / "output", unit_column="unit", station_column="station")
    report = json.loads(Path(result["report"]).read_text())
    assert not report["valid"]
    assert {"missing_or_malformed_timestamp", "invalid_numeric", "inconsistent_units", "identity_mismatch"} <= {i["code"] for i in report["issues"]}
    assert pd.read_csv(result["csv"]).shape[0] == 2


def test_validation_flags_all_temporal_defects():
    frame = normalize(payload(["2020-01-01T02:00", "2020-01-01T00:00", "2020-01-01T00:00", "bad"]), "TEST_ONLY")
    frame["rainfall_mm"] = frame.rainfall_mm.astype(object)
    frame.loc[0, "rainfall_mm"] = "bad"
    frame.loc[1, "temperature_c"] = None
    metadata = {"station_id": "TEST_ONLY", "source": "open_meteo_era5", "latitude": 16, "longitude": 120,
                "timezone": "UTC", "interval_seconds": 3600, "units": {column: unit for column, unit in VARIABLES.values()},
                "expected_start": "2020-01-01T00:00Z", "expected_end": "2020-01-01T03:00Z"}
    report = validate_dataset(frame, metadata)
    assert {"missing_or_malformed_timestamp", "duplicate_timestamp", "chronological_order", "irregular_interval",
            "missing_timestamps", "coverage_mismatch", "timezone_inconsistency", "invalid_numeric", "missing_measurement"} <= {i["code"] for i in report["issues"]}
    assert not report["valid"]


def test_timezone_and_write_once(tmp_path):
    assert utc_timestamp("2020-01-01T08:00+08:00", "Asia/Manila") == pd.Timestamp("2020-01-01T00:00Z")
    assert pd.isna(utc_timestamp("bad", "Asia/Manila"))
    assert pd.isna(utc_timestamp("01/02/2020 08:00", "Asia/Manila"))
    file = tmp_path / "metadata.json"
    write_json(file, {"test": True})
    with pytest.raises(FileExistsError): write_json(file, {})


def test_validation_geography_units_and_ranges():
    frame = normalize(payload(), "TEST_ONLY")
    frame.loc[0, "rainfall_mm"] = -1
    frame.loc[1, "relative_humidity_pct"] = 101
    metadata = {"station_id": "OTHER", "source": "open_meteo_era5", "latitude": 100, "longitude": 120,
                "timezone": "invalid-zone", "interval_seconds": 3600, "units": {"rainfall_mm": "inch", "relative_humidity_pct": "%"}}
    report = validate_dataset(frame, metadata)
    assert {"identity_mismatch", "invalid_geography", "timezone_inconsistency", "inconsistent_units", "suspicious_range"} <= {i["code"] for i in report["issues"]}
