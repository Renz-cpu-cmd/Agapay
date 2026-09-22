"""Export language-neutral prediction contracts: python -m app.export_prediction_contracts."""
import json
from pathlib import Path

from app.prediction_schemas import ModelOutput, PredictionInput, PredictionResponse


def main():
    destination = Path(__file__).resolve().parents[2] / "agapay-docs" / "contracts"
    destination.mkdir(parents=True, exist_ok=True)
    for name, contract in (
        ("prediction-input", PredictionInput),
        ("prediction-model-output", ModelOutput),
        ("prediction-response", PredictionResponse),
    ):
        path = destination / f"{name}.schema.json"
        path.write_text(json.dumps(contract.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
