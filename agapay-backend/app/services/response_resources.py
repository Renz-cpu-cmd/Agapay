from datetime import datetime, timedelta
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update
from app.models import utc_now
from app.governance_models import AlertAuthority, AuthorityGrant, VerifiedArea
from app.resource_models import ResponseResource, ResourceRevision
from app.services.alert_governance import authorized, verified_areas
from app.services.station_security import utc
from app.services.mutation_audit import record


def read(db,row):
    now=utc_now()
    authority=db.get(AlertAuthority,row.authority_id)
    areas=[db.get(VerifiedArea,i) for i in row.area_ids]
    trust=bool(authority and authority.active and all(a and a.active for a in areas)
               and (row.mode!='Actual' or authority.authority_class=='public_authority' and all(a.area_class=='geographic' for a in areas)))
    verification='authority_unavailable' if not trust else 'expired' if row.verification=='verified' and (not row.expires_at or utc(row.expires_at)<=now) else row.verification
    data=row.data
    available=verification=='verified' and row.mode=='Actual'
    capacity_current=False
    effective_state=data.get('state','reference')
    if row.kind=='shelter':
        capacity_at=data.get('capacity_observed_at')
        capacity_current=bool(capacity_at and timedelta(0)<=now-datetime.fromisoformat(capacity_at.replace('Z','+00:00'))<=timedelta(minutes=30))
        if data.get('capacity') is not None and data.get('occupancy') is not None and data['occupancy']>=data['capacity']:
            effective_state='full'
        available=available and effective_state=='active'
    return dict(id=row.id,kind=row.kind,version=row.version,authority_id=row.authority_id,
        issuer_name=authority.name if authority else 'Issuer unavailable',area_ids=row.area_ids,
        area_names=[a.name if a else i for a,i in zip(areas,row.area_ids)],mode=row.mode,data=data,
        source=row.source,verification=verification,published=row.published,
        verified_at=utc(row.verified_at) if row.verified_at else None,
        expires_at=utc(row.expires_at) if row.expires_at else None,updated_at=utc(row.updated_at),
        effective_state=effective_state,capacity_current=capacity_current,route_candidate=available if row.kind=='shelter' else False,
        route_safety='not_established')


def permission(db,actor,authority_id,area_ids,mode):
    authority=authorized(db,actor,authority_id,area_ids)
    areas=verified_areas(db,area_ids)
    if mode=='Actual' and (authority.authority_class!='public_authority' or any(a.area_class!='geographic' for a in areas)):
        raise HTTPException(403,'Actual response resources require a public authority and verified geographic areas; use Exercise for prototype records')


def stale(db,row):
    db.rollback();db.refresh(row)
    raise HTTPException(409,dict(code='refresh_required',message='Resource changed. Refresh and manually review.',current=jsonable_encoder(read(db,row))))


def history(db,row,actor,action,reason):
    snapshot=read(db,row)
    # Serialize timestamps through the JSON contract, never credentials.
    from fastapi.encoders import jsonable_encoder
    db.add(ResourceRevision(resource_id=row.id,version=row.version,actor_id=actor.id,action=action,
                            reason=reason,snapshot=jsonable_encoder(snapshot)))
    record(db,actor,'response_resource',row.id,'resource_'+action,reason,
           after={'version':row.version,'state':row.verification,'name':row.data['name'],'authority_id':row.authority_id})


def write(db,actor,payload):
    row=db.get(ResponseResource,payload.id,populate_existing=True)
    # Existing authority/area ownership cannot be bypassed by posting a replacement issuer.
    if row:
        permission(db,actor,row.authority_id,row.area_ids,row.mode)
        if (payload.kind,payload.authority_id,payload.mode)!=(row.kind,row.authority_id,row.mode):
            raise HTTPException(422,'Resource kind, issuer and exercise/actual namespace are immutable')
    permission(db,actor,payload.authority_id,payload.area_ids,payload.mode)
    if payload.expected_version!=(row.version if row else 0):
        if row:stale(db,row)
        raise HTTPException(409,'Resource does not exist. Refresh and review.')
    fields=dict(area_ids=payload.area_ids,data=payload.data,source=payload.source,verification='unverified',
                verified_at=None,expires_at=None,updated_at=utc_now())
    if row:
        result=db.execute(update(ResponseResource).where(ResponseResource.id==row.id,
            ResponseResource.version==payload.expected_version).values(**fields,version=ResponseResource.version+1).execution_options(synchronize_session=False))
        if result.rowcount!=1:stale(db,row)
        db.refresh(row)
    else:
        row=ResponseResource(id=payload.id,kind=payload.kind,authority_id=payload.authority_id,
                             mode=payload.mode,version=1,**fields)
        db.add(row);db.flush()
    history(db,row,actor,'edited',payload.reason)
    db.commit()
    return read(db,row)


def review(db,row,actor,payload):
    permission(db,actor,row.authority_id,row.area_ids,row.mode)
    if payload.expected_version!=row.version:stale(db,row)
    now=utc_now()
    if payload.action=='verify':
        if not payload.expires_at or not now+timedelta(minutes=1)<=payload.expires_at<=now+timedelta(days=7):
            raise HTTPException(422,'Verification expiry must be 1 minute to 7 days in the future')
        if row.kind=='shelter':
            for name in ('activated_at','capacity_observed_at'):
                value=row.data.get(name)
                if value and datetime.fromisoformat(value.replace('Z','+00:00'))>now+timedelta(minutes=1):
                    raise HTTPException(422,'Activation/capacity cannot claim a future observation')
        fields=dict(verification='verified',published=True,verified_at=now,expires_at=payload.expires_at)
    else:fields=dict(verification='withdrawn',expires_at=now)
    result=db.execute(update(ResponseResource).where(ResponseResource.id==row.id,ResponseResource.version==payload.expected_version)
        .values(**fields,version=ResponseResource.version+1,updated_at=now).execution_options(synchronize_session=False))
    if result.rowcount!=1:stale(db,row)
    db.refresh(row);history(db,row,actor,payload.action,payload.reason);db.commit()
    return read(db,row)
