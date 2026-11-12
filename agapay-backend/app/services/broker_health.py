"""Local subscriber observation only; never infer broker health from HTTP data."""
from threading import Lock
from app.models import utc_now

_lock = Lock()
_state = {"state": "unknown", "observed_at": None}
_subscription='unconfirmed'


def observe_subscription(state):
    global _subscription
    with _lock:_subscription=state


def subscription_snapshot(settings,*,now=None):
    if settings.mqtt_external_subscriber:
        return snapshot(True,shared_path=settings.mqtt_status_path,now=now).get('subscription','unconfirmed')
    with _lock:return _subscription


def observe(state):
    with _lock:
        _state.update(state=state, observed_at=utc_now())


def publish_shared(path, state):
    """Single worker heartbeat. Contains no credentials; atomic file replacement."""
    import json
    from pathlib import Path
    import os
    target=Path(path)
    temporary=target.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8') as output:
        with _lock:subscription=_subscription
        json.dump({'state':state,'observed_at':utc_now().isoformat(),'subscription':subscription},output)
        output.flush();os.fsync(output.fileno())
    os.replace(temporary,target)


def snapshot(enabled, *, shared_path="", now=None):
    if enabled and shared_path:
        import json
        from pathlib import Path
        from datetime import datetime
        from app.services.station_security import utc
        result=dict(state='unknown',observed_at=None,scope='dedicated ingestion worker heartbeat')
        try:
            with Path(shared_path).open(encoding='utf-8') as source:
                value=json.loads(source.read(4097))
            at=utc(datetime.fromisoformat(value['observed_at']))
            if value['state'] in ('connected','disconnected') and 0<=(utc(now or utc_now())-at).total_seconds()<=15:
                result.update(state=value['state'],observed_at=at,subscription=value.get('subscription','unconfirmed'))
        except (OSError,ValueError,TypeError,KeyError):pass
        return result
    with _lock:
        return {**_state, "state": _state["state"] if enabled else "disabled", "scope": "subscriber in this API process"}
