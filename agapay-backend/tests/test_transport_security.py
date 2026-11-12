"""Isolated TLS/broker tests. Synthetic keys; ephemeral loopback listener only."""
from datetime import timedelta
from pathlib import Path
import socket,ssl,subprocess,threading
from uuid import uuid4
import pytest
import paho.mqtt.client as mqtt
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
from app.models import utc_now
from app.config import Settings
from app.services.transport_security import https_origin,mqtt_context
from app.broker_acl import render
from test_station_broker_acl import BROKER,PASSWD

@pytest.mark.parametrize('origin',['http://public.test','https://localhost','https://127.0.0.1','https://192.168.1.1','https://service.local','https://user:password@public.test','https://public.test/api','https://public.test?key=bad','https://public.test#part',''])
def test_production_rejects_nonpublic_or_ambiguous_api_origins(origin):
    with pytest.raises(ValueError):https_origin(origin)


def test_verified_context_has_no_insecure_fallback_and_password_repr_is_redacted(tmp_path):
    settings=Settings(_env_file=None,mqtt_password='synthetic-test-secret')
    context=mqtt_context(settings)
    assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED and context.minimum_version>=ssl.TLSVersion.TLSv1_2
    assert 'synthetic-test-secret' not in repr(settings)
    with pytest.raises(FileNotFoundError):mqtt_context(settings.model_copy(update={'mqtt_ca_file':str(tmp_path/'missing.pem')}))
    with pytest.raises(ValueError):mqtt_context(settings.model_copy(update={'mqtt_client_cert_file':'unpaired.pem'}))


def test_production_acl_has_explicit_physical_identities_only():
    result=render([dict(station_id='STATION_A',active=True,source_class='physical_device'),dict(station_id='STATION_B',active=False,source_class='physical_device')])
    assert 'user STATION_A' in result and 'user STATION_B' not in result and '%u' not in result and '/exercises/' not in result
    assert 'topic write agapay/stations/STATION_A/telemetry' in result
    with pytest.raises(ValueError):render([dict(station_id='STATION_A',active=False),dict(station_id='STATION_A',active=True,source_class='physical_device')])
    for records in [[dict(station_id='INJECT\nuser evil',active=True,source_class='physical_device')],[dict(station_id='STATION_A',active=True,source_class='simulator')]]:
        with pytest.raises(ValueError):render(records)


@pytest.mark.parametrize('changes',[{'mqtt_tls':False},{'mqtt_port':1883},{'mqtt_port':1884},{'mqtt_username':''},{'mqtt_password':''},{'mqtt_client_id':'agapay-backend-dev'},{'mqtt_client_cert_file':'unpaired.pem'},{'database_url':'sqlite:///./explicit-but-development.db'},{'database_url':'postgresql+psycopg://synthetic@db.test/agapay?sslmode=disable'},{'database_url':'postgresql+psycopg://synthetic@db.test/agapay?sslmode=verify-full'}])
def test_complete_production_configuration_rejects_mqtt_development_exceptions(changes):
    from cryptography.fernet import Fernet
    from pydantic import ValidationError
    values=dict(_env_file=None,environment='production',deployment_confirmed=True,local_admin_setup_enabled=False,
        seed_demo_data=False,prediction_preview_enabled=False,staff_mfa_required=True,
        identity_encryption_key=Fernet.generate_key().decode(),public_web_origin='https://web.agapay.test',public_api_origin='https://api.agapay.test',
        identity_mail_provider='smtp',smtp_host='smtp.test',smtp_username='synthetic',smtp_password='synthetic',smtp_sender='test@agapay.test',database_url='postgresql+psycopg://synthetic:synthetic@database.agapay.test/agapay?sslmode=verify-full&sslrootcert=/synthetic/ca.pem',
        mqtt_enabled=True,mqtt_tls=True,mqtt_host='mqtt.agapay.test',mqtt_port=8883,mqtt_client_id='backend-unique-test',mqtt_username='backend-ingest',mqtt_password='synthetic-only-secret')
    with pytest.raises(ValidationError):Settings(**{**values,**changes})


