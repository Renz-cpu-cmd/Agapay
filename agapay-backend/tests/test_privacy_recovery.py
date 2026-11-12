"""Encrypted synthetic restore drills; no live data, transport or key material."""
import json
import os
import sqlite3
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from app.migrations import upgrade, require_current
from app.models import (User, Station, Telemetry, Alert, AlertTransition, NotificationEvent,
    NotificationDevice, NotificationDelivery, AuthSession, SosRequest, utc_now)
from app.identity_models import IdentityAction, IdentityMail
from app.privacy_models import RecoveryFence
from app.recovery import backup, restore, file_hash
from app.services.privacy_governance import require_released


def fixture_source(path):
    bind=create_engine('sqlite:///'+path.as_posix());upgrade(bind);now=utc_now()
    with Session(bind) as db:
        user=User(name='SYNTHETIC PRIVATE PERSON',email='private@example.invalid',password_hash='SYNTHETIC-NOT-A-HASH',phone='+639123456789',barangay='TEST AREA')
        db.add(user);db.flush();db.add(Station(station_id='RESTORE',station_name='Restore fixture'));db.flush()
        sample=Telemetry(station_id='RESTORE',sequence_no=1,sensor_quality='valid',device_uptime_ms=10,water_depth_cm=105)
        db.add(sample);db.flush()
        alert=Alert(station_id='RESTORE',current_severity='EVACUATE',highest_severity='EVACUATE',trigger_telemetry_id=sample.id,
            latest_telemetry_id=sample.id,trigger_sequence_no=1,latest_sequence_no=1,trigger_depth_cm=105,latest_depth_cm=105,triggered_at=now,last_transition_at=now)
        db.add(alert);db.flush()
        change=AlertTransition(alert_id=alert.id,station_id='RESTORE',telemetry_id=sample.id,sequence_no=1,previous_severity='NORMAL',new_severity='EVACUATE',water_depth_cm=105,transitioned_at=now)
        db.add(change);db.flush();event=NotificationEvent(transition_id=change.id);db.add(event);db.flush()
        for i,state in enumerate(('PENDING','PROCESSING','UNKNOWN','SENT','FAILED')):
            device=NotificationDevice(user_id=user.id,installation_id=str(uuid4()),platform='android',provider_token='SYNTHETIC-TOKEN-'+str(i),token_hash=str(i)*64,session_hash='a'*64)
            db.add(device);db.flush();db.add(NotificationDelivery(event_id=event.id,device_id=device.id,user_id=user.id,device_revision=1,state=state))
        db.add(AuthSession(user_id=user.id,token_hash='a'*64,expires_at=now+timedelta(days=1)))
        action=IdentityAction(token_hash='b'*64,purpose='password_reset',user_id=user.id,account_version=1,expires_at=now+timedelta(hours=1),payload={})
        db.add(action);db.flush()
        db.add(IdentityMail(action_hash='b'*64,recipient=user.email,body_ciphertext='SYNTHETIC-CIPHERTEXT',state='PENDING',expires_at=now+timedelta(hours=1)))
        db.add(SosRequest(user_id=user.id,request_id=str(uuid4()),payload_hash='c'*64,resident_name=user.name,phone=user.phone,
            barangay=user.barangay,location='SYNTHETIC PRIVATE ADDRESS',latitude=15.9,longitude=120.5,location_source='gps'))
        db.commit()
    bind.dispose()


