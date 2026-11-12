from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from fastapi import APIRouter,Depends,HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User,NotificationDevice,utc_now
from app.governance_models import VerifiedArea
from app.operations_models import AccountPreference
from app.services.accounts import current_user,lock_account,bearer

router=APIRouter(prefix='/api/auth/preferences',tags=['product preferences'])


class PreferenceWrite(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=0)
    notifications_enabled:bool|None=None
    locale:Literal['en']='en'
    resident_area_id:str|None=Field(default=None,min_length=1,max_length=50)
    requested_language:str|None=Field(default=None,min_length=1,max_length=80)

    @model_validator(mode='after')
    def nonnull_preference(self):
        if 'notifications_enabled' in self.model_fields_set and self.notifications_enabled is None:
            raise ValueError('Delivery preference cannot be null')
        if self.requested_language is not None and not self.requested_language.strip():
            raise ValueError('Language request cannot be blank')
        return self


def preference_contract(db,user):
    row=db.get(AccountPreference,user.id)
    area=db.get(VerifiedArea,row.resident_area_id) if row and row.resident_area_id else None
    return dict(revision=row.revision if row else 0,notifications_enabled=row.notifications_enabled if row else True,
        locale='en',supported_locales=['en'],translation_status='Filipino and other translations unavailable; operational content remains English',
        resident_area_id=row.resident_area_id if row else None,resident_area_name=area.name if area else None,
        resident_area_active=area.active if area else False,requested_language=row.requested_language if row else None,
        delivery_policy='Off disables all AGAPAY sensor push, including critical and citywide; no silent override. In-app notices remain visible. Sends already in flight may arrive.',
        geography_policy='Resident area is profile context, not exposure or a notification subscription')


@router.get('')
def read_preferences(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return preference_contract(db,user)


@router.get('/areas')
def areas(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [dict(id=a.id,name=a.name,identifier_scheme=a.identifier_scheme) for a in db.scalars(
        select(VerifiedArea).where(VerifiedArea.active.is_(True),VerifiedArea.area_class=='geographic').order_by(VerifiedArea.id).limit(500))]


@router.patch('')
def update_preferences(payload:PreferenceWrite,db:Session=Depends(get_db),user:User=Depends(current_user),
                       credentials:HTTPAuthorizationCredentials=Depends(bearer)):
    lock_account(db,user.id)
    current_user(credentials,db)
    row=db.get(AccountPreference,user.id,populate_existing=True)
    revision=row.revision if row else 0
    if payload.expected_revision!=revision:
        raise HTTPException(409,'Preferences changed; refresh and manually review before saving again')
    if payload.resident_area_id:
        area=db.get(VerifiedArea,payload.resident_area_id)
        if not area or not area.active or area.area_class!='geographic':
            raise HTTPException(422,'Choose an active verified geographic identifier; free-text locality is not a verified area')
    if row is None:
        row=AccountPreference(user_id=user.id,revision=0,notifications_enabled=True,locale='en')
        db.add(row)
    from app.services.mutation_audit import record
    before={key:getattr(row,key) for key in ("revision","notifications_enabled","resident_area_id","requested_language")}
    for key in ('notifications_enabled','resident_area_id','requested_language'):
        if key in payload.model_fields_set:
            value=getattr(payload,key)
            setattr(row,key,value.strip() if isinstance(value,str) else value)
    row.revision=revision+1;row.updated_at=utc_now()
    if not row.notifications_enabled:
        from app.services.notification_service import disable_device
        for device in db.scalars(select(NotificationDevice).where(NotificationDevice.user_id==user.id,NotificationDevice.enabled.is_(True))):
            disable_device(device)
    record(db,user,"account_preferences",user.id,"preferences_updated","Account owner preference change",before,{key:getattr(row,key) for key in before})
    db.commit()
    return preference_contract(db,user)
