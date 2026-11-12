"""F05/F06 acceptance: authority-owned source and independent channel clocks."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, inspect, select

from app.database import Base, SessionLocal
from app.models import (Alert, ExerciseTelemetry, NotificationEvent, Station, StationSourceRegistry,
                        Telemetry, TelemetryProvenance, utc_now)
from app.schemas import TelemetryCreate
from app.services import telemetry_service
from app.services.monitoring_service import monitoring_snapshot
from app.ml.hybrid_demo.hydrology import sensor_initial
from app.migrate_station_provenance import migrate
from test_accounts import reset_accounts, staff
from test_alerts import payload
from test_station_security import (device, mqtt_transport, token_headers, commissioning, provision, business_counts)


@pytest.fixture
def simulation(client):
    admin = staff(client)
    body, response = provision(client, admin, commissioning=commissioning(source_class="simulator", stream="exercise"))
    assert response.status_code == 201
    station = body["station_id"]
    credential = client.post(f"/api/stations/{station}/credentials", headers=admin,
        json={"expected_version": 1, "label": "Exercise", "reason": "Synthetic simulation test"})
    assert credential.status_code == 201
    return station, admin, credential.json()


def post(client, identity, reading, *, exercise=False):
    return client.post("/api/exercises/telemetry" if exercise else "/api/telemetry",
                       headers=token_headers(identity[2]), json=reading)


def monitored(station, now=None, limit=2):
    with SessionLocal() as db:
        return next(s for s in monitoring_snapshot(db, stale_after_seconds=30, history_limit=limit, now=now, station_ids=[station]).stations
                    if s.station_id == station)


@pytest.mark.parametrize("firmware", ["1.0.0", "1.0.0-simulator", "9.9.9-physical"])
def test_http_simulator_cannot_claim_physical_or_operational_origin(client, simulation, firmware):
    station, _, _ = simulation
    reading = {**payload(station, 1, 105), "firmware_version": firmware}
    before = business_counts()
    assert post(client, simulation, reading).status_code == 403
    stored = post(client, simulation, reading, exercise=True)
    assert stored.status_code == 201 and business_counts() == before
    data = stored.json()
    assert data["source_class"] == "simulator" and data["stream"] == "exercise" and not data["source_trusted"]
    assert data["ingress_identity"] == reading["source_id"] and data["ingress_transport"] == "http"
    assert post(client, simulation, reading, exercise=True).status_code == 409
    assert post(client, simulation, {**reading,"water_depth_cm":1},exercise=True).status_code == 409
    assert client.get(f"/api/telemetry/{station}/latest").status_code == 404
    assert client.get(f"/api/exercises/telemetry/{station}/latest").json() == data
    assert monitored(station).source == "none" and not monitored(station).is_online
    with SessionLocal() as db:
        row = db.scalar(select(ExerciseTelemetry).where(ExerciseTelemetry.station_id == station))
        assert row.credential_id == simulation[2]["id"]
        assert db.scalar(select(Station).where(Station.station_id == station)).last_ping is None


def test_payload_cannot_assign_its_own_source_class_or_ingress_identity(client, simulation):
    for field, value in (("source_class","physical_device"),("source_trusted",True),("stream","operational"),("credential_id",simulation[2]["id"])):
        assert post(client, simulation, {**payload(simulation[0],1,105),field:value},exercise=True).status_code == 422


def test_registry_phys_source_is_independent_of_firmware_and_persists_authenticated_context(client, device):
    station = device[0]
    response = post(client, device, {**payload(station,1,105),"firmware_version":"1.0.0-simulator"})
    assert response.status_code == 201
    data = response.json()
    assert data["source_class"] == "physical_device" and data["source_trusted"]
    monitor = monitored(station)
    assert monitor.source == "device" and monitor.source_trusted and monitor.depth_source_trusted
    assert "simulator" in monitor.firmware_version
    with SessionLocal() as db:
        provenance = db.get(TelemetryProvenance,data["id"])
        assert provenance.credential_id == device[2]["id"] and provenance.ingress_transport == "http"
        assert provenance.ingress_identity == data["ingress_identity"]
        station_row = db.scalar(select(Station).where(Station.station_id == station))
        assert telemetry_service.utc(station_row.last_ping) == datetime.fromisoformat(data["received_at"].replace("Z","+00:00"))
        assert station_row.last_ping != db.get(Telemetry,data["id"]).measured_at


def test_old_rows_without_provenance_are_unverified_and_cannot_initialize_a_model(client, device):
    station=device[0]
    assert post(client,device,payload(station,1,105)).status_code == 201
    with SessionLocal() as db:
        db.query(TelemetryProvenance).delete()
        db.commit()
    data=monitored(station).model_dump(mode="json")
    assert data["source_class"] == "unverified" and data["source"] == "unverified"
    with pytest.raises(ValueError):sensor_initial(data,utc_now())


def test_missing_registry_fails_closed_without_automatically_promoting_existing_identity(client, device):
    with SessionLocal() as db:
        db.query(StationSourceRegistry).filter_by(station_id=device[0]).delete()
        db.commit()
    before=business_counts()
    assert post(client,device,payload(device[0],1,105)).status_code == 403
    assert business_counts() == before


def test_no_authentication_context_cannot_be_invented_inside_domain_ingestion(client, device):
    from fastapi import HTTPException
    with SessionLocal() as db, pytest.raises(HTTPException):
        telemetry_service.ingest_telemetry(db,TelemetryCreate(**payload(device[0],1,105)))


def test_recommission_creates_audited_source_version_and_invalidates_old_trust(client, device):
    station,admin,_=device
    assert post(client,device,payload(station,1,105)).status_code == 201
    assert monitored(station).depth_source_trusted
    new=commissioning(source_class="simulator",stream="exercise")
    updated=client.post(f"/api/stations/{station}/commission",headers=admin,json={**new,"expected_version":1})
    assert updated.status_code == 200 and updated.json()["source_class"] == "simulator"
    assert not monitored(station).depth_source_trusted
    with pytest.raises(ValueError):sensor_initial(monitored(station).model_dump(mode="json"),utc_now())
    audits=client.get(f"/api/stations/{station}/audit",headers=admin).json()
    assert audits[0]["details"]["after"]["source_class"] == "simulator"


def test_mqtt_exercise_and_operational_namespaces_cannot_be_interchanged(client, device, mqtt_transport):
    station,admin,_=device
    config=commissioning(source_class="simulator",stream="exercise")
    assert client.post(f"/api/stations/{station}/commission",headers=admin,json={**config,"expected_version":1}).status_code == 200
    issued=client.post(f"/api/stations/{station}/credentials",headers=admin,json={"expected_version":2,"label":"Exercise","reason":"Controlled test"}).json()
    sub=mqtt_transport[0]
    envelope=json.dumps({"ingest_token":issued["ingest_token"],"telemetry":payload(station,1,105)}).encode()
    before=business_counts()
    for topic in (f"agapay/stations/{station}/telemetry",f"agapay/exercises/stations/{station}/telemetry"):
        sub.on_message(sub,None,SimpleNamespace(topic=topic,payload=envelope,retain=False))
    assert business_counts() == before
    with SessionLocal() as db:
        row=db.scalar(select(ExerciseTelemetry).where(ExerciseTelemetry.station_id == station))
        assert row.ingress_transport == "mqtt" and row.source_class == "simulator"


@pytest.mark.parametrize("age", [5,3600])
def test_invalid_heartbeats_do_not_refresh_retained_depth_or_evict_it_from_short_chart(client, device, monkeypatch, age):
    station=device[0]
    now=utc_now()
    measured=now-timedelta(seconds=age)
    class Clock(datetime):
        current=measured
        @classmethod
        def now(cls,tz=None):return cls.current
    monkeypatch.setattr(telemetry_service,"datetime",Clock)
    assert post(client,device,{**payload(station,1,105),"measured_at":measured.isoformat()}).status_code == 201
    Clock.current=now
    for sequence in range(2,8):
        # Strictly ordered acquisition times ending now, all with invalid water.
        sampled=now-timedelta(milliseconds=8-sequence)
        assert post(client,device,{**payload(station,sequence,None),"measured_at":sampled.isoformat()}).status_code == 201
    small,large=monitored(station,now,2),monitored(station,now,100)
    assert small.current_depth_cm == large.current_depth_cm == 105
    assert small.last_valid_depth_at == large.last_valid_depth_at == measured
    assert small.observed_at == measured and small.age_seconds == small.depth_age_seconds == age
    assert small.heartbeat_age_seconds == 0 and small.is_online and small.connection_status == "online"
    assert small.latest_sample_at != small.last_valid_depth_at and small.sensor_quality == "invalid"
    assert not small.depth_fresh and small.depth_status == ("stale" if age==3600 else "retained")
    assert not small.rainfall_fresh and small.hazard_state == "unresolved" and small.active_hazard_tier == "EVACUATE"
    assert all(r.water_depth_cm is None for r in small.history)
    with pytest.raises(ValueError):sensor_initial(small.model_dump(mode="json"),now)


@pytest.mark.parametrize("change", [{"source_class":"simulator"},{"source_trusted":False},{"depth_source_trusted":False},
                                   {"stream":"exercise"},{"depth_fresh":False},{"last_valid_depth_at":"2000-01-01T00:00:00Z"}])
def test_hybrid_rejects_untrusted_exercise_or_stale_initialization(client, device, change):
    assert post(client,device,payload(device[0],1,105)).status_code == 201
    data=monitored(device[0]).model_dump(mode="json")
    assert sensor_initial(data,utc_now()) == 105
    with pytest.raises(ValueError):sensor_initial({**data,**change},utc_now())


def test_additive_provenance_migration_never_backfills_trust_or_changes_readings(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'provenance.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO stations (station_id,station_name,sensor_height_cm,threshold_advisory_cm,threshold_warning_cm,threshold_evacuate_cm,status,created_at) VALUES ('OLD_STATION','Old',120,60,85,100,'active',CURRENT_TIMESTAMP)")
        connection.exec_driver_sql("INSERT INTO telemetry (id,station_id,sequence_no,water_depth_cm,rainfall_mm,sensor_quality,device_uptime_ms,recorded_at,received_at) VALUES (42,'OLD_STATION',1,105,0,'valid',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
        for table in (ExerciseTelemetry.__table__,TelemetryProvenance.__table__,StationSourceRegistry.__table__):table.drop(connection)
    assert len(migrate(engine)) == 3
    assert not inspect(engine).has_table('station_source_registry')
    assert len(migrate(engine,apply=True)) == 3 and migrate(engine,apply=True) == []
    with engine.connect() as connection:
        assert connection.exec_driver_sql('SELECT id,water_depth_cm FROM telemetry').one() == (42,105)
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM station_source_registry').scalar() == 0
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM telemetry_provenance').scalar() == 0
    engine.dispose()
