"""Synthetic, in-memory shared-ingress probe. No HTTP/provider/device calls."""
import os
import sys
import json
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'agapay-backend'))
os.environ['AGAPAY_DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['AGAPAY_ENVIRONMENT'] = 'development'
os.environ['AGAPAY_MQTT_ENABLED'] = 'false'
os.environ['AGAPAY_OBSERVABILITY_ENABLED'] = 'false'
os.environ['AGAPAY_READ_MODEL_CACHE_ENABLED'] = 'false'

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.main import app  # Load the complete ORM model registry; do not start it.
from app.database import engine
from app.migrations import upgrade
from app.models import (User, Station, StationIdentity, StationCredential,
                        StationSourceRegistry, Alert, NotificationEvent, NotificationDelivery, utc_now)
from app.device_config import ConfigurationRequest, save_configuration
from app.services.station_security import digest, prepare_ingress
from app.services.telemetry_service import ingest_telemetry
from app.schemas import TelemetryCreate
from app.config import get_settings

assert engine.url.database == ':memory:'
upgrade(engine)
with Session(engine) as db:
    admin = User(name='Synthetic reviewer', email='review@example.invalid',
                 password_hash='not-a-login', role='admin')
    station = Station(station_id='REVIEW_PROBE', station_name='Synthetic probe',
                      latitude=15.9, longitude=120.5, status='active')
    db.add_all([admin, station]); db.flush()
    db.add(StationIdentity(station_id=station.station_id, device_id='SYNTHETIC_DEVICE',
                          state='commissioned', coordinates_verified=True,
                          reference_datum='Synthetic datum', calibration_note='Synthetic fixture only',
                          version=1, commissioned_at=utc_now()))
    db.flush()
    db.add(StationSourceRegistry(station_id=station.station_id, config_version=1,
                                device_id='SYNTHETIC_DEVICE', source_class='physical_device',
                                stream='operational', evidence='Synthetic registry fixture', reviewed_by=admin.id))
    token = 'agi_' + 'x' * 43
    credential = StationCredential(station_id=station.station_id, identity_version=1,
                                   token_hash=digest(token), label='Synthetic fixture',
                                   transport='both', expires_at=utc_now() + timedelta(hours=1))
    db.add(credential); db.flush()
    config = save_configuration(db, station, ConfigurationRequest(
        expected_revision=0, validation_status='prototype',
        installation=dict(datum='Synthetic datum', installation_height_cm=150,
                          sensor_min_cm=20, sensor_max_cm=450, uncertainty_cm=2,
                          range_margin_cm=5, advisory_cm=60, warning_cm=85,
                          critical_cm=100, rain_mm_per_tip=.7),
        evidence='Synthetic software fixture; no field approval',
        reason='Read-only audit reproduction on disposable memory database', effective_at=utc_now()), admin)
    db.commit()
    authenticated = prepare_ingress(db, token, station.station_id, 'http', 'telemetry', get_settings())
    row = ingest_telemetry(db, TelemetryCreate(
        station_id=station.station_id, schema_version=3, config_version=1,
        source_id='SYNTHETIC_DEVICE', boot_id='SYNTHETIC_BOOT', boot_sequence=1,
        sequence_no=1, device_uptime_ms=1000, measured_at=utc_now(),
        water_depth_cm=105, sensor_quality='valid', firmware_version='0.4.0-synthetic-audit',
        applied_config_hash=config.config_hash), credential_id=authenticated.id, transport='http')
    episode = db.scalar(select(Alert).where(Alert.station_id == station.station_id))
    result = dict(scope='Shared authentication/ingestion services, development settings, in-memory database; not a full production deployment test',
                  validation_status=config.validation_status, disposition=row.disposition,
                  eligible_for_current=row.eligible_for_current,
                  episode_tier=episode.current_severity if episode else None,
                  notification_events=db.scalar(select(func.count()).select_from(NotificationEvent)),
                  notification_deliveries=db.scalar(select(func.count()).select_from(NotificationDelivery)),
                  external_messages_sent=0)
    assert result['validation_status'] == 'prototype'
    assert result['eligible_for_current'] and result['episode_tier'] == 'EVACUATE'
    assert result['notification_events'] == 1 and result['notification_deliveries'] == 0
    Path(__file__).with_name('configuration-review-probe.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
engine.dispose()
