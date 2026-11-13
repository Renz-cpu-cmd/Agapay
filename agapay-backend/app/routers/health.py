from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return {"status": "ok", "database": "connected"}


@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    from app.migrations import require_current,REVISIONS
    from app.config import get_settings
    from app.services.operations_health import diagnostics
    try:
        require_current(db.get_bind())
        report=diagnostics(db,get_settings())
    except Exception:
        raise HTTPException(503, "Database unavailable or migration mismatch") from None
    from fastapi.responses import JSONResponse
    return JSONResponse(dict(status='ready' if report['ready'] else 'degraded',schema=REVISIONS[-1],
        degraded=[c['code'] for c in report['components'] if c['required'] and c['state']!='healthy']),status_code=200 if report['ready'] else 503)


@router.get('/live')
def liveness():
    return {'status':'alive'}
