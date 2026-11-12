"""One reviewed operational product, independent of private hybrid settings."""
from datetime import timedelta
import hashlib,json
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select,update
from app.models import Station,StationIdentity,User,utc_now
from app.forecast_models import ForecastModel,ForecastApproval,ForecastDeployment,PublishedForecast
from app.forecast_schemas import ModelCard,ForecastEnvelope
from app.prediction_schemas import PredictionResponse,PublishedPredictionResponse,ForecastPoint,HORIZONS
from app.ml.water_depth import digest,validate_bundle,JsonDepthPredictor
from app.services.ml_predictor import predict_station
from app.services.station_security import utc
from app.services.mutation_audit import record

def admin_lock(db,user):
    changed=db.execute(update(User).where(User.id==user.id,User.role=='admin',User.is_active.is_(True)).values(version=User.version))
    if changed.rowcount!=1:raise HTTPException(403,'Active administrator required')

def register(db,user,bundle):
    admin_lock(db,user)
    if len(json.dumps(bundle,allow_nan=False).encode())>4*1024*1024:raise ValueError('Model bundle exceeds 4 MiB')
    validate_bundle(bundle);identity=digest(bundle)
    if not db.get(ForecastModel,identity):
        db.add(ForecastModel(id=identity,bundle=bundle,registered_by=user.id));db.flush()
        db.add(ForecastApproval(model_id=identity,version=0,state='draft'))
        record(db,user,'forecast_model',identity,'forecast_registered','Offline candidate registered; approval is separate',after={'model_card_id':identity})
    db.commit();return identity

def review(db,user,identity,payload):
    admin_lock(db,user);model=db.get(ForecastModel,identity)
    if not model:raise HTTPException(404,'Unknown model')
    if payload.decision=='approved':
        if model.registered_by==user.id:raise HTTPException(403,'Independent reviewer required; registrant cannot approve their own candidate')
        try:validate_bundle(model.bundle,approval=True)
        except ValueError as error:raise HTTPException(422,str(error)) from None
    changed=db.execute(update(ForecastApproval).where(ForecastApproval.model_id==identity,ForecastApproval.version==payload.expected_version)
        .values(state=payload.decision,version=ForecastApproval.version+1,reviewer_id=user.id,evidence_sha256=payload.evidence_sha256).execution_options(synchronize_session=False))
    if changed.rowcount!=1:db.rollback();raise HTTPException(409,'Model review changed; refresh and review manually')
    record(db,user,'forecast_model',identity,'forecast_reviewed',payload.reason,after={'state':payload.decision,'version':payload.expected_version+1,'evidence_sha256':payload.evidence_sha256})
    db.commit();return {'model_id':identity,'version':payload.expected_version+1,'state':payload.decision}

def deployment(db,station_id):
    row=db.get(ForecastDeployment,station_id,populate_existing=True)
    return dict(station_id=station_id,version=row.version if row else 0,model_id=row.model_id if row else None,configuration_hash=row.configuration_hash if row else None)

def binding(db,station_id,*,full_bundle=False):
    from app.device_config import current_configuration
    row=db.get(ForecastDeployment,station_id,populate_existing=True)
    if not row or not row.model_id:return None,'No independently approved water-depth adapter is deployed for this station.'
    if full_bundle:
        model=db.get(ForecastModel,row.model_id,populate_existing=True)
    else:
        # Viewer/readiness reads need only the small model card, never thousands
        # of held-out cases or coefficients. Publishers verify the complete hash.
        from types import SimpleNamespace
        entry=db.execute(select(ForecastModel.id,ForecastModel.bundle['card'],ForecastModel.bundle['decision_validation']['policy']).where(ForecastModel.id==row.model_id)).first()
        model=SimpleNamespace(id=entry[0],bundle={'card':entry[1],'decision_validation':{'policy':entry[2]}}) if entry else None
    approval=db.get(ForecastApproval,row.model_id,populate_existing=True)
    config=current_configuration(db,station_id);station=db.scalar(select(Station).where(Station.station_id==station_id))
    identity=db.get(StationIdentity,station_id,populate_existing=True)
    if not model or (full_bundle and digest(model.bundle)!=model.id):return None,'Registered model integrity is unavailable.'
    if not approval or approval.state!='approved' or approval.version!=row.model_review_version:return None,'Model approval changed; deployment requires manual review.'
    try:card=ModelCard.model_validate(model.bundle['card'])
    except ValueError:return None,'Registered model card is invalid.'
    if not identity or identity.state!='commissioned' or not station or station.status!='active' or not config or config.validation_status!='field_reviewed' or config.config_hash!=row.configuration_hash or config.config_hash!=card.configuration_hash or config.installation['datum']!=card.datum or card.station_id!=station_id:
        return None,'Site, datum, lifecycle or field-reviewed calibration no longer matches the forecast binding.'
    if not decision_policy_matches(model.bundle,config):return None,'Reviewed decision policy does not match station thresholds or measurement uncertainty.'
    return (row,model,card),'Reviewed binding available'

