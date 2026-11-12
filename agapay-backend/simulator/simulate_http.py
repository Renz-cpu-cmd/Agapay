import argparse
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlparse
from collections.abc import Iterator

import httpx


SCENARIOS = ("normal", "rising", "flash-flood", "recovery", "sensor-fault", "offline")


def scenario_reading(scenario: str, index: int, count: int, rng: random.Random) -> tuple[float | None, float, str]:
    progress = index / max(1, count - 1)
    noise = rng.uniform(-0.35, 0.35)
    if scenario == "normal":
        return round(38 + math.sin(index / 2) * 1.2 + noise, 2), 0.0 if index % 4 else 0.7, "valid"
    if scenario == "rising":
        return round(min(108, 42 + progress * 66 + noise), 2), round(0.7 + progress * 2.1, 2), "valid"
    if scenario == "flash-flood":
        depth = 40 + progress * 12 if progress < 0.35 else 58 + ((progress - 0.35) / 0.65) * 54
        return round(min(112, depth + noise), 2), round(1.4 + progress * 4.2, 2), "valid"
    if scenario == "recovery":
        return round(max(32, 108 - progress * 76 + noise), 2), round(max(0, 3.5 * (1 - progress)), 2), "valid"
    if scenario == "sensor-fault":
        if index < min(3, count):
            return round(64 + index * 0.4 + noise, 2), 0.7, "valid"
        return None, 0.0, "invalid"
    if scenario == "offline":
        return round(48 + math.sin(index) + noise, 2), 0.0, "valid"
    raise ValueError(f"Unknown scenario: {scenario}")


def readings(args: argparse.Namespace) -> Iterator[dict[str, object]]:
    rng = random.Random(args.seed)
    sequence = args.start_sequence or int(time.time() * 1000)
    boot_id = "SIM_" + uuid4().hex
    boot_sequence = getattr(args, "boot_sequence", 1)
    source_id = getattr(args, "device_id", "UNCONFIGURED_SIMULATOR")
    config_version = getattr(args, "config_version", 1)
    started_ns = time.monotonic_ns()
    index = 0
    while True:
        cycle_index = index % args.count
        depth, rainfall, quality = scenario_reading(args.scenario, cycle_index, args.count, rng)
        yield {
            "station_id": args.station_id,
            "schema_version": 2,
            "config_version": config_version,
            "source_id": source_id,
            "boot_id": boot_id,
            "boot_sequence": boot_sequence,
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "sequence_no": sequence + index,
            "water_depth_cm": depth,
            "rainfall_mm": rainfall,
            "sensor_quality": quality,
            "device_uptime_ms": (time.monotonic_ns() - started_ns) // 1_000_000,
            "firmware_version": "0.2.0-simulator",
        }
        index += 1
        if not args.loop and index >= args.count:
            return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send realistic virtual AGAPAY station readings to FastAPI."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--station-id", default="STATION_001")
    parser.add_argument("--device-id", required=True, help="Commissioned device_id (use a dedicated simulator station)")
    parser.add_argument("--config-version", type=int, required=True)
    parser.add_argument("--boot-sequence", type=int, required=True, help="Persist/increment between simulator runs; never reuse")
    parser.add_argument("--scenario", choices=SCENARIOS, default="rising")
    parser.add_argument("--count", type=int, default=16)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--loop", action="store_true", help="Repeat the selected profile until interrupted.")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without contacting the API.")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--start-sequence",
        type=int,
        default=None,
        help="Defaults to the current Unix time in milliseconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if any(getattr(args, field, 1) < 1 for field in ("boot_sequence", "config_version")):
        print("--boot-sequence and --config-version must be positive", file=sys.stderr)
        return 2
    if args.count < 2:
        print("--count must be at least 2", file=sys.stderr)
        return 2
    if args.interval < 0:
        print("--interval cannot be negative", file=sys.stderr)
        return 2

    endpoint = f"{args.url.rstrip('/')}/api/exercises/telemetry"
    token = os.environ.get("AGAPAY_STATION_INGEST_TOKEN", "").strip()
    if not args.dry_run:
        if not token.startswith("agi_") or len(token) != 47:
            print("Set AGAPAY_STATION_INGEST_TOKEN to this station's provisioned token; staff sessions are not ingestion credentials.", file=sys.stderr)
            return 2
        destination = urlparse(endpoint)
        if destination.scheme != "https" and destination.hostname not in ("127.0.0.1", "localhost", "::1"):
            print("Use HTTPS for ingestion outside a loopback development server.", file=sys.stderr)
            return 2
    sent = 0
    client = None if args.dry_run else httpx.Client(timeout=10.0, trust_env=False, headers={"Authorization": "Bearer " + token})
    print(f"AGAPAY virtual station | {args.station_id} | scenario={args.scenario}")
    try:
        for payload in readings(args):
            if args.dry_run:
                print(json.dumps(payload, separators=(",", ":")))
            else:
                try:
                    response = client.post(endpoint, json=payload)
                except httpx.RequestError as exc:
                    print(f"Cannot reach {endpoint}: {exc}", file=sys.stderr)
                    return 1
                if response.status_code != 201:
                    print(f"FAILED {response.status_code}: verify station commissioning, credential scope/expiry and ingest budget.", file=sys.stderr)
                    return 1
                stored = response.json()
                print(
                    f"STORED seq={stored['sequence_no']} "
                    f"depth={stored['water_depth_cm']}cm "
                    f"rain={stored['rainfall_mm']}mm "
                    f"quality={stored['sensor_quality']}"
                )
            sent += 1
            if args.loop or sent < args.count:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        if client is not None:
            client.close()

    print(f"Completed: {sent} simulated readings.")
    if args.scenario == "offline" and not args.loop:
        print("Telemetry has stopped. The apps will mark the station offline after the configured freshness window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
