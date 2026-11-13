"""Package data, exported estimator and UI in one fully offline HTML file."""
import argparse
import json
from pathlib import Path
from .rainfall import DEFAULT_DATASET, load_rainfall
from app.ml.data_collection.build_manifest import write_json, file_record
from app.ml.data_collection.config import DATA_ROOT


def build(model_directory: Path, dataset: Path = DEFAULT_DATASET, output: Path | None = None) -> Path:
    output = output or DATA_ROOT / "demo" / model_directory.name
    output.mkdir(parents=True, exist_ok=True)
    frame = load_rainfall(dataset)
    # Demonstration uses the held-out year, including a preceding-day input window.
    frame = frame.loc[frame.timestamp_utc.ge("2024-12-31T00:00Z")].reset_index(drop=True)
    metadata = json.loads((model_directory / "metadata.json").read_text())
    if file_record(dataset)["sha256"] != metadata["dataset"]["sha256"]:
        raise ValueError("Dataset differs from the model's recorded training source")
    payload = {"start_utc": frame.timestamp_utc.iloc[0].isoformat(), "rainfall_mm": frame.rainfall_mm.tolist(),
               "metadata": metadata, "evaluation": json.loads((model_directory / "evaluation.json").read_text()),
               "forest": json.loads((model_directory / "forest.json").read_text())}
    template = Path(__file__).with_name("demo.html").read_text(encoding="utf-8")
    logic = Path(__file__).with_name("demo.js").read_text(encoding="utf-8")
    logic += "\n" + Path(__file__).with_name("live.js").read_text(encoding="utf-8")
    logic += "\n" + Path(__file__).with_name("live_ui.js").read_text(encoding="utf-8")
    html = template.replace("/*__DEMO_LOGIC__*/", logic).replace("/*__DEMO_PAYLOAD__*/", json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c"))
    target = output / "index.html"
    target.write_text(html, encoding="utf-8")
    # Generated bundles are replaceable derivatives; raw data/models are never rewritten.
    (output / "bundle_manifest.json").write_text(json.dumps({"html": file_record(target), "model_version": model_directory.name,
                                                "dataset": file_record(dataset), "offline": True}, indent=2), encoding="utf-8")
    return target.resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_directory", type=Path)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(build(args.model_directory, args.dataset, args.output))


if __name__ == "__main__":
    main()
