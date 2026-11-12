"""Synthetic registry/receipt evidence only; no live resource or authority seeded."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, func, create_engine
from app.main import app
from app.database import SessionLocal
from app.models import User, SosRequest, utc_now
from app.governance_models import AlertAuthority, AuthorityGrant, VerifiedArea
from app.resource_models import ResponseResource, ResourceRevision
from test_accounts import account, headers, reset_accounts, staff

URL='/api/response-resources'

@pytest.fixture
def registry(client):
    access=staff(client)
    resident=headers(client.post('/api/auth/register',json=account()))
    with SessionLocal() as db:
        actor=db.scalar(select(User).where(User.role=='admin'))
        for code in ['TEST_AREA_A','TEST_AREA_B']:
            db.add(VerifiedArea(id=code,name='Isolated synthetic '+code,identifier_scheme='TEST ONLY',evidence='Synthetic jurisdiction fixture',area_class='geographic'))
        db.add(AlertAuthority(id='TEST_AUTH',name='Synthetic public issuer - not real',evidence='Isolated test fixture',authority_class='public_authority'))
        db.add(AlertAuthority(id='TEST_APP',name='Synthetic app issuer',evidence='Isolated exercise fixture',authority_class='app_operator'))
        db.flush()
        for code in ['TEST_AUTH','TEST_APP']:
            db.add(AuthorityGrant(authority_id=code,user_id=actor.id,area_ids=['TEST_AREA_A'],station_ids=[],citywide=False))
        db.commit()
    return access,resident


def body(identifier='TEST_SHELTER',**changes):
    return dict(id=identifier,kind='shelter',authority_id='TEST_AUTH',area_ids=['TEST_AREA_A'],mode='Actual',expected_version=0,
        source='Synthetic source record; no real shelter claim',reason='Isolated resource test review',data=dict(name='Synthetic shelter',address='Synthetic test entrance',
        point=dict(latitude=15.976,longitude=120.571),state='active',activated_at=(utc_now()-timedelta(minutes=5)).isoformat(),
        capacity=None,occupancy=None,capacity_observed_at=None,wheelchair_accessible=None,services=[],access_constraints='Synthetic access restriction',
        instructions='Synthetic instructions for isolated tests',contacts=[dict(name='Synthetic contact',contact='TEST ONLY - no real phone',hours='Exercise only')]),**changes)


def save(client,access,data=None):
    r=client.post(URL,headers=access,json=data or body());assert r.status_code==200,r.text
    return r.json()


def verify(client,access,row,**changes):
    return client.post(URL+'/'+row['id']+'/review',headers=access,json={**dict(expected_version=row['version'],action='verify',reason='Synthetic verification evidence reviewed',expires_at=(utc_now()+timedelta(hours=2)).isoformat()),**changes})


def test_authority_scoped_writes_drafts_exercise_and_no_defaults(client,registry):
    access,resident=registry
    response=client.get(URL,headers=resident)
    assert response.headers['cache-control']=='no-store'
    assert response.json()['items']==[]
    assert client.post(URL,json=body()).status_code==401
    assert client.post(URL,headers=resident,json=body()).status_code==403
    officer=staff(client,'officer')
    assert client.post(URL,headers=officer,json=body()).status_code==403
    assert client.post(URL,headers=access,json={**body(), 'area_ids':['TEST_AREA_B']}).status_code==403
    assert client.post(URL,headers=access,json={**body(), 'authority_id':'TEST_APP'}).status_code==403
    row=save(client,access)
    assert row['verification']=='unverified' and not row['published']
    assert client.get(URL,headers=resident).json()['total']==0
    assert client.get(URL+'?include_drafts=true',headers=resident).status_code==403
    exercise=save(client,access,{**body('TEST_EXERCISE'),'authority_id':'TEST_APP','mode':'Exercise'})
    verified=verify(client,access,exercise).json()
    assert not verified['route_candidate']
    assert client.get(URL+'?mode=Exercise',headers=resident).status_code==403
    assert client.get(URL,headers=resident).json()['total']==0


def test_verification_expiry_full_capacity_unknown_and_withdrawal(client,registry):
    access,resident=registry
    row=save(client,access)
    row=verify(client,access,row).json()
    assert row['verification']=='verified' and row['route_candidate']
    assert row['data']['capacity'] is None and not row['capacity_current']
    assert row['route_safety']=='not_established'
    data=body();data.update(expected_version=row['version']);data['data'].update(capacity=10,occupancy=10,capacity_observed_at=(utc_now()-timedelta(hours=1)).isoformat())
    row=save(client,access,data)
    assert row['published'] and row['verification']=='unverified' and not row['route_candidate']
    row=verify(client,access,row).json()
    assert row['effective_state']=='full' and not row['capacity_current'] and not row['route_candidate']
    with SessionLocal() as db:
        db.get(ResponseResource,row['id']).expires_at=utc_now()-timedelta(seconds=1);db.commit()
    item=client.get(URL,headers=resident).json()['items'][0]
    assert item['verification']=='expired' and not item['route_candidate']
    r=verify(client,access,row,action='withdraw')
    assert r.status_code==200 and r.json()['verification']=='withdrawn'
    assert client.get(URL,headers=resident).json()['items'][0]['verification']=='withdrawn'


def test_edit_verify_cas_immutable_revision_and_actor_audit(client,registry):
    access,_=registry
    row=save(client,access)
    edit=body();edit.update(expected_version=1,source='New synthetic evidence')
    current=save(client,access,edit)
    stale=verify(client,access,row)
    assert stale.status_code==409 and stale.json()['detail']['current']['version']==2
    assert client.post(URL,headers=access,json=edit).status_code==409
    row=verify(client,access,current).json()
    revisions=client.get(URL+'/'+row['id']+'/revisions',headers=access).json()
    assert [r['version'] for r in revisions]==[3,2,1]
    assert all(r['actor_id'] and r['reason'] for r in revisions)
    assert 'password' not in str(revisions) and 'access_token' not in str(revisions)
    with SessionLocal() as db:
        revision=db.scalar(select(ResourceRevision));revision.reason='Overwrite attempt'
        with pytest.raises(ValueError,match='append-only'):db.commit()
        db.rollback()
        authority=db.get(AlertAuthority,'TEST_AUTH');authority.active=False;db.commit()
    item=client.get(URL).status_code
    assert item==401
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ResourceRevision))==3


def test_concurrent_edit_has_one_winner_and_requires_manual_review(client,registry):
    access,_=registry
    save(client,access)
    payload={**body(),'expected_version':1}
    def write(index):
        with TestClient(app) as c:
            return c.post(URL,headers=access,json={**payload,'source':'Synthetic concurrent editor '+str(index)})
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(write,range(2)))
    assert sorted(r.status_code for r in responses)==[200,409]
    with SessionLocal() as db:
        assert db.get(ResponseResource,'TEST_SHELTER').version==2
        assert db.scalar(select(func.count()).select_from(ResourceRevision))==2


@pytest.mark.parametrize('change',[
    {'capacity':2}, {'state':'active','activated_at':None}, {'point':{'latitude':float('inf'),'longitude':0}},
    {'capacity':1.5,'capacity_observed_at':'2026-01-01T00:00:00Z'}, {'activated_at':'2026-01-01T00:00:00'},
])
def test_invalid_channel_contracts_are_rejected(client,registry,change):
    access,_=registry;data=body();data['data'].update(change)
    # JSON cannot represent infinity: exercise the schema directly for that case.
    if change.get('point'):
        from app.resource_schemas import ResourceWrite
        with pytest.raises(ValueError):ResourceWrite.model_validate(data)
    else:assert client.post(URL,headers=access,json=data).status_code==422


def test_bounded_exact_area_filter_road_and_preparedness(client,registry):
    access,resident=registry
    for i in range(2):verify(client,access,save(client,access,body('TEST_SHELTER_'+str(i))))
    assert client.get(URL+'?limit=1&offset=1&area_id=TEST_AREA_A',headers=resident).json()['total']==2
    assert len(client.get(URL+'?limit=1&offset=1',headers=resident).json()['items'])==1
    assert client.get(URL+'?area_id=TEST_AREA',headers=resident).json()['total']==0
    assert client.get(URL+'?limit=101',headers=resident).status_code==422
    road={**body('TEST_ROAD'),'kind':'road','data':dict(name='Synthetic road',state='closed',geometry=[dict(latitude=15,longitude=120),dict(latitude=15.01,longitude=120.01)],access_constraints='Synthetic blockage',instructions='Synthetic test instructions',contacts=body()['data']['contacts'])}
    verify(client,access,save(client,access,road))
    item=client.get(URL+'?kind=road',headers=resident).json()
    assert item['items'][0]['data']['state']=='closed' and 'partial' in item['road_coverage']
    preparedness={**body('TEST_READY'),'kind':'preparedness','data':{k:v for k,v in body()['data'].items() if k in ['name','instructions','contacts']}}
    verify(client,access,save(client,access,preparedness))
    assert client.get(URL+'?kind=preparedness',headers=resident).json()['total']==1


def test_empty_additive_migration_is_idempotent(tmp_path):
    from app.migrate_response_resources import migrate,missing,require_schema
    bind=create_engine('sqlite:///'+str(tmp_path/'resources.db'))
    with bind.begin() as c:c.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY)')
    with pytest.raises(RuntimeError):require_schema(bind)
    assert len(migrate(bind)['tables'])==2
    assert migrate(bind,apply=True)['records_seeded']==0
    assert not missing(bind) and not migrate(bind,apply=True)['tables']
    with bind.connect() as c:assert c.exec_driver_sql('SELECT COUNT(*) FROM response_resources').scalar()==0
    bind.dispose()


def test_exact_payload_receipt_is_read_only_private_and_survives_location_updates(client,registry):
    _,resident=registry
    from test_sos import payload
    data=payload()
    assert client.post('/api/sos/receipt',headers=resident,json=data).json()['receipt']=='unseen'
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(SosRequest))==0
    row=client.post('/api/sos',headers=resident,json=data).json()
    other=headers(client.post('/api/auth/register',json=account('other@example.com')))
    assert client.post('/api/sos/receipt',headers=other,json=data).json()['receipt']=='unseen'
    assert client.post('/api/sos/receipt',headers=resident,json={**data,'message':'Different payload'}).json()['receipt']=='conflict'
    fix=dict(expected_version=1,latitude=15.98,longitude=120.58,accuracy_m=4,location_recorded_at=utc_now().isoformat())
    assert client.patch('/api/sos/'+str(row['id'])+'/location',headers=resident,json=fix).status_code==200
    receipt=client.post('/api/sos/receipt',headers=resident,json=data).json()
    assert receipt['receipt']=='received' and receipt['item']['version']==2
    assert receipt['item']['latitude']==15.98
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(SosRequest))==1
