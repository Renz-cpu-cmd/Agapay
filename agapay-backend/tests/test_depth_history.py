"""F28: durable retries are historical across transports, ACKs follow commit."""
import json
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Telemetry
from test_alerts import payload
from test_accounts import reset_accounts
from test_station_security import device, mqtt_transport, token_headers
from test_telemetry_ordering import snapshot, send


def message(device, reading, **changes):
    return SimpleNamespace(topic=f'agapay/stations/{device[0]}/telemetry', retain=False,
        payload=json.dumps(dict(ingest_token=device[2]['ingest_token'],telemetry=reading,
                               delivery_mode='backfill',**changes)).encode())


def test_recent_backfill_never_creates_live_status_alert_or_outbox(client, device):
    before=snapshot(device[0])
    data=payload(device[0],100,105)
    response=client.post('/api/telemetry?delivery_mode=backfill',headers=token_headers(device[2]),json=data)
    assert response.status_code==201 and response.json()['disposition']=='journal_backfill'
    assert response.json()['eligible_for_current'] is False
    assert snapshot(device[0])==before
    # An exact lost-response retry succeeds, while reusing the key with new depth conflicts.
    assert client.post('/api/telemetry?delivery_mode=backfill',headers=token_headers(device[2]),json=data).status_code==201
    assert client.post('/api/telemetry?delivery_mode=backfill',headers=token_headers(device[2]),json={**data,'water_depth_cm':1}).status_code==409
    assert client.post('/api/telemetry?delivery_mode=backfill',json=payload(device[0],101,105)).status_code==401
    assert snapshot(device[0])==before


def test_mqtt_commit_exact_retry_and_conflict_acknowledgments(client, device, mqtt_transport, monkeypatch):
    sub=mqtt_transport[0];acks=[]
    def published(topic, body, **kwargs):
        # Query using an independent transaction: ACK must follow a committed row.
        decoded=json.loads(body)
        with SessionLocal() as db:
            row=db.scalar(select(Telemetry).where(Telemetry.station_id==device[0],Telemetry.sequence_no==decoded['sequence_no']))
            assert row is not None and row.disposition=='journal_backfill'
        acks.append((topic,decoded,kwargs))
    monkeypatch.setattr(sub,'publish',published)
    data=payload(device[0],100,105);before=snapshot(device[0])
    sub.on_message(sub,None,message(device,data))
    sub.on_message(sub,None,message(device,data))
    assert len(acks)==2 and acks[0]==acks[1]
    assert acks[0][0].endswith('/telemetry-ack') and acks[0][1]['persisted'] is True
    assert acks[0][1]['telemetry']==data
    assert acks[0][2]==dict(qos=1,retain=False)
    sub.on_message(sub,None,message(device,{**data,'water_depth_cm':1}))
    assert len(acks)==2 and snapshot(device[0])==before
    assert send(client,device,payload(device[0],101,105)).json()['eligible_for_current'] is True


def test_reboot_and_delayed_replay_cannot_change_an_active_incident(client, device, mqtt_transport, monkeypatch):
    mqtt_transport=mqtt_transport[0]
    acks=[];monkeypatch.setattr(mqtt_transport,'publish',lambda *a,**k:acks.append(a))
    current=payload(device[0],101,105)
    current.update(boot_id='new-boot-002',boot_sequence=2)
    assert send(client,device,current).status_code==201
    before=snapshot(device[0]);old=payload(device[0],100,1)
    mqtt_transport.on_message(mqtt_transport,None,message(device,old))
    assert len(acks)==1 and snapshot(device[0])==before
    retained=message(device,payload(device[0],102,105));retained.retain=True
    mqtt_transport.on_message(mqtt_transport,None,retained)
    assert len(acks)==1


def test_failed_persistence_never_acknowledges(client, device, mqtt_transport, monkeypatch):
    import app.services.mqtt_subscriber as module
    mqtt_transport=mqtt_transport[0]
    acks=[];monkeypatch.setattr(mqtt_transport,'publish',lambda *a,**k:acks.append(a))
    def fail(*a,**k):raise OSError('Synthetic disk failure')
    monkeypatch.setattr(module,'ingest_telemetry',fail)
    mqtt_transport.on_message(mqtt_transport,None,message(device,payload(device[0],100,105)))
    assert acks==[]
