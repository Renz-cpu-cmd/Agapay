from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.config import Settings,get_settings
from app.services.accounts import current_user
from app.services import forecast_registry as registry
from app.forecast_schemas import ReviewRequest,DeploymentRequest,ForecastEnvelope,CatalogResponse,CandidateRead,ForecastWorkspaceResponse
from app.routers.telemetry import require_station
from app.hybrid_schemas import RainActivityResponse
from app.models import utc_now

router=APIRouter(tags=['published advisory forecasts'])

@router.get('/api/rain-activity/{station_id}',response_model=RainActivityResponse)
def rain_activity(station_id:str,db:Session=Depends(get_db),settings:Settings=Depends(get_settings),user:User=Depends(current_user)):
    import sqlite3
    from pathlib import Path
    from app.services.rain_gauge_service import RainGaugeStore
    require_station(db,station_id);now=utc_now();snapshot=None
    if settings.rain_gauge_enabled:
        try:snapshot=RainGaugeStore(Path(settings.rain_gauge_store_path),read_only=True,raw_retention_days=settings.rain_raw_retention_days).snapshot(station_id,'physical_rain_gauge',now=now)
        except (OSError,ValueError,sqlite3.Error):pass
    return dict(station_id=station_id,checked_at=now,rain_activity=snapshot)
def staff(user:User=Depends(current_user)):
    if user.role not in ('admin','officer'):raise HTTPException(403,'Staff access required')
    return user

@router.get('/api/forecast-registry',response_model=CatalogResponse)
def catalog(db:Session=Depends(get_db),settings:Settings=Depends(get_settings),user:User=Depends(staff)):
    return registry.catalog(db,settings)

@router.get('/api/forecast-workspaces/{station_id}',response_model=ForecastWorkspaceResponse)
def workspace(station_id:str,limit:int=Query(5,ge=1,le=20),offset:int=Query(0,ge=0),
              db:Session=Depends(get_db),user:User=Depends(staff)):
    require_station(db,station_id)
    return registry.workspace(db,station_id,limit,offset)

@router.get('/api/forecast-registry/{identity}/evidence',response_model=CandidateRead)
def deployed_evidence(identity:str,db:Session=Depends(get_db),user:User=Depends(staff)):
    return registry.candidate_evidence(db,identity)

@router.post('/api/forecast-registry/{identity}/review')
def review(identity:str,payload:ReviewRequest,db:Session=Depends(get_db),user:User=Depends(staff)):
    return registry.review(db,user,identity,payload)

@router.get('/api/forecast-deployments/{station_id}')
def deployment(station_id:str,db:Session=Depends(get_db),user:User=Depends(staff)):
    require_station(db,station_id);return registry.deployment(db,station_id)

@router.post('/api/forecast-deployments/{station_id}')
def configure(station_id:str,payload:DeploymentRequest,db:Session=Depends(get_db),user:User=Depends(staff)):
    return registry.configure(db,user,station_id,payload)

@router.get('/api/forecasts/{identity}',response_model=ForecastEnvelope)
def historical(identity:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    return registry.historical(db,identity)
