from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, exists, cast
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import utc_now
from app.governance_models import AlertAuthority, AuthorityGrant, VerifiedArea
from app.resource_models import ResponseResource, ResourceRevision
from app.resource_schemas import ResourceWrite, ResourceReview
from app.services.accounts import current_user
from app.routers.sos_response import locked_staff
from app.services import response_resources as service

router=APIRouter(prefix='/api/response-resources',tags=['verified response resources'])


@router.get('/maintenance-context')
def context(user=Depends(locked_staff),db:Session=Depends(get_db)):
    grants=list(db.scalars(select(AuthorityGrant).where(AuthorityGrant.user_id==user.id,AuthorityGrant.active.is_(True)).limit(100)))
    return dict(authorities=[dict(id=g.authority_id,name=a.name,authority_class=a.authority_class,area_ids=g.area_ids)
        for g in grants if (a:=db.get(AlertAuthority,g.authority_id)) and a.active],
        areas=[dict(id=a.id,name=a.name,area_class=a.area_class) for a in db.scalars(select(VerifiedArea).where(VerifiedArea.active.is_(True)).limit(200))])


@router.get('')
def listing(kind:str=Query('shelter',pattern='^(shelter|road|preparedness)$'),mode:str=Query('Actual',pattern='^(Actual|Exercise)$'),
            area_id:str|None=None,include_drafts:bool=False,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),
            user=Depends(current_user),db:Session=Depends(get_db)):
    if (include_drafts or mode=='Exercise') and user.role not in ('admin','officer'):
        raise HTTPException(403,'Draft/exercise inventory is staff-only')
    conditions=[ResponseResource.kind==kind,ResponseResource.mode==mode]
    if not include_drafts:conditions.append(ResponseResource.published.is_(True))
    if area_id is not None:
        if db.bind.dialect.name=='sqlite':
            values=func.json_each(ResponseResource.area_ids).table_valued('value')
            conditions.append(exists(select(1).select_from(values).where(values.c.value==area_id)))
        else:
            from sqlalchemy.dialects.postgresql import JSONB
            conditions.append(cast(ResponseResource.area_ids,JSONB).contains([area_id]))
    total=db.scalar(select(func.count()).select_from(ResponseResource).where(*conditions))
    rows=db.scalars(select(ResponseResource).where(*conditions).order_by(ResponseResource.id).offset(offset).limit(limit))
    return dict(items=[service.read(db,r) for r in rows],total=total,
        generated_at=utc_now(),has_more=offset+limit<total,road_coverage='partial_source_inventory_not_proof_of_open_roads')


@router.post('')
def write(payload:ResourceWrite,user=Depends(locked_staff),db:Session=Depends(get_db)):
    try:return service.write(db,user,payload)
    except IntegrityError:
        db.rollback();raise HTTPException(409,dict(code='refresh_required',message='Resource was created concurrently. Refresh and review.')) from None


@router.post('/{resource_id}/review')
def review(resource_id:str,payload:ResourceReview,user=Depends(locked_staff),db:Session=Depends(get_db)):
    row=db.get(ResponseResource,resource_id)
    if not row:raise HTTPException(404,'Resource not found')
    return service.review(db,row,user,payload)


@router.get('/{resource_id}/revisions')
def revisions(resource_id:str,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(locked_staff),db:Session=Depends(get_db)):
    return [dict(version=r.version,action=r.action,actor_id=r.actor_id,reason=r.reason,snapshot=r.snapshot,created_at=r.created_at)
        for r in db.scalars(select(ResourceRevision).where(ResourceRevision.resource_id==resource_id).order_by(ResourceRevision.version.desc()).offset(offset).limit(limit))]
