from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Station, StationAuditEvent, StationCredential, StationIdentity, StationSourceRegistry, User, utc_now
from app.schemas import StationRead
from app.station_schemas import (CommissionRead, CommissionRequest, CredentialIssued, CredentialRead,
                                 CredentialRequest, RevokeRequest, StationAuditRead, StationProvisionRequest)
from app.services.accounts import require_admin
from app.services.station_security import audit, commission, commit_security, issue_credential, lock_station


router = APIRouter(prefix="/api/stations", tags=["stations"])

from app.device_config import ConfigurationRequest,configuration_contract,current_configuration,save_configuration
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from app.services.accounts import current_user
from app.services.station_lifecycle import contract as lifecycle_contract,touch as touch_lifecycle


class LifecycleWrite(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=0)
    expected_identity_version:int=Field(ge=1)
    state:Literal['active','maintenance','inactive','decommissioned']
    reason:str=Field(min_length=3,max_length=500)


class MetadataWrite(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=0)
    station_name:str|None=Field(default=None,min_length=1,max_length=255)
    barangay:str|None=Field(default=None,max_length=255)
    municipality:str|None=Field(default=None,max_length=255)
    reason:str=Field(min_length=3,max_length=500)


def operations_contract(db,station):
    return {**lifecycle_contract(db,station),'station_id':station.station_id,'station_name':station.station_name,
        'barangay':station.barangay,'municipality':station.municipality}


