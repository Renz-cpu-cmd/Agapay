"""DEVELOPMENT-ONLY supervised runner for isolated EXERCISE_TEST notifications.

Never part of the production worker service (app/worker_service.py). Importing this
module does nothing. It refuses to start in production or when exercises are disabled.

Modes
  dry-run (default)  read-only report of armed stations and pending deliveries; no writes
  fake               scan sensor triggers and process deliveries with the fake provider
                     (deliveries become TESTED; nothing leaves this machine)
  fcm                real Firebase delivery. Requires BOTH AGAPAY_EXERCISE_NOTIFICATIONS_ENABLED
                     and AGAPAY_EXERCISE_REAL_DELIVERY_ENABLED, a configured FCM provider, and
                     the explicit --mode fcm flag. Every send is still revalidated by the
                     exercise service and by the provider's EXERCISE_TEST gate.

Each tick: (1) scan_sensor_triggers, (2) manual deliveries, (3) sensor deliveries, all in
bounded batches. Two runners are safe: arms are row-locked, triggers/deliveries are unique,
and deliveries are claimed atomically with exactly one attempt.

  python -m app.exercise_runner                      # dry run, one report
  python -m app.exercise_runner --mode fake --once   # one fake-provider tick
  python -m app.exercise_runner --mode fake          # loop until Ctrl+C / SIGTERM
"""
import argparse
import logging
import signal
from threading import Event

log = logging.getLogger("agapay.exercise_runner")
MODES = ("dry-run", "fake", "fcm")


class RunnerRefused(RuntimeError):
    pass


def preflight(mode, settings=None):
    from app.config import get_settings
    from app.services.exercise_notifications import availability_problem
    settings = settings or get_settings()
    if mode not in MODES:
        raise RunnerRefused("unknown mode")
    problem = availability_problem(settings)
    if problem:
        raise RunnerRefused(problem)
    if mode == "fcm":
        if not settings.exercise_real_delivery_enabled:
            raise RunnerRefused("real exercise delivery is not enabled (AGAPAY_EXERCISE_REAL_DELIVERY_ENABLED)")
        if settings.notification_provider != "fcm":
            raise RunnerRefused("notification provider is not configured for FCM")
    return settings


def provider_for(mode, settings):
    from app.services.notification_provider import FakeNotificationProvider, configured_provider
    if mode == "fake":
        return FakeNotificationProvider()
    if mode == "fcm":
        return configured_provider(settings)
    return None


def report(session_factory=None):
    """Read-only dry-run summary."""
    from sqlalchemy import func, select
    from app.exercise_models import ExerciseDelivery, ExerciseSensorDelivery, ExerciseStationArm
    if session_factory is None:
        from app.database import SessionLocal as session_factory
    with session_factory() as db:
        count = lambda model, *where: db.scalar(select(func.count()).select_from(model).where(*where))
        return {"armed_stations": count(ExerciseStationArm, ExerciseStationArm.disarmed_at.is_(None)),
                "pending_manual": count(ExerciseDelivery, ExerciseDelivery.state == "PENDING"),
                "pending_sensor": count(ExerciseSensorDelivery, ExerciseSensorDelivery.state == "PENDING")}


def tick(provider, *, batch=10, session_factory=None):
    from app.services.exercise_notifications import process_pending, process_sensor_pending, scan_sensor_triggers
    return {"triggers": scan_sensor_triggers(session_factory=session_factory),
            "manual": process_pending(provider, limit=batch, session_factory=session_factory),
            "sensor": process_sensor_pending(provider, limit=batch, session_factory=session_factory)}


def run(mode="dry-run", *, once=False, interval=5.0, batch=10, stop=None, provider=None, session_factory=None):
    settings = preflight(mode)
    if mode == "dry-run":
        summary = report(session_factory)
        log.info("exercise dry run: %s", summary)
        return [summary]
    provider = provider or provider_for(mode, settings)
    stop = stop or Event()
    results = []
    from app.services import observability as obs
    while not stop.is_set():
        try:
            preflight(mode)  # re-check every tick: a disabled feature stops further work
            outcome = tick(provider, batch=batch, session_factory=session_factory)
            results.append(outcome)
            log.info("exercise runner tick: %s", outcome)
            obs.event("exercise_runner.tick", state="processed")
        except RunnerRefused as error:
            log.warning("exercise runner stopped: %s", error)
            break
        except Exception:
            # Never log exception text: it can contain tokens or credential paths.
            log.error("exercise runner tick failed")
            obs.event("exercise_runner.tick", state="failed")
        if once:
            break
        stop.wait(interval)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=MODES, default="dry-run")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--batch", type=int, default=10, choices=range(1, 51), metavar="1-50")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    stop = Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    try:
        results = run(args.mode, once=args.once, interval=args.interval, batch=args.batch, stop=stop)
    except RunnerRefused as error:
        raise SystemExit(f"Exercise runner refused: {error}")
    print(results[-1] if results else {})


if __name__ == "__main__":
    main()
