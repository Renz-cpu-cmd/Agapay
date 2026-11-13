"""Mode boundaries: archived future values are available only in replay."""
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .rainfall import causal_features, load_rainfall, predict_export
from .hydrology import Basin, project, sensor_initial


class DemoEngine:
    def __init__(self, model_directory: Path, dataset: Path):
        self.forest = json.loads((model_directory / "forest.json").read_text())
        self.metadata = json.loads((model_directory / "metadata.json").read_text())
        self.frame = load_rainfall(dataset)

    def run(self, *, mode: str, initial_cm: float, basin: Basin, as_of: str,
            current_history: list[dict] | None = None, sensor: dict | None = None,
            now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        origin = pd.Timestamp(as_of)
        if origin.tzinfo is None or origin.minute != 0 or origin.second != 0:
            raise ValueError("Rainfall origin must be an explicit timezone-aware hourly boundary")
        origin = origin.tz_convert("UTC")
        if sensor is not None:
            if mode != "ml_current":
                raise ValueError("A current sensor measurement cannot initialize an archived simulation")
            initial_cm = sensor_initial(sensor, now)
        if mode == "ml_current":
            if not current_history or not 0 <= (now - origin.to_pydatetime()).total_seconds() < 3600:
                raise ValueError("Current mode needs recent supplied rainfall; archive cannot be substituted")
            history = pd.DataFrame(current_history)
            history["timestamp_utc"] = pd.to_datetime(history.timestamp_utc, utc=True, errors="raise")
            values = pd.to_numeric(history.rainfall_mm, errors="raise")
            if len(history) != 24 or not np.isfinite(values).all() or values.lt(0).any() or history.timestamp_utc.iloc[-1] != origin or not history.timestamp_utc.diff().dropna().eq(pd.Timedelta(hours=1)).all():
                raise ValueError("Supply exactly 24 consecutive finite nonnegative completed-hour rainfall observations ending at origin")
            history["rainfall_mm"] = values
            projection_at = now
            rain = predict_export(self.forest, causal_features(history).iloc[-1].tolist())
            rain_source = "ML prediction from user-supplied current hourly rainfall; source transfer unvalidated"
        elif mode in ("historical_replay", "ml_backtest"):
            matching = self.frame.index[self.frame.timestamp_utc.eq(origin)]
            if len(matching) != 1 or matching[0] < 23 or matching[0] + 3 >= len(self.frame):
                raise ValueError("Archived date needs preceding 24 hours and three following hours")
            index = int(matching[0])
            history = self.frame.iloc[index-23:index+1]
            projection_at = origin.to_pydatetime()
            if mode == "historical_replay":
                rain = self.frame.rainfall_mm.iloc[index+1:index+4].tolist()
                rain_source = "Archived future ERA5 rainfall used for historical simulation only"
            else:
                if origin < pd.Timestamp("2025-01-01", tz="UTC"):
                    raise ValueError("Archived ML demonstration must use held-out 2025 observations")
                rain = predict_export(self.forest, causal_features(history.reset_index(drop=True)).iloc[-1].tolist())
                rain_source = "ML rainfall prediction from archived past inputs; historical backtest, not a live forecast"
        else:
            raise ValueError("Unknown projection mode")
        result = project(initial_cm, rain, basin, projection_at, rainfall_origin=origin.to_pydatetime())
        result.update(mode=mode, model_version=self.metadata["version"], created_at_utc=now.isoformat(),
                      initial_source="registry-verified physical source" if sensor is not None else "manual configured depth",
                      initial_observed_at=sensor.get("last_valid_depth_at") if sensor is not None else None,
                      rainfall_hourly_mm=rain, rainfall_source=rain_source,
                      historical_rainfall=history[["timestamp_utc", "rainfall_mm"]].assign(timestamp_utc=lambda f: f.timestamp_utc.map(lambda t: t.isoformat())).to_dict("records"))
        return result
