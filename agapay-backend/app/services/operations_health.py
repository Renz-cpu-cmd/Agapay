"""Workflow readiness: observed dependencies, progress and actionable fault codes."""
from datetime import timedelta
import errno,json,os,shutil,sqlite3,tempfile
from pathlib import Path
from contextlib import closing
from sqlalchemy import func,select
from app.models import NotificationDelivery,Station,StationIdentity,Telemetry,utc_now
from app.identity_models import IdentityMail,IdentityAction
from app.runtime_models import WorkerHeartbeat,OperatorAlert,SharedReadModel
from app.services.station_security import utc
from app.services.broker_health import snapshot as broker_snapshot
from app.services import observability as obs


def storage_probe(path,min_free_bytes,*,write=False):
    target=Path(path);parent=target.parent
    if not parent.is_dir():return 'RAIN_STORAGE_MISSING'
    if shutil.disk_usage(parent).free<min_free_bytes:return 'RAIN_STORAGE_FULL'
    if not target.is_file():return 'RAIN_JOURNAL_MISSING'
    try:
        from urllib.parse import quote
        with closing(sqlite3.connect(f'file:{quote(target.resolve().as_posix())}?mode=rw',uri=True,timeout=.2)) as store:
            store.execute('SELECT id FROM events LIMIT 1').fetchone()
            from app.services.rain_rollups import VERSION
            if store.execute('PRAGMA user_version').fetchone()[0]!=VERSION:return 'RAIN_SCHEMA_MIGRATION_REQUIRED'
            if write:
                store.execute('BEGIN IMMEDIATE')
                store.execute('UPDATE events SET received=received WHERE 0')
                store.rollback()
        if write:
            descriptor,name=tempfile.mkstemp(prefix='.agapay-health-',dir=parent)
            try:
                os.write(descriptor,b'AGAPAY readiness probe\n');os.fsync(descriptor)
            finally:
                os.close(descriptor);Path(name).unlink(missing_ok=True)
    except OSError as error:
        return 'RAIN_STORAGE_FULL' if error.errno==errno.ENOSPC else 'RAIN_WRITE_FAILED'
    except sqlite3.Error:return 'RAIN_JOURNAL_UNAVAILABLE'
    return None


