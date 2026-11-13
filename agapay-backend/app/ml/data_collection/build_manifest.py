"""Write-once manifests linking exact source bytes, CSV and quality reports."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


def run_id(label: str) -> str:
    return f"{label}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:12]}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)


def file_record(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path.resolve()), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def build_manifest(path: Path, metadata: dict, raw_paths: list[Path], csv_path: Path, report_path: Path) -> dict:
    manifest = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        **metadata,
        "raw_files": [file_record(p) for p in raw_paths],
        "processed_file": file_record(csv_path),
        "validation_report": file_record(report_path),
    }
    write_json(path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--raw", type=Path, nargs="+", required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_manifest(args.output, json.loads(args.metadata.read_text(encoding="utf-8")), args.raw, args.csv, args.report)


if __name__ == "__main__":
    main()
