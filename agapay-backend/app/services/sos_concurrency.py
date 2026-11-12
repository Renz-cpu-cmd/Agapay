"""One optimistic version covers location, response actions and request lifecycle."""
from fastapi import HTTPException
from sqlalchemy import update
from app.models import SosRequest
from app.sos_schemas import SosRead


def conflict(db, item, message='SOS changed. Refresh and manually review before submitting again.'):
    db.rollback()
    db.refresh(item)
    raise HTTPException(409, {'code': 'refresh_required', 'message': message,
                             'current': SosRead.model_validate(item).model_dump(mode='json')})


def claim(db, item, expected_version, *, conditions=(), fields=None):
    """CAS is the serialization point, with no stale ORM mutation before it."""
    result = db.execute(update(SosRequest).where(
        SosRequest.id == item.id, SosRequest.version == expected_version, *conditions
    ).values(**(fields or {}), version=SosRequest.version + 1)
      .execution_options(synchronize_session=False))
    if result.rowcount != 1:
        conflict(db, item)
    db.refresh(item)
    return item
