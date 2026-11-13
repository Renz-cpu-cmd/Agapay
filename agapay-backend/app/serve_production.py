"""Deliberate production entry point; binds only the local reverse-proxy interface."""
import os
from pydantic import ValidationError
from app.config import get_settings


def preflight():
    if os.environ.get('AGAPAY_ENVIRONMENT')!='production':
        raise RuntimeError('Set AGAPAY_ENVIRONMENT=production explicitly in the deployment service environment')
    try:settings=get_settings()
    except ValidationError:
        raise RuntimeError('Production configuration is incomplete. Review the identity production template; secret values are not printed.') from None
    if settings.environment!='production':raise RuntimeError('Production service environment mismatch')
    if settings.api_tls_proxy_peer not in ('127.0.0.1','::1'):
        raise RuntimeError('Explicitly configure the same-host HTTPS proxy peer before production serving')
    from sqlalchemy.engine import make_url
    database = make_url(settings.database_url)
    if database.drivername != 'postgresql+psycopg' or database.query.get('sslmode') != 'verify-full' or not database.query.get('sslrootcert'):
        raise RuntimeError('Production serving requires managed PostgreSQL with psycopg, sslmode=verify-full and an explicit trust anchor')
    from app.database import engine
    from app.migrations import require_current
    require_current(engine)
    from app.migrate_identity_security import require_schema
    from app.migrate_telemetry_ordering import require_ordering_schema
    from app.migrate_interval_configuration import needs_upgrade
    from sqlalchemy import inspect
    require_schema(engine)
    from app.migrate_sos_response import require_schema as require_sos_schema
    require_sos_schema(engine)
    from app.migrate_response_resources import require_schema as require_resource_schema
    require_resource_schema(engine)
    if not inspect(engine).has_table('users'):
        raise RuntimeError('Initialize the reviewed schema and bootstrap the first administrator offline before serving production')
    from app.database import SessionLocal
    from app.models import User
    from sqlalchemy import select
    from app.services.privacy_governance import approved_record, require_released
    approved_record(settings.service_governance_path)
    with SessionLocal() as db:
        require_released(db)
        if db.scalar(select(User.id).where(User.role=='admin', User.is_active.is_(True)).limit(1)) is None:
            raise RuntimeError('An active administrator is required; use the reviewed offline bootstrap or recovery procedure before serving production')
    if inspect(engine).has_table('telemetry'):
        require_ordering_schema(engine)
        if needs_upgrade(engine):raise RuntimeError('Apply the reviewed installation/interval schema migration before production startup')
    return settings


if __name__=='__main__':
    settings=preflight()
    if settings.mqtt_enabled and not settings.mqtt_external_subscriber:
        raise SystemExit('Use external MQTT subscriber mode in HTTP; run one dedicated ingestion worker')
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=8000,workers=2,proxy_headers=True,
                forwarded_allow_ips=settings.api_tls_proxy_peer)
