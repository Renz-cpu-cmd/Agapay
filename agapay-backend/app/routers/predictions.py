from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import User
from app.prediction_schemas import ForecastStatus, PredictionResponse
from app.routers.telemetry import require_station
from app.services.accounts import current_user
from app.services.ml_predictor import get_predictor, predict_station, preview_station

router = APIRouter(prefix="/api/predictions", tags=["advisory predictions"])

def get_prediction_reader():
    from app.services.forecast_registry import read_latest
    return read_latest


@router.get("/{station_id}", response_model=PredictionResponse)
def forecast(station_id: str, mode: Literal["actual", "preview"] = "actual", scenario: ForecastStatus = "available",
             user: User = Depends(current_user), db: Session = Depends(get_db),
             settings: Settings = Depends(get_settings), reader=Depends(get_prediction_reader)):
    require_station(db, station_id)
    allowed = settings.environment == "development" and settings.prediction_preview_enabled
    if mode == "preview":
        if not allowed:
            raise HTTPException(403, "Forecast previews are disabled in this environment.")
        return preview_station(station_id, scenario)
    return reader(db, station_id, allowed)