def diagnostics(db,settings,*,now=None,write_probe=False):
    now=utc(now or utc_now());components=[];alerts=[]
    def component(name,state,code=None,message='',**detail):
        required=name in settings.operations_required
        item=dict(name=name,state=state,required=required,code=code,message=message,**detail)
        components.append(item)
        if code:alerts.append(dict(code=code,severity='critical' if required else 'warning',message=message))
    beats={row.role:row for row in db.scalars(select(WorkerHeartbeat))}
    def worker(role):
        beat=beats.get(role)
        if not beat or (now-utc(beat.observed_at)).total_seconds()>45:return role.upper().replace('-','_')+'_WORKER_STALE'
        if beat.state!='healthy':return role.upper().replace('-','_')+'_WORKER_'+beat.state.upper()
        if not beat.last_success_at or (now-utc(beat.last_success_at)).total_seconds()>45:return role.upper().replace('-','_')+'_WORKER_NO_PROGRESS'
        return None
    if settings.read_model_worker_enabled:
        fault=worker('read-model');component('monitoring','degraded' if fault else 'healthy',fault,'Monitoring read-model producer is not progressing' if fault else 'Read-model producer is progressing')
    else:component('monitoring','healthy',message='Bounded on-demand shared read model; no background producer required')
    if settings.mqtt_enabled:
        from app.services.broker_health import subscription_snapshot
        broker=broker_snapshot(True,shared_path=settings.mqtt_status_path if settings.mqtt_external_subscriber else '',now=now)
        subscribed=subscription_snapshot(settings,now=now)
        fault='BROKER_DISCONNECTED' if broker['state']=='disconnected' else 'BROKER_HEARTBEAT_STALE' if broker['state']!='connected' else 'BROKER_SUBSCRIPTION_REJECTED' if subscribed=='rejected' else 'BROKER_SUBSCRIPTION_UNCONFIRMED' if subscribed!='confirmed' else None
        component('mqtt','degraded' if fault else 'healthy',fault,'MQTT authentication/connection/subscription is not confirmed' if fault else 'Broker connection and subscription acknowledged',subscription=subscribed)
    else:component('mqtt','disabled','BROKER_REQUIRED_DISABLED' if 'mqtt' in settings.operations_required else None,'Broker ingestion is disabled')
    if settings.rain_gauge_enabled:
        fault=storage_probe(settings.rain_gauge_store_path,settings.operations_min_free_bytes,write=write_probe)
        if not write_probe and settings.operations_probe_enabled:
            persisted=db.scalar(select(OperatorAlert).where(OperatorAlert.resolved_at.is_(None),
                OperatorAlert.code.in_(('RAIN_WRITE_FAILED','RAIN_STORAGE_FULL','RAIN_JOURNAL_UNAVAILABLE'))))
            fault=fault or (persisted.code if persisted else None) or ('RAIN_WRITE_PROBE_STALE' if worker('diagnostics') else None)
        if not fault and not write_probe and not settings.operations_probe_enabled and 'rain' in settings.operations_required:fault='RAIN_WRITE_PROBE_DISABLED'
        component('rain','degraded' if fault else 'healthy',fault,'Rain journal storage/write capability cannot be confirmed' if fault else 'Rain journal readable; '+('write probe passed' if write_probe else 'scheduled write probe required' if settings.operations_probe_enabled else 'scheduled write probe disabled'),write_probed=write_probe)
    else:component('rain','disabled','RAIN_REQUIRED_DISABLED' if 'rain' in settings.operations_required else None,'Independent rain ingestion is disabled')
    # Queues are bounded aggregate reads; uncertain sends are never blindly retried.
    from app.delivery_models import DeliveryControl
    from sqlalchemy import exists,or_
    from app.services import delivery_recovery
    # Recovery-held rows are reported by the delivery_recovery component, not as queue age.
    unresolved=~exists(select(DeliveryControl.delivery_id).where(DeliveryControl.delivery_id==NotificationDelivery.id,DeliveryControl.review_status.in_(('provider_accepted','not_accepted','closed_no_resend'))))&delivery_recovery.not_held('operational',NotificationDelivery.id)
    pending,oldest=db.execute(select(func.count(),func.min(NotificationDelivery.created_at)).where(NotificationDelivery.state=='PENDING',unresolved)).one()
    processing,attempted=db.execute(select(func.count(),func.min(NotificationDelivery.attempted_at)).where(NotificationDelivery.state=='PROCESSING',unresolved)).one()
    unknown=db.scalar(select(func.count()).select_from(NotificationDelivery).where(NotificationDelivery.state=='UNKNOWN',unresolved))
    failed=db.scalar(select(func.count()).select_from(NotificationDelivery).where(NotificationDelivery.state=='FAILED',unresolved))
    queue_age=max(0,(now-utc(oldest)).total_seconds()) if oldest else 0
    processing_age=max(0,(now-utc(attempted)).total_seconds()) if attempted else 0
    stalled_count=db.scalar(select(func.count()).select_from(NotificationDelivery).where(NotificationDelivery.state=='PROCESSING',unresolved,
        func.coalesce(NotificationDelivery.attempted_at,NotificationDelivery.created_at)<now-timedelta(seconds=settings.operations_queue_age_seconds)))
    enabled=settings.notification_provider!='disabled'
    fault=worker('notifications') if enabled else 'NOTIFICATIONS_REQUIRED_DISABLED' if 'notifications' in settings.operations_required else None
    if unknown:fault='NOTIFICATION_DELIVERY_UNCERTAIN'
    elif stalled_count:fault='NOTIFICATION_DELIVERY_STALLED'
    elif pending and queue_age>settings.operations_queue_age_seconds:fault='NOTIFICATION_QUEUE_OLD'
    elif failed:fault='NOTIFICATION_DELIVERY_FAILED'
    component('notifications','degraded' if fault else 'healthy' if enabled else 'disabled',fault,
        'Notification delivery needs operator review; no automatic uncertain resend' if fault else 'Delivery worker and queue within configured budget' if enabled else 'External notification delivery is disabled',
        pending=pending,processing=processing,uncertain=unknown,failed=failed,oldest_pending_seconds=queue_age,
        oldest_processing_seconds=processing_age if attempted else None,stalled=stalled_count,
        queue_budget_seconds=settings.operations_queue_age_seconds,provider_mode=settings.notification_provider)
    mail_count=db.scalar(select(func.count()).select_from(IdentityMail).where(IdentityMail.state=='SENDING'))
    enabled=settings.identity_mail_provider!='disabled'
    fault=worker('identity-mail') if enabled else 'IDENTITY_MAIL_REQUIRED_DISABLED' if 'identity_mail' in settings.operations_required else None
    if mail_count:fault=fault or 'IDENTITY_MAIL_IN_FLIGHT' # Not an error until its worker stops progressing.
    if mail_count and not worker('identity-mail'):fault=None
    mail_unknown=db.scalar(select(func.count()).select_from(IdentityMail).where(IdentityMail.state=='UNKNOWN'))
    mail_oldest=db.scalar(select(func.min(IdentityAction.created_at)).join(IdentityMail,IdentityMail.action_hash==IdentityAction.token_hash).where(IdentityMail.state=='PENDING'))
    mail_age=max(0,(now-utc(mail_oldest)).total_seconds()) if mail_oldest else 0
    if mail_unknown:fault='IDENTITY_MAIL_DELIVERY_UNCERTAIN'
    elif mail_age>settings.operations_queue_age_seconds:fault='IDENTITY_MAIL_QUEUE_OLD'
    component('identity_mail','degraded' if fault else 'healthy' if enabled else 'disabled',fault,'Account email worker needs review' if fault else 'Account email capability state',in_flight=mail_count)
    if settings.hybrid_projection_enabled:
        try:
            from app.services.hybrid_projection import get_engine
            get_engine(settings.hybrid_model_directory,settings.hybrid_dataset_path)
            component('models','healthy',message='Model manifest, estimator and dataset verified; scientific/field validity is separate')
        except (OSError,ValueError,KeyError,ImportError):component('models','degraded','MODEL_ARTIFACT_UNAVAILABLE','Projection artifacts/runtime unavailable or integrity check failed')
    else:component('models','disabled','MODEL_REQUIRED_DISABLED' if 'models' in settings.operations_required else None,'Experimental projection is disabled')
    from app.forecast_models import ForecastDeployment,PublishedForecast
    from app.services.forecast_registry import binding
    deployments=list(db.scalars(select(ForecastDeployment.station_id).where(ForecastDeployment.model_id.is_not(None)).limit(settings.read_model_max_stations+1)))
    forecast_fault=None
    if len(deployments)>settings.read_model_max_stations:forecast_fault='FORECAST_STATION_BUDGET_EXCEEDED'
    elif deployments:
        forecast_fault=worker('forecasts')
        if not forecast_fault:
            for station_id in deployments:
                bound,_=binding(db,station_id)
                if not bound:forecast_fault='FORECAST_BINDING_INVALID';break
                gate=db.get(SharedReadModel,'forecast-gate:'+station_id,populate_existing=True)
                if not gate or gate.generation!=str(bound[0].version) or not gate.expires_at or utc(gate.expires_at)<=now:
                    forecast_fault='FORECAST_INPUT_UNAVAILABLE';break
                if gate.payload.get('status')!='available':
                    forecast_fault='FORECAST_INPUT_OUT_OF_DOMAIN' if 'outside the reviewed training feature domain' in gate.payload.get('reason','') else 'FORECAST_INPUT_UNAVAILABLE';break
                product=db.scalar(select(PublishedForecast).where(PublishedForecast.station_id==station_id).order_by(PublishedForecast.generated_at.desc()).limit(1))
                if not product or utc(product.valid_until)<=now or product.payload.get('deployment_version')!=bound[0].version:
                    forecast_fault='FORECAST_PRODUCT_UNAVAILABLE';break
    elif 'forecasting' in settings.operations_required:forecast_fault='FORECAST_NOT_CONFIGURED'
    component('forecasting','degraded' if forecast_fault else 'healthy' if deployments else 'disabled',forecast_fault,
        'Published water-depth forecast workflow requires attention' if forecast_fault else 'Reviewed forecast publisher and products are current' if deployments else 'No operational water-depth adapter deployed; clients receive unavailable')
    latest=select(Telemetry.station_id,func.max(Telemetry.received_at).label('received')).where(Telemetry.eligible_for_current.is_(True)).group_by(Telemetry.station_id).subquery()
    stations=db.execute(select(Station.station_id,latest.c.received).join(StationIdentity,StationIdentity.station_id==Station.station_id)
        .outerjoin(latest,latest.c.station_id==Station.station_id).where(Station.status=='active',StationIdentity.state=='commissioned').limit(settings.read_model_max_stations+1)).all()
    stale=sum(at is None or (now-utc(at)).total_seconds()>settings.telemetry_stale_after_seconds for _,at in stations)
    if stale:alerts.append(dict(code='OPERATIONAL_INGRESS_STALE',severity='warning',message=f'{stale} active station(s) have no recent eligible water measurement; original timestamps remain visible'))
    if len(stations)>settings.read_model_max_stations:
        alerts.append(dict(code='READ_MODEL_STATION_BUDGET_EXCEEDED',severity='critical',message='Configured station count exceeds the reviewed read-model budget'))
        components[0].update(state='degraded',code='READ_MODEL_STATION_BUDGET_EXCEEDED')
    values=obs.metrics(db,now=now)
    stalled=db.scalar(select(func.count()).select_from(SharedReadModel).where(SharedReadModel.lease_token.is_not(None),SharedReadModel.lease_until<now))
    if stalled:alerts.append(dict(code='READ_MODEL_PRODUCER_STALLED',severity='warning',message='A read-model/inference producer lease expired; next read may take over without accepting late output'))
    monitoring_stalled=db.scalar(select(func.count()).select_from(SharedReadModel).where(SharedReadModel.key.like('monitor:%'),SharedReadModel.lease_token.is_not(None),SharedReadModel.lease_until<now))
    if monitoring_stalled:components[0].update(state='degraded',code='READ_MODEL_PRODUCER_STALLED',message='Monitoring producer lease expired; current read model is unavailable')
    live=values.get('ingest.live')
    within_budget=sum(count for bound,count in live['histogram'].items() if bound!='inf' and float(bound)<=5) if live else 0
    if live and live['count']>=20 and within_budget/live['count']<.95:
        alerts.append(dict(code='INGESTION_LATENCY_BUDGET_BURN',severity='warning',message='Eligible ingestion latency exceeds the provisional five-second p95 budget'))
    http=[v for k,v in values.items() if k.startswith('http.') and k!='http.queries']
    count=sum(v['count'] for v in http);failed=sum(v['failures'] for v in http)
    if count>=20 and failed/count>.01:alerts.append(dict(code='HTTP_ERROR_BUDGET_BURN',severity='warning',message='Five-minute HTTP 5xx fraction exceeds 1%; investigate correlated workflow failures'))
    from app.services.privacy_governance import deployment_status, require_released
    governance=deployment_status(settings)
    if settings.environment=='production':
        fault=None if governance['status']=='organization_attested' else 'PRIVACY_SERVICE_REVIEW_REQUIRED'
        component('governance','degraded' if fault else 'healthy',fault,'Current organizational privacy and service review required' if fault else 'Organizational review record is current')
        components[-1]['required']=True
    try:require_released(db)
    except RuntimeError:
        component('recovery','degraded','RESTORE_QUARANTINED','Restored data must be reconciled before activation')
        components[-1]['required']=True
    # Not required for readiness: ingestion and local alarms continue while delivery is fenced.
    fence=delivery_recovery.status(db,settings)
    code=None if fence['open'] and not fence['undecided'] else 'DELIVERY_RECOVERY_UNDECIDED' if fence['open'] else 'DELIVERY_RECOVERY_FENCED'
    component('delivery_recovery','degraded' if code else 'healthy',code,
        fence['reason'] or ('Held deliveries await reconciliation; they are never resent' if code else 'Delivery generation active; no undecided recovery holds'),
        generation=fence['generation'],generation_state=fence['state'],undecided_holds=fence['undecided'],ledger=fence['ledger'])
    ready=not any(c['required'] and c['state']!='healthy' for c in components)
    workers=[dict(role=row.role,state=row.state,observed_at=utc(row.observed_at).isoformat(),
        last_success_at=utc(row.last_success_at).isoformat() if row.last_success_at else None,
        age_seconds=max(0,(now-utc(row.observed_at)).total_seconds()),
        fresh=0<=(now-utc(row.observed_at)).total_seconds()<=45) for row in beats.values()]
    return dict(checked_at=now.isoformat(),status='healthy' if not alerts else 'degraded',ready=ready,
                components=components,alerts=alerts,metrics_window_minutes=5,metrics=values,workers=workers,
                ingress=dict(stations_checked=len(stations),stale_or_missing_eligible_receipt_count=stale,
                    receipt_budget_seconds=settings.telemetry_stale_after_seconds,bounded=len(stations)>settings.read_model_max_stations),
                budgets=dict(station_limit=settings.read_model_max_stations,water_attempts_per_station_minute=settings.telemetry_ingest_per_minute,
                    rain_attempts_per_station_minute=settings.rain_ingest_per_minute,queue_age_seconds=settings.operations_queue_age_seconds),
                external_quotas=[dict(service=name,state='unknown',reason='Provider quota and billing telemetry are not connected; configured limits are not remaining provider capacity')
                    for name in ('push','maps','identity_mail')])


def reconcile(db,report):
    now=utc_now();active={item['code']:item for item in report['alerts']}
    rows={r.code:r for r in db.scalars(select(OperatorAlert))}
    for code,item in active.items():
        row=rows.get(code)
        if row is None:
            row=OperatorAlert(code=code,severity=item['severity'],message=item['message'],first_seen_at=now,last_seen_at=now);db.add(row)
            obs.event('operator_alert.opened',code=code,state=item['severity'])
        elif row.resolved_at:
            row.resolved_at=None;row.first_seen_at=now;obs.event('operator_alert.reopened',code=code,state=item['severity'])
        row.last_seen_at=now;row.message=item['message'];row.severity=item['severity']
    for code,row in rows.items():
        if code not in active and row.resolved_at is None:
            row.resolved_at=now;obs.event('operator_alert.resolved',code=code,state='resolved')
    db.commit()


def public_summary(report):
    return dict(status=report['status'],checked_at=report['checked_at'],codes=[a['code'] for a in report['alerts']],
                message='Some live services are degraded. Check observation timestamps and delivery status.' if report['alerts'] else 'Configured workflows are within their operational budgets.')