def decision_policy_matches(bundle,config):
    from app.ml.decision_evaluation import DecisionPolicy
    try:policy=DecisionPolicy.model_validate(bundle['decision_validation']['policy'])
    except (ValueError,KeyError,TypeError):return False
    installation=config.installation
    return policy.status=='reviewed' and policy.thresholds_cm==[installation[k] for k in ('advisory_cm','warning_cm','critical_cm')] and policy.measurement_uncertainty_cm>=installation['uncertainty_cm']

def configure(db,user,station_id,payload):
    from app.services.delivery_evidence import insert_for
    admin_lock(db,user)
    if not db.scalar(select(Station).where(Station.station_id==station_id)):raise HTTPException(404,'Unknown station')
    approval=None
    if payload.model_id:
        from app.device_config import current_configuration
        model=db.get(ForecastModel,payload.model_id);approval=db.get(ForecastApproval,payload.model_id)
        config=current_configuration(db,station_id)
        if not model or not approval or approval.state!='approved':raise HTTPException(422,'Choose an independently approved candidate')
        card=ModelCard.model_validate(model.bundle['card'])
        if card.station_id!=station_id or not config or config.validation_status!='field_reviewed' or config.config_hash!=payload.configuration_hash or card.configuration_hash!=config.config_hash or card.datum!=config.installation['datum']:
            raise HTTPException(422,'Reviewed site, datum and field calibration must match exactly')
        if not decision_policy_matches(model.bundle,config):raise HTTPException(422,'Reviewed decision policy must match station thresholds and uncertainty')
    db.execute(insert_for(db,ForecastDeployment,dict(station_id=station_id,version=0)).on_conflict_do_nothing())
    changed=db.execute(update(ForecastDeployment).where(ForecastDeployment.station_id==station_id,ForecastDeployment.version==payload.expected_version)
        .values(version=ForecastDeployment.version+1,model_id=payload.model_id,model_review_version=approval.version if approval else None,
            configuration_hash=payload.configuration_hash if approval else None,reviewed_by=user.id).execution_options(synchronize_session=False))
    if changed.rowcount!=1:db.rollback();raise HTTPException(409,'Forecast binding changed; refresh and review manually')
    record(db,user,'forecast_deployment',station_id,'forecast_binding_changed',payload.reason,after={'version':payload.expected_version+1,'model_card_id':payload.model_id,'config_hash':payload.configuration_hash})
    db.commit();return deployment(db,station_id)

def unavailable(db,station_id,allowed,reason,*,status='unavailable'):
    # No product means no selected model inputs. Do not rescan an hour of raw
    # observations per viewer; measurement freshness has its own read model.
    return PredictionResponse(station_id=station_id,status=status,reason=reason,source='none',checked_at=utc_now(),
        input_status='insufficient_data',sample_count=0,valid_sample_count=0,timestamp_basis='device_measured',preview_allowed=allowed,
        forecasts=[ForecastPoint(horizon_minutes=h) for h in HORIZONS])