@router.get('/{station_id}/operations')
def read_operations(station_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if user.role not in ('admin','officer'):raise HTTPException(403,'Staff lifecycle access required')
    station=db.scalar(select(Station).where(Station.station_id==station_id))
    if not station:raise HTTPException(404,'Station not found')
    return operations_contract(db,station)


@router.patch('/{station_id}/metadata')
def update_metadata(station_id:str,payload:MetadataWrite,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    station=lock_station(db,station_id)
    current=lifecycle_contract(db,station)
    if current['revision']!=payload.expected_revision:raise HTTPException(409,'Station metadata changed; refresh and review manually')
    changes=payload.model_dump(include={'station_name','barangay','municipality'},exclude_unset=True)
    if not changes or ('station_name' in changes and (changes['station_name'] is None or not changes['station_name'].strip())):
        raise HTTPException(422,'Supply station metadata; station name cannot be empty')
    before={key:getattr(station,key) for key in changes}
    for key,value in changes.items():setattr(station,key,value.strip() if isinstance(value,str) else value)
    touch_lifecycle(db,station,admin,payload.reason)
    audit(db,station,admin,'station_metadata_updated',payload.reason,{'before':before,'after':changes})
    commit_security(db)
    return operations_contract(db,station)


@router.post('/{station_id}/lifecycle')
def update_lifecycle(station_id:str,payload:LifecycleWrite,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    station=lock_station(db,station_id)
    current=lifecycle_contract(db,station)
    identity=db.get(StationIdentity,station_id,populate_existing=True)
    if current['revision']!=payload.expected_revision or not identity or identity.version!=payload.expected_identity_version:
        raise HTTPException(409,'Lifecycle or commissioning changed; refresh and review manually')
    if current['state']==payload.state:raise HTTPException(409,'Station already has this lifecycle state')
    if payload.state=='decommissioned':
        registry=db.get(StationSourceRegistry,(station_id,identity.version))
        from app.station_schemas import Commissioning
        review=Commissioning(device_id=identity.device_id,state='decommissioned',coordinates_verified=identity.coordinates_verified,
            reference_datum=identity.reference_datum,calibration_note=identity.calibration_note,reason=payload.reason,
            source_class=registry.source_class if registry else 'unverified',stream=registry.stream if registry else 'exercise',
            provenance_evidence=registry.evidence if registry else 'No source review')
        commission(db,station,review,admin,expected_version=identity.version)
    else:
        if identity.state!='commissioned':raise HTTPException(409,'Commission the source identity before changing operational state')
        if payload.state in ('active','maintenance') and (not identity.coordinates_verified or station.latitude is None or station.longitude is None):
            raise HTTPException(422,'Verified commissioning coordinates are required')
        before=station.status
        station.status=payload.state
        touch_lifecycle(db,station,admin,payload.reason,invalidate_delivery=True)
        audit(db,station,admin,'station_lifecycle_changed',payload.reason,{'before':before,'after':payload.state,'incidents':'retained; no automatic administrative resolution'})
    commit_security(db)
    return operations_contract(db,station)


@router.get("/{station_id}/configuration")
def get_configuration(station_id:str,db:Session=Depends(get_db),_admin:User=Depends(require_admin)):
    row=current_configuration(db,station_id)
    if row is None:
        raise HTTPException(404,"Station installation configuration has not been reviewed")
    return configuration_contract(row)


@router.post("/{station_id}/configuration",status_code=201)
def configure_station(station_id:str,payload:ConfigurationRequest,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    station=lock_station(db,station_id)
    row=save_configuration(db,station,payload,admin)
    commit_security(db)
    return configuration_contract(row)


def commissioning_contract(db, identity):
    result = CommissionRead.model_validate(identity)
    registry = db.get(StationSourceRegistry, (identity.station_id, identity.version))
    if registry:
        result = result.model_copy(update={"source_class": registry.source_class, "stream": registry.stream,
                                           "provenance_evidence": registry.evidence})
    return result


@router.get("", response_model=list[StationRead])
def list_stations(db: Session = Depends(get_db)) -> list[Station]:
    return list(db.scalars(select(Station).order_by(Station.station_id)))


@router.get("/{station_id}", response_model=StationRead)
def get_station(station_id: str, db: Session = Depends(get_db)) -> Station:
    station = db.scalar(select(Station).where(Station.station_id == station_id))
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    return station


@router.post("", response_model=StationRead, status_code=status.HTTP_201_CREATED)
def create_station(
    payload: StationProvisionRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> Station:
    existing = db.scalar(
        select(Station).where(Station.station_id == payload.station_id)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Station already exists")

    station = Station(**payload.model_dump(exclude={"commissioning"}), status="inactive")
    db.add(station)
    try:
        db.flush()
        commission(db, station, payload.commissioning, admin, expected_version=0, action="station_provisioned")
        commit_security(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Station or device binding already exists. Refresh before retrying.") from None
    except Exception:
        db.rollback()
        raise
    db.refresh(station)
    return station


@router.get("/{station_id}/provisioning", response_model=CommissionRead)
def read_provisioning(station_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    identity = db.get(StationIdentity, station_id)
    if identity is None:
        raise HTTPException(404, "Station has no commissioning record. Existing data is preserved.")
    return commissioning_contract(db, identity)


@router.post("/{station_id}/commission", response_model=CommissionRead)
def commission_station(station_id: str, payload: CommissionRequest, db: Session = Depends(get_db),
                       admin: User = Depends(require_admin)):
    station = lock_station(db, station_id)
    identity = commission(db, station, payload, admin, expected_version=payload.expected_version,
                          coordinates=payload.model_dump(include={"latitude", "longitude"}, exclude_unset=True))
    commit_security(db)
    db.refresh(identity)
    return commissioning_contract(db, identity)


@router.post("/{station_id}/credentials", response_model=CredentialIssued, status_code=201)
def create_credential(station_id: str, payload: CredentialRequest, db: Session = Depends(get_db),
                      admin: User = Depends(require_admin)):
    station = lock_station(db, station_id)
    credential, token = issue_credential(db, station, payload, admin)
    commit_security(db)
    db.refresh(credential)
    return CredentialIssued(**CredentialRead.model_validate(credential).model_dump(), ingest_token=token)


@router.get("/{station_id}/credentials", response_model=list[CredentialRead])
def list_credentials(station_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return list(db.scalars(select(StationCredential).where(StationCredential.station_id == station_id)
                           .order_by(StationCredential.created_at.desc()).limit(100)))


@router.post("/{station_id}/credentials/{credential_id}/revoke", response_model=CredentialRead)
def revoke_credential(station_id: str, credential_id: UUID, payload: RevokeRequest,
                      db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    station = lock_station(db, station_id)
    credential = db.get(StationCredential, str(credential_id), populate_existing=True)
    if credential is None or credential.station_id != station_id:
        raise HTTPException(404, "Station credential not found")
    if credential.revoked_at is None:
        credential.revoked_at = utc_now()
        audit(db, station, admin, "credential_revoked", payload.reason, {"credential_id": credential.id})
        commit_security(db)
        db.refresh(credential)
    return credential


@router.get("/{station_id}/audit", response_model=list[StationAuditRead])
def station_audit(station_id: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return list(db.scalars(select(StationAuditEvent).where(StationAuditEvent.station_id == station_id)
                           .order_by(StationAuditEvent.id.desc()).offset(offset).limit(limit)))
