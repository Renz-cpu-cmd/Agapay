import hmac
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.config import get_settings,Settings
from app.database import get_db
from app.models import User
from app.services.accounts import current_user
from app.services.operations_health import diagnostics,public_summary
from datetime import timedelta
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime
from app.models import utc_now

router=APIRouter(prefix='/api/operations',tags=['operational health'])


@router.get('/status')
def status(db:Session=Depends(get_db),settings:Settings=Depends(get_settings),user:User=Depends(current_user)):
    return public_summary(diagnostics(db,settings))


@router.get('/diagnostics')
def dependency_diagnostics(db:Session=Depends(get_db),settings:Settings=Depends(get_settings),user:User=Depends(current_user)):
    if user.role not in ('admin','officer'):raise HTTPException(403,'Staff diagnostics access required')
    return diagnostics(db,settings)


class RecoveryReview(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    checked_at:AwareDatetime
    code:str=Field(pattern='^[A-Z][A-Z0-9_]{2,79}$')
    activity:Literal['investigated','handoff_recorded','completed_recovery_review']
    reason:str=Field(min_length=8,max_length=500)
    evidence_sha256:str=Field(pattern='^[a-f0-9]{64}$')


class RecoveryReviewReceipt(BaseModel):
    id:int
    recorded_at:AwareDatetime
    recorded:Literal[True]=True
    notice:str


@router.post('/recovery-reviews',status_code=201,response_model=RecoveryReviewReceipt)
def recovery_review(payload:RecoveryReview,db:Session=Depends(get_db),user:User=Depends(current_user)):
    from app.services.accounts import lock_account
    lock_account(db,user.id);db.refresh(user)
    if user.role!='admin' or not user.is_active:raise HTTPException(403,'Administrator recovery review required')
    now=utc_now()
    if not now-timedelta(hours=24)<=payload.checked_at<=now:
        raise HTTPException(409,'Diagnostic review time is future or older than one day. Refresh and manually review.')
    from app.identity_models import MutationAudit
    from app.services.mutation_audit import redact
    row=MutationAudit(actor_id=user.id,actor_label=user.name,subject_type='operations_review',subject_id=payload.code,
        action='operations_recovery_reviewed',reason=payload.reason,before={},
        after=redact({'diagnostic_checked_at':payload.checked_at.isoformat(),'operator_fault_code':payload.code,
            'recovery_activity':payload.activity,'evidence_sha256':payload.evidence_sha256,'attestation_kind':'operator_attestation'}))
    db.add(row);db.commit();db.refresh(row)
    from app.services.station_security import utc
    return dict(id=row.id,recorded_at=utc(row.created_at),recorded=True,
        notice='Operator review recorded only. Dependency readiness, delivery state and restore quarantine are unchanged; nothing was resent.')


@router.get('/metrics',response_class=PlainTextResponse)
def prometheus(request:Request,db:Session=Depends(get_db),settings:Settings=Depends(get_settings)):
    token=settings.observability_scrape_token.get_secret_value()
    if len(token)<32:raise HTTPException(503,'Operational metrics scraper is not configured')
    authorization=request.headers.get('Authorization','')
    if not hmac.compare_digest(authorization.encode(),('Bearer '+token).encode()):raise HTTPException(401,'Metrics scrape authorization required')
    report=diagnostics(db,settings)
    lines=['# HELP agapay_workflow_ready Configured dependency readiness.','# TYPE agapay_workflow_ready gauge']
    for item in report['components']:lines.append(f'agapay_workflow_ready{{component="{item["name"]}"}} {int(item["state"]=="healthy")}')
    for alert in report['alerts']:lines.append(f'agapay_operator_fault{{code="{alert["code"]}"}} 1')
    for metric,value in report['metrics'].items():
        safe=metric.replace('.','_')
        lines.extend([f'agapay_window_events{{workflow="{safe}"}} {value["count"]}',f'agapay_window_errors{{workflow="{safe}"}} {value["failures"]}',
                      f'agapay_window_latency_max_seconds{{workflow="{safe}"}} {value["maximum_seconds"]}'])
        for name in ('p95','p99'):
            bound=value.get(name+'_seconds_upper_bound')
            if bound is not None:lines.append(f'agapay_window_latency_{name}_seconds_upper_bound{{workflow="{safe}"}} {bound}')
    return PlainTextResponse('\n'.join(lines)+'\n',media_type='text/plain; version=0.0.4',headers={'Cache-Control':'no-store'})
