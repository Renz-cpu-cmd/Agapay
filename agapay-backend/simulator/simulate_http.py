import argparse
import sys
import time

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send simulated AGAPAY readings to FastAPI."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--station-id", default="STATION_001")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument(
        "--start-sequence",
        type=int,
        default=None,
        help="Defaults to the current Unix time in milliseconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.count < 1:
        print("--count must be at least 1", file=sys.stderr)
        return 2
    if args.interval < 0:
        print("--interval cannot be negative", file=sys.stderr)
        return 2

    start_sequence = args.start_sequence or int(time.time() * 1000)
    endpoint = f"{args.url.rstrip('/')}/api/telemetry"

    # The development API is local. Ignoring system proxy variables prevents a
    # VPN or school proxy from trying to route 127.0.0.1 through the internet.
    with httpx.Client(timeout=10.0, trust_env=False) as client:
        for index in range(args.count):
            sensor_valid = (index + 1) % 13 != 0
            depth_cm = min(110.0, 25.0 + index * 5.0) if sensor_valid else None
            rainfall_mm = 0.70 if index % 3 == 0 else 0.0
            payload = {
                "station_id": args.station_id,
                "sequence_no": start_sequence + index,
                "water_depth_cm": depth_cm,
                "rainfall_mm": rainfall_mm,
                "sensor_quality": "valid" if sensor_valid else "invalid",
                "device_uptime_ms": index * int(max(args.interval, 0.001) * 1000),
                "firmware_version": "0.1.0-simulator",
            }

            try:
                response = client.post(endpoint, json=payload)
            except httpx.RequestError as exc:
                print(f"Cannot reach {endpoint}: {exc}", file=sys.stderr)
                return 1

            if response.status_code != 201:
                print(
                    f"FAILED {response.status_code}: {response.text}",
                    file=sys.stderr,
                )
                return 1

            stored = response.json()
            print(
                "STORED "
                f"seq={stored['sequence_no']} "
                f"depth={stored['water_depth_cm']}cm "
                f"rain={stored['rainfall_mm']}mm "
                f"quality={stored['sensor_quality']}"
            )
            if index + 1 < args.count:
                time.sleep(args.interval)

    print(f"Completed: {args.count} simulated readings stored successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
