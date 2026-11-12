"""Compile actual ESP32 release TLS with synthetic headers; never read secrets or flash."""
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timedelta,timezone
import subprocess,sys,shutil
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
firmware=Path(__file__).resolve().parents[1]
folder=firmware/'.pio'/('release-fixture-'+uuid4().hex[:10]);(folder/'src').mkdir(parents=True);(folder/'include').mkdir()
shutil.copy2(firmware/'src/main.cpp',folder/'src/main.cpp')
for name in ['transport_policy.h','prototype_config.h','depth_journal.h','depth_storage.h']:shutil.copy2(firmware/'include'/name,folder/'include'/name)
shutil.copy2(firmware/'include/prototype_config.h',folder/'include/station_config.h')
(folder/'include/release_secrets.h').write_text('#pragma once\nconstexpr char WIFI_SSID[]="ISOLATED_BUILD_ONLY";\nconstexpr char WIFI_PASSWORD[]="SYNTHETIC_NOT_A_FIELD_SECRET";\nconstexpr char MQTT_HOST[]="mqtt.agapay.invalid";\nconstexpr int MQTT_PORT=8883;\nconstexpr char MQTT_USERNAME[]="STATION_001";\nconstexpr char MQTT_PASSWORD[]="SYNTHETIC_BUILD_ONLY_NOT_A_REAL_PASSWORD";\n',encoding='utf-8')
(folder/'include/ingest_secrets.h').write_text('#pragma once\nconstexpr char STATION_INGEST_TOKEN[]="agi_SYNTHETIC_BUILD_ONLY_NOT_A_REAL_TOKEN_0000";\n#define AGAPAY_DEVICE_ID "SYNTHETIC_BUILD_ONLY"\n#define AGAPAY_CONFIG_VERSION 1\n',encoding='utf-8')
key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'ISOLATED COMPILE FIXTURE ONLY')]);now=datetime.now(timezone.utc)
cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).sign(key,hashes.SHA256()).public_bytes(serialization.Encoding.PEM).decode()
(folder/'include/transport_secrets.h').write_text('#pragma once\nconstexpr char MQTT_ROOT_CA[]=R"PEM('+cert+')PEM";\n',encoding='utf-8')
(folder/'platformio.ini').write_text('[env:esp32-production]\nplatform=espressif32\nboard=esp32doit-devkit-v1\nframework=arduino\nlib_extra_dirs='+str(firmware/'.pio/libdeps/esp32doit-devkit-v1').replace('\\','/')+'\nbuild_flags=\n -DAGAPAY_RELEASE_BUILD=1\n -DAGAPAY_LOCAL_DEVELOPMENT=0\n -DAGAPAY_LOCAL_BENCH_ALERTS=0\n',encoding='utf-8')
result=subprocess.run(['C:/Python314/python.exe','-m','platformio','run','--project-dir',str(folder),'--environment','esp32-production'])
print('Synthetic release compile fixture:',folder)
print('No real secret, device, NVS, broker or field configuration was used. No upload action exists in this script.')
sys.exit(result.returncode)
