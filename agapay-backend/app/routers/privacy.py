from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, SecretStr, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.privacy_models import PrivacyCase, PrivacyEvent, PrivacyHold
from app.privacy_schemas import StepUp, CaseCreate, CaseDecision, HoldChange
from app.services.accounts import current_user, require_admin, lock_account, bearer
from fastapi.security import HTTPAuthorizationCredentials
from app.services.auth_abuse import limiter
from app.services import privacy as service
from app.services.privacy_governance import POLICY, deployment_status

router = APIRouter(prefix='/api/privacy', tags=['privacy and data rights'])


def reauthorize(db, actor, credentials, subject=None):
    for identity in sorted({actor.id, subject or actor.id}): lock_account(db, identity)
    actor = current_user(credentials, db)
    if actor.role != 'admin': raise HTTPException(403, 'Administrator access required')
    return actor



@router.get('/notice')
def notice():
    deployment = deployment_status(get_settings())
    return {'deployment': deployment, 'policy': dict(POLICY, approval='organization-attested' if deployment['status']=='organization_attested' else POLICY['approval']),
        'data': ['account/contact/profile', 'SOS narrative and latest location', 'session/push authorization',
                 'area subscriptions/preferences', 'audit and delivery evidence'],
        'recipients': ['authorized AGAPAY staff for recorded duties', 'configured hosting/database/backup operators',
                      'configured SMTP and Firebase/APNs delivery providers', 'Google Maps when a map/route is explicitly used'],
        'rights': 'Sign in to request access, correction or erasure. Requests require review; unresolved incidents and justified holds may defer erasure.',
        'limits': 'Organizational attestation recorded; verify the stated scope and contact. This notice is not legal certification.' if deployment['status']=='organization_attested' else 'Development policy is unapproved. No operational response SLA or legal compliance is represented by this notice.'}


@router.get('/cases')
def own_cases(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [service.view(row) for row in db.scalars(select(PrivacyCase).where(PrivacyCase.user_id == user.id)
            .order_by(PrivacyCase.created_at.desc()).limit(100))]


@router.post('/cases', status_code=202)
def request_case(payload: CaseCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.hit('privacy-case:' + str(user.id), 6, 3600)
    service.step_up(db, user, payload.current_password.get_secret_value())
    return service.create_case(db, user, payload.kind)


@router.post('/export')
def export(payload: StepUp, after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.hit('privacy-export:' + str(user.id), 10, 3600)
    service.step_up(db, user, payload.current_password.get_secret_value())
    return service.export_page(db, user, after=after, limit=limit)


@router.get('/admin/cases')
def admin_cases(after: str | None = None, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    query = select(PrivacyCase).order_by(PrivacyCase.id).limit(50)
    if after: query = query.where(PrivacyCase.id > after)
    rows = db.scalars(query).all()
    service.evidence(db, admin, 'privacy-cases', 'administrative_read', returned=len(rows)); db.commit()
    return [dict(service.view(row), user_id=row.user_id, account_version=db.get(User, row.user_id).version) for row in rows]


@router.patch('/admin/cases/{identity}')
def decide(identity: str, payload: CaseDecision, admin: User = Depends(require_admin), db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    case = service.case_for(db, admin, identity, admin=True)
    admin = reauthorize(db, admin, credentials, case.user_id)
    return service.decide(db, admin, service.case_for(db, admin, identity, admin=True), payload)


class ErasureApply(StepUp):
    expected_version: int = Field(ge=1)
    expected_account_version: int = Field(ge=1)


@router.post('/admin/cases/{identity}/application-erasure')
def erase(identity: str, payload: ErasureApply, admin: User = Depends(require_admin), db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    limiter.hit('privacy-erasure:'+str(admin.id), 5, 3600)
    case = service.case_for(db, admin, identity, admin=True)
    admin = reauthorize(db, admin, credentials, case.user_id)
    service.step_up(db, admin, payload.current_password.get_secret_value())
    return service.erase_resident(db, admin, service.case_for(db, admin, identity, admin=True),
                                 payload.expected_version, payload.expected_account_version)


@router.get('/admin/holds/{user_id}')
def get_hold(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(PrivacyHold, user_id)
    return {'version': row.version if row else 0, 'active': bool(row and row.active),
            'expires_at': row.expires_at if row else None, 'reason_code': row.reason_code if row else None}


@router.patch('/admin/holds/{user_id}')
def hold(user_id: int, payload: HoldChange, admin: User = Depends(require_admin), db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    admin = reauthorize(db, admin, credentials, user_id)
    return service.change_hold(db, admin, user_id, payload)


@router.get('/admin/evidence')
def evidence(after: int = Query(0, ge=0), admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(PrivacyEvent).where(PrivacyEvent.id > after).order_by(PrivacyEvent.id).limit(100)).all()
    return [dict(id=row.id, actor_id=row.actor_id, subject_id=row.subject_id, action=row.action,
                 details=row.details, created_at=row.created_at) for row in rows]


@router.get('/admin/access-review')
def access_inventory(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.access_review(db)


class AccessReview(StepUp):
    snapshot_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    evidence_sha256: str = Field(pattern='^[a-f0-9]{64}$')


@router.post('/admin/access-review')
def record_access_review(payload: AccessReview, admin: User = Depends(require_admin), db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    admin = reauthorize(db, admin, credentials)
    service.step_up(db, admin, payload.current_password.get_secret_value())
    inventory = service.access_review(db)
    if inventory['sha256'] != payload.snapshot_sha256:
        raise HTTPException(409, 'Access changed; refresh and manually review the inventory')
    service.evidence(db, admin, inventory['sha256'], 'access_reviewed', evidence_sha256=payload.evidence_sha256)
    db.commit()
    return {'status':'recorded','snapshot_sha256':inventory['sha256']}
