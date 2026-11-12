import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.export_prediction_contracts import artifacts
from app.prediction_schemas import PublishedPredictionResponse

ROOT=Path(__file__).resolve().parents[2]
def test_generated_contracts_match_the_actual_openapi():
    for path,expected in artifacts().items():assert path.read_text(encoding='utf-8')==expected,str(path)

@pytest.mark.parametrize('case',json.loads((ROOT/'agapay-docs/contracts/published-forecast-cases.json').read_text(encoding='utf-8')),ids=lambda case:case['name'])
def test_shared_cross_client_cases(case):
    if case['valid']:assert PublishedPredictionResponse.model_validate(case['value']).forecast_id
    else:
        with pytest.raises(ValidationError):PublishedPredictionResponse.model_validate(case['value'])