def read_latest(db,station_id,preview_allowed):
    bound,reason=binding(db,station_id)
    if not bound:
        head=db.get(ForecastDeployment,station_id)
        return unavailable(db,station_id,preview_allowed,reason,status='not_trained' if not head or not head.model_id else 'unavailable')
    row,model,card=bound
    from app.runtime_models import SharedReadModel
    gate=db.get(SharedReadModel,'forecast-gate:'+station_id,populate_existing=True)
    if not gate or gate.generation!=str(row.version) or not gate.expires_at:
        return unavailable(db,station_id,preview_allowed,'Forecast input validation is absent or expired; waiting for the publisher.')
    if utc(gate.expires_at)<=utc_now():return unavailable(db,station_id,preview_allowed,'Forecast input validation expired; waiting for the publisher.',status='stale_data')
    if gate.payload['status']!='available':return unavailable(db,station_id,preview_allowed,gate.payload['reason'],status=gate.payload['status'])
    product=db.scalar(select(PublishedForecast).where(PublishedForecast.station_id==station_id).order_by(PublishedForecast.generated_at.desc(),PublishedForecast.id.desc()).limit(1))
    if not product:return unavailable(db,station_id,preview_allowed,'Approved adapter is waiting for a published product from the forecast worker.')
    data=PredictionResponse.model_validate(product.payload);now=utc_now()
    if not data.generated_at or utc(data.generated_at)>now or not data.data_cutoff or utc(data.data_cutoff)>now:return unavailable(db,station_id,preview_allowed,'Published timing cannot be reconciled with the current server clock.')
    identity=db.get(StationIdentity,station_id,populate_existing=True)
    if not identity or data.ingress_identity!=identity.device_id or data.registry_version!=identity.version:return unavailable(db,station_id,preview_allowed,'Published source identity changed; waiting for a new reviewed input product.')
    if data.deployment_version!=row.version or data.model_card_id!=model.id:return unavailable(db,station_id,preview_allowed,'Published product belongs to an older binding; waiting for regeneration.')
    if not data.valid_until or utc(data.valid_until)<=now:
        return data.model_copy(update={'status':'stale_data','source':'none','checked_at':now,'forecasts':[ForecastPoint(horizon_minutes=h) for h in HORIZONS],
            'reason':'Published forecast expired; measured observations remain separate.','preview_allowed':preview_allowed})
    return data.model_copy(update={'checked_at':now,'preview_allowed':preview_allowed})

def publish_station(db,station_id):
    # Serialize publishers on the station binding, including SQLite's write lock.
    changed=db.execute(update(ForecastDeployment).where(ForecastDeployment.station_id==station_id).values(version=ForecastDeployment.version))
    if changed.rowcount!=1:db.rollback();return None
    bound,_=binding(db,station_id,full_bundle=True)
    if not bound:db.rollback();return None
    row,model,card=bound
    result=predict_station(db,station_id,JsonDepthPredictor(model.bundle,model.id),False)
    from app.runtime_models import SharedReadModel
    from app.services.delivery_evidence import insert_for
    now=utc_now();key='forecast-gate:'+station_id
    db.execute(insert_for(db,SharedReadModel,dict(key=key,generation=str(row.version))).on_conflict_do_nothing())
    db.execute(update(SharedReadModel).where(SharedReadModel.key==key).values(generation=str(row.version),payload=dict(status=result.status,reason=result.reason),checked_at=now,expires_at=now+timedelta(seconds=60)))
    if result.status!='available':db.commit();return None
    fingerprint=digest([row.version,model.id,result.input_last_recorded_at.isoformat(),result.input_window_start.isoformat(),result.sample_count])
    previous=db.scalar(select(PublishedForecast).where(PublishedForecast.station_id==station_id,PublishedForecast.input_fingerprint==fingerprint))
    if previous:db.commit();return previous.id
    identity=str(uuid4())
    source=db.get(StationIdentity,station_id,populate_existing=True)
    from app.ml.decision_evaluation import evaluate
    from app.prediction_schemas import ForecastUncertainty
    evaluation=evaluate(model.bundle)
    if not evaluation['release_ready']:db.rollback();return None
    radius=evaluation['radius_cm']
    result=result.model_copy(update={'uncertainty':ForecastUncertainty(method=evaluation['method'],nominal_coverage=evaluation['nominal_coverage'],withheld_event_coverage=evaluation['event_coverage'],
        calibration_events=evaluation['calibration_events'],test_events=evaluation['test_events'],policy_sha256=evaluation['policy_sha256'],display_resolution_cm=max(1,evaluation['policy']['measurement_uncertainty_cm'])),
        'forecasts':[p.model_copy(update={'lower_depth_cm':max(0,p.water_depth_cm-radius),'upper_depth_cm':min(1000,p.water_depth_cm+radius)}) for p in result.forecasts]})
    result=result.model_copy(update=dict(forecast_id=identity,deployment_version=row.version,configuration_hash=row.configuration_hash,
        reference_datum=card.datum,model_card_id=model.id,data_cutoff=result.input_last_recorded_at,measurement_source='registry_verified_physical_device',ingress_identity=source.device_id,registry_version=source.version))
    result=PublishedPredictionResponse.model_validate(result.model_dump())
    db.add(PublishedForecast(id=identity,station_id=station_id,input_fingerprint=fingerprint,generated_at=result.generated_at,valid_until=result.valid_until,payload=result.model_dump(mode='json')))
    db.commit();return identity

def historical(db,identity):
    product=db.get(PublishedForecast,identity)
    if not product:raise HTTPException(404,'Unknown forecast product')
    data=PublishedPredictionResponse.model_validate(product.payload);bound,_=binding(db,product.station_id);now=utc_now()
    latest=read_latest(db,product.station_id,False)
    current=latest.status=='available' and latest.forecast_id==identity
    return ForecastEnvelope(product=data,read_at=now,current=current)