def test_encrypted_snapshot_restore_preserves_history_and_stops_all_delivery_replay(tmp_path):
    source=tmp_path/'source.db';fixture_source(source);before=file_hash(source)
    rain=tmp_path/'rain.db'
    with sqlite3.connect(rain) as db:db.execute('CREATE TABLE ack_fixture (sequence INTEGER, cumulative INTEGER)');db.execute('INSERT INTO ack_fixture VALUES (42,105)')
    key=os.urandom(32);archive=tmp_path/'private.agapaybak'
    record=backup(archive,key,source=source,rain=rain,writers_stopped=True)
    assert b'SYNTHETIC PRIVATE' not in archive.read_bytes() and b'SQLite format' not in archive.read_bytes()
    assert file_hash(source)==before
    result=restore(archive,tmp_path/'restored',key)
    assert result['status']=='verified_and_quarantined'
    # R2 P0: restored deliveries keep their state; uncertain ones are held, not rewritten.
    assert result['deliveries_held_unsent']==2 and result['deliveries_held_uncertain']==2 and result['delivery_generation']==1
    assert result['actual_data_loss_seconds'] is None # Requires independent source/checkpoint evidence.
    assert result['restore_seconds']<14400 and result['package_age_seconds']<900 # Tiny drill, not deployment RPO/RTO proof.
    bind=create_engine('sqlite:///'+(tmp_path/'restored/database.sqlite3').as_posix());require_current(bind)
    with Session(bind) as db:
        assert db.scalar(select(Alert)).current_severity=='EVACUATE'
        assert db.scalar(select(SosRequest)).location=='SYNTHETIC PRIVATE ADDRESS'
        assert db.scalar(select(AuthSession)) is None
        assert all(not row.enabled and row.provider_token is None for row in db.scalars(select(NotificationDevice)))
        states=list(db.scalars(select(NotificationDelivery.state).order_by(NotificationDelivery.id)))
        assert states==['PENDING','PROCESSING','UNKNOWN','SENT','FAILED'], 'restored delivery evidence is preserved'
        from app.recovery_models import DeliveryGeneration, DeliveryHold
        held=sorted(db.scalars(select(DeliveryHold.original_state)))
        assert held==['FAILED','PENDING','PROCESSING','UNKNOWN'], 'every replay-eligible or uncertain row is held; SENT is not'
        assert [(g.state,g.kind) for g in db.scalars(select(DeliveryGeneration))]==[('RECOVERING','restore')]
        assert db.scalar(select(IdentityMail)).state=='SUPPRESSED'
        with pytest.raises(RuntimeError,match='quarantined'):require_released(db)
    with sqlite3.connect(tmp_path/'restored/rain.sqlite3') as db:assert db.execute('SELECT * FROM ack_fixture').fetchall()==[(42,105)]
    class ForbiddenProvider:
        mode='fcm'
        def send(self,*args,**kwargs):pytest.fail('Historical alert must not reach any provider')
    from app.services.notification_service import process_pending
    with pytest.raises(RuntimeError,match='quarantined'):process_pending(ForbiddenProvider(),session_factory=sessionmaker(bind))
    from app.identity_mail_worker import process_pending as mail
    with pytest.raises(RuntimeError,match='quarantined'):mail(session_factory=sessionmaker(bind),send=lambda *_:pytest.fail('No recovery mail replay'))
    bind.dispose()
    with pytest.raises(RuntimeError,match='must not exist'):restore(archive,tmp_path/'restored',key)


@pytest.mark.parametrize('mutation',['wrong_key','ciphertext','truncated'])
def test_authentication_failure_never_writes_a_restore_target(tmp_path,mutation):
    source=tmp_path/'source.db';fixture_source(source);key=os.urandom(32);archive=tmp_path/'backup.agapaybak'
    backup(archive,key,source=source,writers_stopped=True)
    if mutation=='wrong_key':key=os.urandom(32)
    else:
        data=bytearray(archive.read_bytes())
        if mutation=='ciphertext':data[len(data)//2]^=1
        else:data=data[:40]
        archive.write_bytes(data)
    with pytest.raises(RuntimeError):restore(archive,tmp_path/'untrusted',key)
    assert not (tmp_path/'untrusted').exists()


def test_backup_refuses_live_assumption_missing_source_and_existing_output(tmp_path):
    source=tmp_path/'source.db';fixture_source(source);key=os.urandom(32);output=tmp_path/'backup.agapaybak'
    with pytest.raises(RuntimeError,match='Stop all writers'):backup(output,key,source=source)
    backup(output,key,source=source,writers_stopped=True)
    with pytest.raises(RuntimeError,match='new file'):backup(output,key,source=source,writers_stopped=True)


def test_api_refuses_to_start_on_a_quarantined_restored_database(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    source=tmp_path/'source.db';fixture_source(source);key=os.urandom(32);archive=tmp_path/'backup.agapaybak'
    backup(archive,key,source=source,writers_stopped=True);restore(archive,tmp_path/'restore',key)
    bind=create_engine('sqlite:///'+(tmp_path/'restore/database.sqlite3').as_posix());monkeypatch.setattr(main,'engine',bind)
    with pytest.raises(RuntimeError,match='quarantined'):
        with TestClient(main.app):pass
    bind.dispose()
