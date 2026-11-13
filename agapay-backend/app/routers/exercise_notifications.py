"""Administrator-controlled EXERCISE_TEST notifications (Stage A). Never operational."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.exercise_models import ExerciseSession
from app.models import User
from app.services import exercise_notifications as service
from app.services.accounts import current_user, require_admin

router = APIRouter(prefix="/api/exercise-notifications", tags=["exercise notifications"])


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=10, max_length=500)
    duration_minutes: int = Field(ge=1, le=240)
    max_sends: int = Field(default=5, ge=1, le=50)


class RecipientChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(min_length=36, max_length=36)
    reason: str = Field(min_length=3, max_length=500)


class Termination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=500)


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(min_length=36, max_length=36)
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    reason: str = Field(min_length=3, max_length=500)
    dry_run: bool = False


def _session(db, session_id):
    session = db.get(ExerciseSession, session_id)
    if session is None:
        raise HTTPException(404, "Exercise session not found")
    return session


@router.get("/consent/{device_id}")
def read_consent(device_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return service.consent_state(db, user, device_id)


@router.put("/consent/{device_id}")
def opt_in(device_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """The device owner opts this registration in to EXERCISE_TEST messages."""
    return service.set_consent(db, user, device_id, True)


@router.delete("/consent/{device_id}")
def opt_out(device_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return service.set_consent(db, user, device_id, False)


@router.post("/sessions", status_code=201)
def create_session(payload: SessionCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    session = service.create_session(db, admin, payload.reason, payload.duration_minutes, payload.max_sends)
    return service.session_contract(db, session)


@router.get("/sessions/{session_id}")
def read_session(session_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    service.require_available()
    return service.session_contract(db, _session(db, session_id))


@router.post("/sessions/{session_id}/recipients")
def allowlist(session_id: str, payload: RecipientChange, db: Session = Depends(get_db),
              admin: User = Depends(require_admin)):
    service.allowlist_device(db, admin, session_id, payload.device_id, payload.reason)
    return service.session_contract(db, _session(db, session_id))


@router.post("/sessions/{session_id}/recipients/revoke")
def revoke(session_id: str, payload: RecipientChange, db: Session = Depends(get_db),
           admin: User = Depends(require_admin)):
    service.revoke_device(db, admin, session_id, payload.device_id, payload.reason)
    return service.session_contract(db, _session(db, session_id))


@router.post("/sessions/{session_id}/terminate")
def terminate(session_id: str, payload: Termination, db: Session = Depends(get_db),
              admin: User = Depends(require_admin)):
    service.terminate_session(db, admin, session_id, payload.reason)
    return service.session_contract(db, _session(db, session_id))


class StationArm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str = Field(min_length=1, max_length=50)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/sessions/{session_id}/stations")
def arm(session_id: str, payload: StationArm, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Stage B: arm one physical station; its later upward tier changes create EXERCISE_TEST messages."""
    service.arm_station(db, admin, session_id, payload.station_id, payload.reason)
    return service.session_contract(db, _session(db, session_id))


@router.post("/sessions/{session_id}/stations/disarm")
def disarm(session_id: str, payload: StationArm, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    service.disarm_station(db, admin, session_id, payload.station_id, payload.reason)
    return service.session_contract(db, _session(db, session_id))


@router.post("/sessions/{session_id}/send")
def send(session_id: str, payload: SendRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    delivery, replayed = service.request_send(db, admin, session_id, payload.device_id, payload.idempotency_key,
                                              payload.reason, payload.dry_run)
    if delivery is None:
        return {"dry_run": True, "eligible": True, "message_type": service.EXERCISE_TYPE,
                "title": service.EXERCISE_TITLE, "body": service.EXERCISE_BODY}
    return {"dry_run": False, "replayed": replayed, "delivery": service.delivery_contract(delivery)}
