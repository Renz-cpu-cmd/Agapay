"""Validated TLS contexts; no insecure fallback or implicit proxy trust."""
from ipaddress import ip_address
from urllib.parse import urlsplit
import ssl


def https_origin(value):
    url=urlsplit(value)
    host=(url.hostname or '').lower()
    try:local=not ip_address(host).is_global
    except ValueError:local=host in ('localhost','') or host.endswith(('.localhost','.local')) or '.' not in host
    if url.scheme!='https' or local or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        raise ValueError('Production requires a public HTTPS origin without credentials, path, query or fragment')
    try:url.port
    except ValueError:raise ValueError('Invalid HTTPS origin port') from None
    return value.rstrip('/')


def validate_mqtt(settings):
    if not settings.mqtt_tls:raise ValueError('MQTT ingestion requires TLS outside development')
    if not settings.mqtt_username or not settings.mqtt_password.get_secret_value():raise ValueError('MQTT requires a dedicated broker account')
    if settings.mqtt_port in (1883,1884) or not 1<=settings.mqtt_port<=65535:raise ValueError('Production MQTT cannot use development plaintext ports')
    if not settings.mqtt_host or any(c in settings.mqtt_host for c in '/@\\') or settings.mqtt_client_id.endswith('-dev'):
        raise ValueError('Review production MQTT host and unique client ID')
    if bool(settings.mqtt_client_cert_file)!=bool(settings.mqtt_client_key_file):raise ValueError('MQTT client certificate and private key must be configured together')


def mqtt_context(settings):
    context=ssl.create_default_context(cafile=settings.mqtt_ca_file or None)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.verify_mode=ssl.CERT_REQUIRED
    context.check_hostname=True
    if bool(settings.mqtt_client_cert_file)!=bool(settings.mqtt_client_key_file):raise ValueError('MQTT certificate/key pair incomplete')
    if settings.mqtt_client_cert_file:context.load_cert_chain(settings.mqtt_client_cert_file,settings.mqtt_client_key_file)
    return context
