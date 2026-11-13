"""Direct +1/+2/+3-hour rainfall regression with strictly causal features."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestRegressor
from app.ml.data_collection.build_manifest import file_record, run_id, write_json
from app.ml.data_collection.config import DATA_ROOT

DEFAULT_DATASET = DATA_ROOT / "processed/urdaneta_example_20261011T231532Z_ed4c1003e2e4.csv"
FEATURES = [f"rain_lag_{i}" for i in range(24)] + [f"rain_sum_{h}h" for h in (3, 6, 12, 24)] + ["hour_sin", "hour_cos", "weekday_sin", "weekday_cos", "month_sin", "month_cos"]


def load_rainfall(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["timestamp_utc"] = pd.to_datetime(frame.timestamp_utc, utc=True, errors="raise")
    rain = pd.to_numeric(frame.rainfall_mm, errors="raise")
    if frame.empty or not np.isfinite(rain).all() or rain.lt(0).any():
        raise ValueError("Rainfall needs finite nonnegative hourly amounts")
    if frame.station_id.nunique() != 1 or frame.dataset_source.nunique() != 1:
        raise ValueError("Use one identified dataset/location")
    if not frame.rainfall_interval_seconds.eq(3600).all() or not frame.timestamp_utc.diff().dropna().eq(pd.Timedelta(hours=1)).all():
        raise ValueError("Require consecutive ordered hourly observations; do not fill gaps")
    if not frame.timestamp_utc.dt.minute.eq(0).all() or not frame.timestamp_utc.dt.second.eq(0).all():
        raise ValueError("Rainfall must lie on UTC hour boundaries")
    frame["rainfall_mm"] = rain
    return frame


def causal_features(frame: pd.DataFrame) -> pd.DataFrame:
    rain = frame.rainfall_mm
    result = pd.DataFrame({f"rain_lag_{i}": rain.shift(i) for i in range(24)})
    for hours in (3, 6, 12, 24):
        result[f"rain_sum_{hours}h"] = rain.rolling(hours, min_periods=hours).sum()
    time = pd.to_datetime(frame.timestamp_utc, utc=True)
    for name, values, period in (("hour", time.dt.hour, 24), ("weekday", time.dt.dayofweek, 7), ("month", time.dt.month - 1, 12)):
        result[f"{name}_sin"] = np.sin(2 * np.pi * values / period)
        result[f"{name}_cos"] = np.cos(2 * np.pi * values / period)
    return result[FEATURES]


def training_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    features = causal_features(frame)
    targets = pd.DataFrame({f"rain_plus_{h}h": frame.rainfall_mm.shift(-h) for h in (1, 2, 3)})
    usable = features.notna().all(axis=1) & targets.notna().all(axis=1)
    return features.loc[usable], targets.loc[usable], frame.timestamp_utc.loc[usable]


def partition_masks(times: pd.Series) -> dict[str, pd.Series]:
    first, second = pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")
    end = times + pd.Timedelta(hours=3)
    return {"train": end.lt(first), "validation": times.ge(first) & end.lt(second), "test": times.ge(second)}


def metrics(truth: np.ndarray, predictions: np.ndarray) -> dict:
    def score(y, p):
        return {"count": int(y.size), "mae_mm": None if not y.size else float(np.mean(np.abs(y-p))),
                "rmse_mm": None if not y.size else float(np.sqrt(np.mean((y-p)**2)))}
    wet = truth >= 0.1
    return {"overall": score(truth, predictions), "wet_only": score(truth[wet], predictions[wet]),
            "by_horizon": {f"{h}h": {"overall": score(truth[:, h-1], predictions[:, h-1]),
                          "wet_only": score(truth[:, h-1][wet[:, h-1]], predictions[:, h-1][wet[:, h-1]])} for h in (1, 2, 3)}}


def export_forest(model: RandomForestRegressor) -> dict:
    trees = []
    for estimator in model.estimators_:
        tree = estimator.tree_
        trees.append({"left": tree.children_left.tolist(), "right": tree.children_right.tolist(),
                      "feature": tree.feature.tolist(), "threshold": tree.threshold.tolist(),
                      "value": tree.value[:, :, 0].tolist()})
    return {"features": FEATURES, "outputs": 3, "trees": trees}


def predict_export(forest: dict, values: list[float]) -> list[float]:
    values = np.asarray(values, dtype=np.float32)
    result = np.zeros(forest["outputs"])
    for tree in forest["trees"]:
        node = 0
        while tree["left"][node] != -1:
            node = tree["left"][node] if values[tree["feature"][node]] <= tree["threshold"][node] else tree["right"][node]
        result += tree["value"][node]
    return (result / len(forest["trees"])).tolist()


def train(dataset: Path = DEFAULT_DATASET, output: Path = DATA_ROOT / "models") -> dict:
    frame = load_rainfall(dataset)
    x, y, times = training_rows(frame)
    masks = partition_masks(times)
    if any(mask.sum() < 24 for mask in masks.values()):
        raise ValueError("Need data in 2020–2023 training, 2024 validation and 2025 test periods")
    candidates, fitted = [], []
    for depth in (6, 10):
        model = RandomForestRegressor(n_estimators=24, max_depth=depth, min_samples_leaf=16, random_state=42, n_jobs=1)
        model.fit(x.loc[masks["train"]], y.loc[masks["train"]])
        validation = metrics(y.loc[masks["validation"]].to_numpy(), model.predict(x.loc[masks["validation"]]))
        candidates.append({"max_depth": depth, "validation": validation})
        fitted.append(model)
    selected = min(range(len(candidates)), key=lambda i: candidates[i]["validation"]["overall"]["mae_mm"])
    model = fitted[selected]
    evaluation = {}
    for name in ("validation", "test"):
        mask = masks[name]
        truth = y.loc[mask].to_numpy()
        persistence = np.repeat(x.loc[mask, ["rain_lag_0"]].to_numpy(), 3, axis=1)
        evaluation[name] = {"random_forest": metrics(truth, model.predict(x.loc[mask])),
                            "persistence": metrics(truth, persistence), "zero_rainfall": metrics(truth, np.zeros_like(truth))}
    directory = output / run_id("hybrid_rain_v01")
    directory.mkdir(parents=True)
    joblib.dump(model, directory / "rainfall.joblib")
    exported = export_forest(model)
    # Browser/Python export parity must hold before a usable bundle is saved.
    sample = x.loc[masks["test"]].iloc[:100]
    np.testing.assert_allclose([predict_export(exported, row.tolist()) for _, row in sample.iterrows()], model.predict(sample), rtol=1e-10, atol=1e-10)
    write_json(directory / "forest.json", exported)
    metadata = {"version": directory.name, "trained_at_utc": datetime.now(timezone.utc).isoformat(),
                "dataset": file_record(dataset), "record_count": len(frame), "source": "Open-Meteo ERA5 gridded rainfall",
                "location_id": frame.station_id.iloc[0], "requested_coordinates": [15.97430, 120.56906],
                "target": "preceding-hour rainfall amount (mm), direct next 1/2/3 UTC hours",
                "water_level_training": False, "features": FEATURES, "random_seed": 42,
                "selected_max_depth": candidates[selected]["max_depth"], "candidate_validation": candidates,
                "splits": {name: {"count": int(mask.sum()), "start": times.loc[mask].min().isoformat(), "end": times.loc[mask].max().isoformat()} for name, mask in masks.items()},
                "split_policy": "Train only through 2023; choose depth on 2024; test 2025; purge +3h targets crossing boundaries; no refit on test or validation",
                "wet_period_definition": "target rainfall >=0.1 mm in the evaluated hour",
                "limitations": ["Reanalysis is revised/delayed, not live gauge input", "Rainfall metrics do not validate water depth", "Provisional point is not a confirmed river station"],
                "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
                "files": {name: file_record(directory / name) for name in ("rainfall.joblib", "forest.json")}}
    write_json(directory / "evaluation.json", evaluation)
    write_json(directory / "metadata.json", metadata)
    return {"directory": str(directory.resolve()), "metadata": metadata, "evaluation": evaluation}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DATA_ROOT / "models")
    args = parser.parse_args()
    result = train(args.dataset, args.output)
    print(json.dumps({"directory": result["directory"], "test": result["evaluation"]["test"]}, indent=2))


if __name__ == "__main__":
    main()
