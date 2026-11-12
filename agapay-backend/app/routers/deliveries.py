from fastapi import APIRouter,Depends,HTTPException,Query,Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.accounts import current_user
from app.delivery_schemas import ReceiptCreate,ConsentUpdate,DeliveryAcknowledge,DeliveryReconcile
from app.services import delivery_evidence as evidence

router=APIRouter(tags=['notification delivery evidence'])


@router.post('/api/notification-receipts')
def receipt(payload:ReceiptCreate,request:Request,db:Session=Depends(get_db)):
    from app.services.auth_abuse import limiter,request_ip
    limiter.hit('notification-receipt:'+request_ip(request),1200,60)
    return evidence.capture_receipt(db,payload)


def resident(user:User=Depends(current_user)):
    if user.role!='resident':raise HTTPException(403,'Resident delivery preference required')
    return user


@router.get('/api/notification-deliveries/consent')
def consent(db:Session=Depends(get_db),user:User=Depends(resident)):
    return evidence.consent_read(db,user)


@router.post('/api/notification-deliveries/consent')
def update_consent(payload:ConsentUpdate,db:Session=Depends(get_db),user:User=Depends(resident)):
    return evidence.update_consent(db,user,payload)


@router.get('/api/notification-deliveries')
def deliveries(before_id:int|None=Query(None,gt=0),limit:int=Query(30,ge=1,le=50),
    state:str|None=Query(None,pattern='^(PENDING|PROCESSING|SENT|FAILED|SUPPRESSED|TESTED|UNKNOWN)$'),
    db:Session=Depends(get_db),user:User=Depends(current_user)):
    return evidence.read_rows(db,user,before_id=before_id,limit=limit,state=state)


@router.get('/api/notification-deliveries/{identity}')
def delivery(identity:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    return evidence.detail(db,user,identity)


@router.post('/api/notification-deliveries/{identity}/acknowledge')
def acknowledge(identity:int,payload:DeliveryAcknowledge,db:Session=Depends(get_db),user:User=Depends(resident)):
    return evidence.acknowledge(db,user,identity,payload)


@router.post('/api/notification-deliveries/{identity}/reconcile')
def reconcile(identity:int,payload:DeliveryReconcile,db:Session=Depends(get_db),user:User=Depends(current_user)):
    return evidence.reconcile(db,user,identity,payload)
