"""Administrator inspection and reconciliation of recovery-held deliveries (R2 P0).

Declaring recovery, releasing restored data and activating a generation are offline,
worker-host operations (python -m app.delivery_recovery) because activation anchors the
external ledger. This API never re-queues or resends a held delivery.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services import delivery_recovery as recovery
from app.services.accounts import current_user

router = APIRouter(prefix='/api/delivery-recovery', tags=['delivery recovery'])


class HoldDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['provider_accepted', 'not_delivered', 'outcome_unknown', 'superseded']
    evidence_kind: Literal['provider_record', 'no_provider_record', 'operator_review']
    evidence_sha256: str = Field(pattern='^[0-9a-f]{64}$')
    reason: str = Field(min_length=10, max_length=500)
    expected_version: int = Field(ge=1)


def admin(user: User = Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Administrator delivery recovery access required')
    return user


@router.get('')
def status(db: Session = Depends(get_db), user: User = Depends(admin)):
    return recovery.status(db)


@router.get('/holds')
def holds(undecided: bool = False, before_id: int | None = Query(None, gt=0), limit: int = Query(50, ge=1, le=100),
          db: Session = Depends(get_db), user: User = Depends(admin)):
    items = recovery.list_holds(db, undecided_only=undecided, before_id=before_id, limit=limit)
    return dict(items=items, next_before_id=items[-1]['id'] if len(items) == limit else None,
                notice='Held deliveries are never resent. A decision records evidence and closes the hold.')


@router.post('/holds/{hold_id}/decision')
def decide(hold_id: int, payload: HoldDecision, db: Session = Depends(get_db), user: User = Depends(admin)):
    try:
        hold = recovery.decide(db, hold_id, actor_id=user.id, **payload.model_dump())
    except recovery.RecoveryRefused as error:
        db.rollback()
        raise HTTPException(404 if 'not found' in str(error) else 409, str(error)) from None
    db.commit()
    return recovery.hold_view(hold)
