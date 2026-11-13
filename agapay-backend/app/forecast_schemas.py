from datetime import datetime
from typing import Literal
from pydantic import AwareDatetime,BaseModel,ConfigDict,Field,model_validator
from app.prediction_schemas import PredictionResponse,PublishedPredictionResponse

class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class ModelCard(Contract):
    station_id:str=Field(pattern=r'^[A-Z0-9_-]{3,50}$')
    target:Literal['local_sensor_depth_above_datum']='local_sensor_depth_above_datum'
    units:Literal['cm']='cm'
    datum:str=Field(min_length=3,max_length=200)
    configuration_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    source_class:Literal['physical_field','synthetic_fixture']
    data_license:str=Field(min_length=5,max_length=1000)
    provenance:str=Field(min_length=10,max_length=2000)
    calibration_history:str=Field(min_length=10,max_length=2000)
    training_cutoff:AwareDatetime
    features:Literal['depth_cm,rate_cm_per_minute']='depth_cm,rate_cm_per_minute'
    inference_availability:Literal['observations_received_by_issue_time']='observations_received_by_issue_time'
    allowed_use:Literal['advisory_only']='advisory_only'
    fallback:Literal['unavailable_measured_observations_remain_visible']='unavailable_measured_observations_remain_visible'
    limitations:str=Field(min_length=20,max_length=3000)
    dataset_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')

class ReviewRequest(Contract):
    expected_version:int=Field(ge=0)
    decision:Literal['approved','revoked']
    reason:str=Field(min_length=8,max_length=500)
    evidence_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')

class DeploymentRequest(Contract):
    expected_version:int=Field(ge=0)
    model_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    configuration_hash:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    reason:str=Field(min_length=8,max_length=500)

class ForecastEnvelope(Contract):
    schema_version:Literal['1.0']='1.0'
    product:PublishedPredictionResponse
    read_at:AwareDatetime
    current:bool
    notice:Literal['Historical product; never extend its original expiry']='Historical product; never extend its original expiry'

class ErrorScore(Contract):
    count:int=Field(ge=1)
    mae_cm:float=Field(ge=0)
    rmse_cm:float=Field(ge=0)
    bias_cm:float
    maximum_absolute_error_cm:float=Field(ge=0)

class CandidateRead(Contract):
    id:str
    card:ModelCard
    state:Literal['draft','approved','revoked']
    version:int=Field(ge=0)
    evaluation:dict[str,dict[str,ErrorScore]]
    decision_evaluation:dict

class CatalogResponse(Contract):
    checked_at:AwareDatetime
    operational:list[CandidateRead]=Field(max_length=100)
    experimental:dict

class DeploymentRead(Contract):
    station_id: str
    version: int
    model_id: str | None
    configuration_hash: str | None
    model_review_version: int | None

class ModelStateRead(Contract):
    id: str
    state: str
    version: int
    evidence_sha256: str | None

class ForecastWorkspaceResponse(Contract):
    station_id: str
    checked_at: AwareDatetime
    deployment: DeploymentRead
    model: ModelStateRead | None
    publication_status: str
    publication_reason: str
    current_forecast_id: str | None
    products: list[ForecastEnvelope] = Field(max_length=20)
    total: int
    has_more: bool