def certificates(folder):
    now=utc_now();key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'AGAPAY isolated test CA')])
    root=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=7)).not_valid_after(now+timedelta(days=7)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).sign(key,hashes.SHA256())
    (folder/'ca.pem').write_bytes(root.public_bytes(serialization.Encoding.PEM))
    server=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    (folder/'server.key').write_bytes(server.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    def issue(expired=False):
        cert=x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])).issuer_name(name).public_key(server.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=2)).not_valid_after(now-timedelta(days=1) if expired else now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(key,hashes.SHA256())
        (folder/'server.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    issue();return issue


@pytest.mark.skipif(not BROKER or not PASSWD,reason='Installed Mosquitto required for isolated TLS acceptance')
def test_real_tls_broker_rejects_certificate_topic_and_revoked_account(tmp_path):
    issue=certificates(tmp_path);secret='synthetic-only-'+uuid4().hex
    password=tmp_path/'passwords';acl=tmp_path/'physical.acl'
    acl.write_text(render([dict(station_id='STATION_A',active=True,source_class='physical_device')]),encoding='utf-8')
    for i,user in enumerate(['STATION_A','backend-ingest']):subprocess.run([PASSWD,'-b',*(['-c'] if i==0 else []),str(password),user,secret],check=True,capture_output=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    config=tmp_path/'broker.conf';config.write_text(f'listener {port} 127.0.0.1\nallow_anonymous false\npassword_file {password.as_posix()}\nacl_file {acl.as_posix()}\ncertfile {(tmp_path/"server.pem").as_posix()}\nkeyfile {(tmp_path/"server.key").as_posix()}\ntls_version tlsv1.2\nretain_available false\nmax_packet_size 8192\nmessage_size_limit 4096\npersistence false\n',encoding='utf-8')
    clients=[];process=None;log=(tmp_path/'broker.log').open('w')
    def start():
        process=subprocess.Popen([BROKER,'-c',str(config)],stdout=log,stderr=log,**({'creationflags':subprocess.CREATE_NO_WINDOW} if hasattr(subprocess,'CREATE_NO_WINDOW') else {}))
        for _ in range(100):
            if process.poll() is not None:pytest.fail('Isolated TLS broker failed; inspect test-only broker.log')
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):return process
            except OSError:threading.Event().wait(.05)
        pytest.fail('Isolated TLS broker not ready')
    def connect(user='STATION_A',password_value=None,expected=True):
        client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='tls-test-'+uuid4().hex,protocol=mqtt.MQTTv5)
        client.tls_set_context(ssl.create_default_context(cafile=str(tmp_path/'ca.pem')))
        if user:client.username_pw_set(user,secret if password_value is None else password_value)
        event=threading.Event();outcome=[]
        client.on_connect=lambda c,u,f,r,p:(outcome.append(not r.is_failure),event.set())
        client.connect('localhost',port);client.loop_start();clients.append(client)
        assert event.wait(5) and outcome==[expected]
        return client
    def stop():
        for c in clients:c.disconnect();c.loop_stop()
        clients.clear()
        process.terminate();process.wait(timeout=5)
    try:
        process=start()
        context=ssl.create_default_context(cafile=str(tmp_path/'ca.pem'));context.minimum_version=ssl.TLSVersion.TLSv1_2
        with context.wrap_socket(socket.create_connection(('127.0.0.1',port),timeout=3),server_hostname='localhost') as channel:
            assert channel.version() in ('TLSv1.2','TLSv1.3') and channel.cipher()[2]>=128
        for ctx,hostname in [(ssl.create_default_context(),'localhost'),(context,'127.0.0.1')]:
            with pytest.raises(ssl.SSLCertVerificationError):
                with ctx.wrap_socket(socket.create_connection(('127.0.0.1',port),timeout=3),server_hostname=hostname):pass
        connect(user=None,expected=False);connect(password_value='wrong',expected=False)
        device=connect();backend=connect('backend-ingest')
        results=[];device.on_publish=lambda c,u,mid,reason,p:results.append(reason.is_failure)
        for topic,denied in [('agapay/stations/STATION_A/telemetry',False),('agapay/stations/STATION_B/telemetry',True),('agapay/stations/STATION_A/rain-ack',True),('agapay/stations/STATION_A/telemetry-ack',True),('agapay/exercises/stations/STATION_A/telemetry',True)]:
            before=len(results);device.publish(topic,b'synthetic-only',qos=1).wait_for_publish(5)
            assert len(results)==before+1 and results[-1]==denied
        messages=[];subscribed=threading.Event();received=threading.Event()
        device.on_subscribe=lambda *args:subscribed.set()
        device.on_message=lambda c,u,m:(messages.append((m.topic,m.payload)),received.set() if m.payload==b'own-ack-sentinel' else None)
        device.subscribe([('agapay/stations/STATION_A/rain-ack',1),('agapay/stations/STATION_B/rain-ack',1),('agapay/stations/STATION_A/telemetry-ack',1),('agapay/stations/STATION_B/telemetry-ack',1)])
        assert subscribed.wait(5)
        backend.publish('agapay/stations/STATION_B/rain-ack',b'other-station-private-ack',qos=1).wait_for_publish(5)
        backend.publish('agapay/stations/STATION_A/rain-ack',b'own-ack-sentinel',qos=1).wait_for_publish(5)
        assert received.wait(5) and messages==[('agapay/stations/STATION_A/rain-ack',b'own-ack-sentinel')]
        received.clear();messages.clear()
        backend.publish('agapay/stations/STATION_B/telemetry-ack',b'other-private-water-ack',qos=1).wait_for_publish(5)
        backend.publish('agapay/stations/STATION_A/telemetry-ack',b'own-ack-sentinel',qos=1).wait_for_publish(5)
        assert received.wait(5) and messages==[('agapay/stations/STATION_A/telemetry-ack',b'own-ack-sentinel')]
        forbidden=[];backend.on_publish=lambda c,u,mid,reason,p:forbidden.append(reason.is_failure)
        backend.publish('agapay/stations/STATION_A/telemetry',b'backend-cannot-forge',qos=1).wait_for_publish(5)
        assert forbidden==[True]
        # A reviewed broker restart also disconnects already-authenticated sessions.
        stop();subprocess.run([PASSWD,'-b',str(password),'STATION_A','rotated-synthetic-only-'+uuid4().hex],check=True,capture_output=True)
        process=start();connect(password_value=secret,expected=False)
        stop();issue(expired=True);process=start()
        with pytest.raises(ssl.SSLCertVerificationError):
            with context.wrap_socket(socket.create_connection(('127.0.0.1',port),timeout=3),server_hostname='localhost'):pass
    finally:
        for c in clients:c.disconnect();c.loop_stop()
        if process and process.poll() is None:process.terminate();process.wait(timeout=5)
        log.close()
