"""Volume-conserving controlled-basin model; never writes telemetry or alerts."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
import math

NOTICE = "EXPERIMENTAL — NOT VALIDATED FOR REAL-WORLD FLOOD WARNING"


@dataclass(frozen=True)
class Basin:
    contributing_area_m2: float = 2.0
    basin_surface_area_m2: float = 0.1
    runoff_coefficient: float = 0.8
    outflow_m3_per_hour: float = 0.0
    maximum_depth_cm: float = 100.0
    parameter_basis: dict[str, str] = field(default_factory=lambda: {key: "assumed" for key in (
        "contributing_area_m2", "basin_surface_area_m2", "runoff_coefficient", "outflow_m3_per_hour", "maximum_depth_cm")})

    def __post_init__(self):
        values = (self.contributing_area_m2, self.basin_surface_area_m2, self.runoff_coefficient, self.outflow_m3_per_hour, self.maximum_depth_cm)
        if not all(math.isfinite(v) for v in values) or self.contributing_area_m2 < 0 or self.basin_surface_area_m2 <= 0 or not 0 <= self.runoff_coefficient <= 1 or self.outflow_m3_per_hour < 0 or self.maximum_depth_cm <= 0:
            raise ValueError("Invalid controlled-basin physical parameters")
        if set(self.parameter_basis) != set(asdict(self)) - {"parameter_basis"} or any(v not in ("measured", "estimated", "assumed") for v in self.parameter_basis.values()):
            raise ValueError("Every physical parameter needs measured/estimated/assumed provenance")


def water_balance(depth_cm: float, rainfall_mm: float, minutes: float, basin: Basin) -> dict:
    if not all(math.isfinite(v) for v in (depth_cm, rainfall_mm, minutes)) or not 0 <= depth_cm <= basin.maximum_depth_cm or rainfall_mm < 0 or minutes <= 0:
        raise ValueError("Depth, rainfall and interval must be valid; initial depth must fit the basin")
    inflow = rainfall_mm / 1000 * basin.contributing_area_m2 * basin.runoff_coefficient
    stored = depth_cm / 100 * basin.basin_surface_area_m2
    requested_outflow = basin.outflow_m3_per_hour * minutes / 60
    outflow = min(requested_outflow, stored + inflow)
    capacity = basin.maximum_depth_cm / 100 * basin.basin_surface_area_m2
    remaining = stored + inflow - outflow
    overflow = max(0.0, remaining - capacity)
    return {"depth_cm": min(basin.maximum_depth_cm, max(0.0, min(capacity, remaining) / basin.basin_surface_area_m2 * 100)),
            "inflow_m3": inflow, "outflow_m3": outflow, "overflow_m3": overflow,
            "unmet_outflow_m3": requested_outflow - outflow}


def project(initial_cm: float, hourly_rainfall_mm: list[float], basin: Basin,
            generated_at: datetime, *, rainfall_origin: datetime | None = None) -> dict:
    if generated_at.tzinfo is None:
        raise ValueError("Projection time must have a timezone")
    origin = rainfall_origin or generated_at
    offset = (generated_at - origin).total_seconds() / 60
    if origin.tzinfo is None or not 0 <= offset < 60 or len(hourly_rainfall_mm) < 3 or any(not math.isfinite(v) or v < 0 for v in hourly_rainfall_mm):
        raise ValueError("Need three hourly rainfall predictions and a preceding-hour origin within 60 minutes")
    depth, points = initial_cm, []
    water_balance(depth, 0, 1, basin)  # validate initial condition, including finite bounds
    for end in (30, 60, 90):
        cursor, stop = offset + end - 30, offset + end
        inflow = outflow = overflow = unmet = rain = 0.0
        while cursor < stop - 1e-9:
            hour = int(cursor // 60)
            duration = min(stop - cursor, 60 - cursor % 60)
            amount = hourly_rainfall_mm[hour] * duration / 60
            step = water_balance(depth, amount, duration, basin)
            depth = step["depth_cm"]
            inflow += step["inflow_m3"]; outflow += step["outflow_m3"]
            overflow += step["overflow_m3"]; unmet += step["unmet_outflow_m3"]; rain += amount
            cursor += duration
        points.append({"horizon_minutes": end, "target_at": (generated_at + timedelta(minutes=end)).isoformat(),
                       "depth_cm": depth, "rainfall_mm": rain, "inflow_m3": inflow, "outflow_m3": outflow,
                       "overflow_m3": overflow, "unmet_outflow_m3": unmet})
    return {"notice": NOTICE, "advisory_only": True, "initial_depth_cm": initial_cm,
            "generated_at": generated_at.isoformat(), "rainfall_origin": origin.isoformat(),
            "parameters": asdict(basin), "assumption": "Uniform rainfall within each forecast hour; half-hour amounts are allocations, not independent forecasts",
            "points": points}


def sensor_initial(sample: dict, now: datetime, stale_after_seconds: int = 30) -> float:
    """Require registry-owned provenance and freshness of the actual depth."""
    if (sample.get("source_class") != "physical_device" or sample.get("source_trusted") is not True
            or sample.get("hazard_review_required") is True
            or sample.get("depth_source_trusted") is not True or sample.get("stream") != "operational"
            or sample.get("depth_fresh") is not True or sample.get("heartbeat_fresh") is not True
            or sample.get("sensor_quality") != "valid" or not sample.get("is_online")):
        raise ValueError("A fresh valid depth from a registry-verified operational physical source is required")
    depth = sample.get("current_depth_cm")
    if depth is None or not math.isfinite(depth) or depth < 0:
        raise ValueError("Missing or invalid depth")
    try:
        observed = datetime.fromisoformat(sample["last_valid_depth_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or now.tzinfo is None or not 0 <= (now - observed).total_seconds() <= stale_after_seconds:
            raise ValueError("Stale or future sensor timestamp")
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Missing sensor observation timestamp") from error
    return depth