def tick():
    from app.database import SessionLocal
    from app.config import get_settings
    budget=get_settings().read_model_max_stations
    with SessionLocal() as db:ids=list(db.scalars(select(ForecastDeployment.station_id).where(ForecastDeployment.model_id.is_not(None)).limit(budget+1)))
    if len(ids)>budget:raise ValueError('Forecast station budget exceeded; review deployment capacity')
    count=0
    for station_id in ids:
        with SessionLocal() as db:count+=bool(publish_station(db,station_id))
        from app.services import observability as obs
        obs.heartbeat('forecasts')
    return count

def candidate_evidence(db,identity):
    model=db.get(ForecastModel,identity);approval=db.get(ForecastApproval,identity)
    if not model or not approval:raise HTTPException(404,'Registered evaluation unavailable')
    if digest(model.bundle)!=model.id:raise HTTPException(503,'Registered model evidence failed its immutable identity check')
    _,report=validate_bundle(model.bundle)
    from app.ml.decision_evaluation import evaluate
    return dict(id=model.id,card=model.bundle['card'],state=approval.state,version=approval.version,
        evaluation=report,decision_evaluation=evaluate(model.bundle))


def workspace(db,station_id,limit,offset):
    from sqlalchemy import func
    now=utc_now();head=db.get(ForecastDeployment,station_id,populate_existing=True)
    approval=db.get(ForecastApproval,head.model_id,populate_existing=True) if head and head.model_id else None
    latest=read_latest(db,station_id,False)
    query=select(PublishedForecast).where(PublishedForecast.station_id==station_id)
    rows=db.scalars(query.order_by(PublishedForecast.generated_at.desc(),PublishedForecast.id.desc()).offset(offset).limit(limit)).all()
    total=db.scalar(select(func.count()).select_from(PublishedForecast).where(PublishedForecast.station_id==station_id))
    products=[ForecastEnvelope(product=PublishedPredictionResponse.model_validate(row.payload),read_at=now,
        current=latest.status=='available' and latest.forecast_id==row.id) for row in rows]
    return dict(station_id=station_id,checked_at=now,
        deployment={**deployment(db,station_id),'model_review_version':head.model_review_version if head else None},
        model=dict(id=head.model_id,state=approval.state if approval else 'unavailable',version=approval.version if approval else 0,
            evidence_sha256=approval.evidence_sha256 if approval else None) if head and head.model_id else None,
        publication_status=latest.status,publication_reason=latest.reason,
        current_forecast_id=latest.forecast_id if latest.status=='available' else None,
        products=products,total=total,has_more=offset+len(rows)<total)


def catalog(db,settings):
    from pathlib import Path
    models=[]
    for model,approval in db.execute(select(ForecastModel,ForecastApproval).join(ForecastApproval).order_by(ForecastModel.created_at.desc()).limit(100)):
        _,report=validate_bundle(model.bundle)
        from app.ml.decision_evaluation import evaluate
        models.append(dict(id=model.id,card=model.bundle['card'],state=approval.state,version=approval.version,evaluation=report,decision_evaluation=evaluate(model.bundle)))
    experiment=dict(status='unavailable',workspace='private_experiment',reason='Configured experimental artifacts are unavailable')
    if settings.environment=='development' and settings.hybrid_projection_enabled:
        try:
            root=Path(settings.hybrid_model_directory);metadata=json.loads((root/'metadata.json').read_text(encoding='utf-8'))
            forest=root/'forest.json';dataset=Path(settings.hybrid_dataset_path)
            if hashlib.sha256(forest.read_bytes()).hexdigest()!=metadata['files']['forest.json']['sha256'] or hashlib.sha256(dataset.read_bytes()).hexdigest()!=metadata['dataset']['sha256']:raise ValueError('Integrity')
            evaluation_bytes=(root/'evaluation.json').read_bytes();evaluation=json.loads(evaluation_bytes)
            experiment=dict(status='available',workspace='private_experiment',model_version=metadata['version'],artifact_sha256=metadata['files']['forest.json']['sha256'],evaluation_sha256=hashlib.sha256(evaluation_bytes).hexdigest(),
                source=metadata['source'],training_cutoff=metadata['splits']['train']['end'],splits=metadata['splits'],evaluation=evaluation,
                notice='Rainfall evaluation only; never evidence of field water-depth accuracy')
        except (OSError,ValueError,KeyError,TypeError):pass
    return dict(checked_at=utc_now(),operational=models,experimental=experiment)
