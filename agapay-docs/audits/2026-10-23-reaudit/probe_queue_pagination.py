"""Reproduce the provenance test's first-page assumption in an isolated DB."""
import os
import sys
import json
from pathlib import Path
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'agapay-backend'))
os.environ.update(AGAPAY_DATABASE_URL='sqlite:///:memory:', AGAPAY_ENVIRONMENT='development',
                  AGAPAY_MQTT_ENABLED='false', AGAPAY_OBSERVABILITY_ENABLED='false',
                  AGAPAY_READ_MODEL_CACHE_ENABLED='false')
from app.main import app
from app.database import engine
from app.migrations import upgrade
from app.models import Station, Telemetry, Alert, User, utc_now
from app.routers.staff_workspaces import command_queue
from sqlalchemy.orm import Session

assert engine.url.database == ':memory:'
upgrade(engine)
with Session(engine) as db:
    admin = User(name='Synthetic reviewer', email='review@example.invalid', password_hash='not-a-login', role='admin')
    db.add(admin)
    target = None
    for i in range(21):
        sid = f'PAGINATION_PROBE_{i:02}'
        at = utc_now() - timedelta(hours=2, seconds=21-i)
        db.add(Station(station_id=sid, station_name='Synthetic queue record'))
        db.flush()
        sample = Telemetry(station_id=sid, sequence_no=1, water_depth_cm=61 if i==20 else 105,
                           sensor_quality='valid', device_uptime_ms=1000, recorded_at=at)
        db.add(sample); db.flush()
        severity = 'ADVISORY' if i==20 else 'EVACUATE'
        episode = Alert(station_id=sid, current_severity=severity, highest_severity=severity,
                        status='ACTIVE', trigger_telemetry_id=sample.id, latest_telemetry_id=sample.id,
                        trigger_sequence_no=1, latest_sequence_no=1, trigger_depth_cm=sample.water_depth_cm,
                        latest_depth_cm=sample.water_depth_cm, triggered_at=at, last_transition_at=at)
        db.add(episode); db.flush()
        if i==20: target=episode.id
    db.commit()
    first = command_queue(scope='unverified', limit=20, offset=0, db=db, user=admin)
    second = command_queue(scope='unverified', limit=20, offset=20, db=db, user=admin)
    result = dict(scope='Direct actual queue function with synthetic in-memory rows; no network calls',
                  total=first['total'], first_page_count=len(first['items']),
                  first_page_has_more=first['has_more'],
                  target_on_first_page=target in [row['id'] for row in first['items']],
                  target_on_second_page=target in [row['id'] for row in second['items']])
    assert result['total']==21 and not result['target_on_first_page'] and result['target_on_second_page']
    Path(__file__).with_name('queue-pagination-probe.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))
engine.dispose()
