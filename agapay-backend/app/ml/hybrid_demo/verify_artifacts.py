"""Verify the trusted local model, browser estimator and physical-model parity."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import joblib
import numpy as np
from .rainfall import load_rainfall, training_rows, partition_masks, DEFAULT_DATASET
from .hydrology import Basin, project
from dataclasses import asdict
from app.ml.data_collection.build_manifest import file_record


def verify(directory: Path, dataset: Path, node: str = "node") -> dict:
    metadata = json.loads((directory / "metadata.json").read_text())
    for name, record in metadata["files"].items():
        if file_record(directory / name)["sha256"] != record["sha256"]:
            raise ValueError(f"Artifact hash mismatch: {name}")
    if file_record(dataset)["sha256"] != metadata["dataset"]["sha256"]:
        raise ValueError("Dataset hash mismatch")
    # Only load this task's trusted locally trained estimator; never untrusted pickles.
    model = joblib.load(directory / "rainfall.joblib")
    forest = json.loads((directory / "forest.json").read_text())
    frame = load_rainfall(dataset)
    x, _, times = training_rows(frame)
    selected = x.loc[partition_masks(times)["test"]].iloc[::87][:100]
    positions = selected.index.tolist()
    rows = [{"history": frame.rainfall_mm.iloc[i-23:i+1].tolist(), "asof": frame.timestamp_utc.iloc[i].isoformat()} for i in positions]
    basin = Basin()
    source = Path(__file__).with_name("demo.js").resolve()
    code = "const H=require(process.argv[1]);let raw='';process.stdin.on('data',c=>raw+=c);process.stdin.on('end',()=>{const d=JSON.parse(raw);process.stdout.write(JSON.stringify({predictions:d.rows.map(r=>H.predict(d.forest,H.featureVector(r.history,r.asof))),points:H.project(20,[4,8,12],d.basin,45)}));});"
    result = subprocess.run([node, "-e", code, str(source)], input=json.dumps({"forest":forest,"rows":rows,"basin":asdict(basin)}),
                            capture_output=True, text=True, check=True, timeout=30)
    actual = json.loads(result.stdout)
    predicted = model.predict(selected)
    np.testing.assert_allclose(actual["predictions"], predicted, rtol=1e-10, atol=1e-10)
    at = datetime(2026,10,12,1,45,tzinfo=timezone.utc)
    expected = project(20,[4,8,12],basin,at,rainfall_origin=at.replace(minute=0))["points"]
    for left,right in zip(expected,actual["points"]):
        for key in ("depth_cm","rainfall_mm","inflow_m3","outflow_m3","overflow_m3","unmet_outflow_m3"):
            np.testing.assert_allclose(left[key],right[key],atol=1e-12)
    return {"model_version":metadata["version"],"hashes_match":True,"browser_sklearn_origins":len(selected),
            "maximum_prediction_difference_mm":float(np.max(np.abs(np.asarray(actual['predictions'])-predicted))),
            "python_browser_volume_balance_parity":True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--dataset",type=Path,default=DEFAULT_DATASET)
    parser.add_argument("--node",default="node")
    args=parser.parse_args()
    print(json.dumps(verify(args.directory,args.dataset,args.node),indent=2))


if __name__ == "__main__":
    main()
