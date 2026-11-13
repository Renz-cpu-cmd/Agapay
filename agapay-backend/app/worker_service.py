"""Production bounded workers. Delivery services require explicit deployment opt-in."""
import argparse
import signal
from threading import Event
from app.serve_production import preflight


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['notifications', 'identity-mail', 'sos-drills','read-model','diagnostics','forecasts'])
    kind = parser.parse_args().kind
    from app.process_pool import background_defaults
    background_defaults()  # One tick at a time: small per-process pool unless explicitly configured.
    settings = preflight()
    if kind == 'notifications':
        from app.services.notification_provider import configured_provider
        from app.services.notification_service import process_pending
        provider = configured_provider(settings)
        if provider.mode == 'disabled':
            raise SystemExit('Configure a delivery provider explicitly before enabling this worker')
        tick = lambda: process_pending(provider, limit=50)
    elif kind == 'identity-mail':
        from app.identity_mail_worker import process_pending
        tick = lambda: process_pending(limit=20)
    elif kind=='sos-drills':
        from app.database import SessionLocal
        from app.services.sos_response import process_due
        tick = lambda: process_due(SessionLocal, limit=50)
    elif kind=='forecasts':
        from app.services.forecast_registry import tick
    elif kind=='read-model':
        from app.database import SessionLocal
        from app.services.read_models import snapshot
        def tick():
            with SessionLocal() as db:snapshot(db,settings,history_limit=120,refresh_before_seconds=settings.read_model_seconds/2)
    else:
        from app.database import SessionLocal
        from app.services.operations_health import diagnostics,reconcile
        def tick():
            with SessionLocal() as db:reconcile(db,diagnostics(db,settings,write_probe=True))
    stop = Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    from app.services import observability as obs
    from app.services.delivery_recovery import DeliveryFenced
    import logging
    try:
        while not stop.is_set():
            try:
                tick();obs.heartbeat(kind)
            except DeliveryFenced as fenced:
                # R2 P0: fail closed and say why; the message carries no secrets.
                logging.getLogger('agapay.worker').warning('%s worker fenced: %s', kind, fenced)
                obs.heartbeat(kind,'failed','delivery_fenced')
                obs.event('worker.fenced',role=kind,state='failed')
            except Exception:
                obs.heartbeat(kind,'failed','tick_failed')
                obs.event('worker.failed',role=kind,state='failed')
            obs.flush(force=True)
            stop.wait(settings.read_model_seconds/2 if kind=='read-model' else 10)
    finally:
        obs.heartbeat(kind,'stopped');obs.flush(force=True)


if __name__ == '__main__':
    main()
