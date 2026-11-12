from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SosRequest, User
from app.sos_response_models import SosDrillIncident
from app.sos_response_schemas import DrillPolicyWrite, StartDrill, ResponseAction, IncidentCreate
from app.services.accounts import current_user, require_admin, bearer, lock_account
from app.services import sos_response as service
from app.routers.sos import visible
from app.services.mutation_audit import record

router = APIRouter(prefix='/api/sos-response', tags=['SOS response drills'])


def staff(user=Depends(current_user)):
    if user.role not in ('admin', 'officer'): raise HTTPException(403, 'Staff access required')
    return user


def locked_staff(user=Depends(staff), credentials: HTTPAuthorizationCredentials=Depends(bearer), db: Session=Depends(get_db)):
    lock_account(db, user.id)
    user = current_user(credentials, db)
    if user.role not in ('admin', 'officer'): raise HTTPException(403, 'Staff access required')
    return user


@router.get('/policy')
def policy(user=Depends(staff), db: Session=Depends(get_db)):
    return service.policy_read(db)


@router.patch('/policy')
def save_policy(payload: DrillPolicyWrite, user=Depends(locked_staff), db: Session=Depends(get_db)):
    if user.role != 'admin': raise HTTPException(403, 'Administrator policy review required')
    try: return service.save_policy(db, user, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, {'code': 'refresh_required', 'message': 'Another administrator configured the policy. Refresh and review.'}) from None


@router.get('/staff')
def staff_directory(user=Depends(staff), db: Session=Depends(get_db)):
    return [dict(id=u.id, name=u.name, role=u.role) for u in db.scalars(select(User).where(
        User.is_active.is_(True), User.role.in_(('admin', 'officer'))).order_by(User.id).limit(200))]


@router.get('/incidents')
def incidents(user=Depends(staff), limit: int=Query(50, ge=1, le=100), offset: int=Query(0, ge=0), db: Session=Depends(get_db)):
    return [dict(id=i.id, label=i.label, mode='drill') for i in db.scalars(select(SosDrillIncident).order_by(SosDrillIncident.id.desc()).offset(offset).limit(limit))]


@router.post('/incidents', status_code=201)
def create_incident(payload: IncidentCreate, user=Depends(locked_staff), db: Session=Depends(get_db)):
    item = SosDrillIncident(label=payload.label, correlation_reason=payload.reason, created_by=user.id)
    db.add(item); db.flush()
    record(db, user, 'sos_incident', item.id, 'drill_incident_created', payload.reason, after={'name': item.label, 'state': 'drill'})
    db.commit()
    return dict(id=item.id, label=item.label, mode='drill')


@router.get('/{sos_id}')
def response(sos_id: int, before_event_id: int | None=Query(None, ge=1), user=Depends(current_user), db: Session=Depends(get_db)):
    return service.read(db, visible(db, user, sos_id), user, before_event_id=before_event_id)


@router.post('/{sos_id}/start')
def start(sos_id: int, payload: StartDrill, user=Depends(locked_staff), db: Session=Depends(get_db)):
    item = visible(db, user, sos_id)
    result = service.start(db, item, user, payload)
    return result


@router.post('/{sos_id}/actions')
def action(sos_id: int, payload: ResponseAction, user=Depends(locked_staff), db: Session=Depends(get_db)):
    return service.act(db, visible(db, user, sos_id), user, payload)
