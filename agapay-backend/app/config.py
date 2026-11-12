from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, model_validator
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGAPAY_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    environment: Literal['development','testing','production'] = "development"
    database_url: str = Field(default="sqlite:///./agapay_dev.db", repr=False)
    session_days: int = 7
    cors_origins: list[str] = ["http://localhost:8080", "http://127.0.0.1:8080"]
    prediction_preview_enabled: bool = True
    hybrid_projection_enabled: bool = True
    hybrid_model_directory: str = "../data/models/hybrid_rain_v01_20261012T003510Z_fdaff56583ad"
    hybrid_dataset_path: str = "../data/processed/urdaneta_example_20261011T231532Z_ed4c1003e2e4.csv"
    local_admin_setup_enabled: bool = True
    seed_demo_data: bool = False
    service_governance_path: str = ""
    deployment_confirmed: bool = False
    staff_mfa_required: bool = False
    identity_encryption_key: SecretStr = SecretStr("")
    public_web_origin: str = ""
    public_api_origin: str = ""
    identity_mail_provider: Literal['disabled','smtp'] = 'disabled'
    smtp_host: str = ""
    smtp_port: int = Field(default=587,ge=1,le=65535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_sender: str = ""
    smtp_tls_mode: Literal['starttls','ssl'] = 'starttls'
    auth_trusted_proxy_peers: list[str] = []
    auth_proxy_key: SecretStr = SecretStr("")
    # R4: only field_reviewed installation configurations may drive resident push,
    # the staff operational queue or citywide dispatch. Default-deny everywhere. Setting
    # this to false is honoured only outside production AND with notification_provider
    # "disabled" (no external delivery possible); see device_config.operational_review_required.
    operational_review_required: bool = True
    # Isolated EXERCISE_TEST notifications: disabled by default, prohibited in production.
    exercise_notifications_enabled: bool = False
    exercise_session_max_minutes: int = Field(default=60, ge=5, le=240)
    exercise_min_send_interval_seconds: int = Field(default=30, ge=5, le=3600)
    # Second, separate opt-in for the development exercise runner to use a REAL provider.
    exercise_real_delivery_enabled: bool = False

    @model_validator(mode='after')
    def production_identity(self):
        from urllib.parse import urlsplit
        from cryptography.fernet import Fernet
        if self.identity_encryption_key.get_secret_value():
            try:Fernet(self.identity_encryption_key.get_secret_value().encode())
            except (ValueError,TypeError):raise ValueError('Identity encryption key must be a valid Fernet key') from None
        if self.auth_trusted_proxy_peers:
            from ipaddress import ip_network
            for peer in self.auth_trusted_proxy_peers:
                network=ip_network(peer)
                if network.prefixlen==0:raise ValueError('Trust explicit proxy peers, never every address')
            if len(self.auth_proxy_key.get_secret_value())<32:raise ValueError('Trusted proxy identity requires a dedicated shared key of at least 32 characters')
        if self.environment=='production' and (self.exercise_notifications_enabled or self.exercise_real_delivery_enabled):
            raise ValueError('Exercise test notifications are prohibited in production')
        if self.environment=='production':
            origin=urlsplit(self.public_web_origin)
            if (not self.deployment_confirmed or self.local_admin_setup_enabled or self.seed_demo_data
                    or self.prediction_preview_enabled or not self.staff_mfa_required
                    or not self.identity_encryption_key.get_secret_value()
                    or origin.scheme!='https' or not origin.hostname or origin.path not in ('','/')
                    or origin.query or origin.fragment or origin.username or origin.password
                    or self.identity_mail_provider!='smtp' or not self.smtp_host or not self.smtp_sender
                    or not self.smtp_username or not self.smtp_password.get_secret_value()
                    or self.database_url=='sqlite:///./agapay_dev.db'):
                raise ValueError('Production requires explicit deployment confirmation, reviewed database/origin, SMTP, identity encryption, staff MFA, and disabled demo/setup/preview defaults')
        if self.environment=='production':
            from sqlalchemy.engine import make_url
            try:
                deployment_database=make_url(self.database_url)
            except Exception:
                raise ValueError('Production database URL is invalid') from None
            if (deployment_database.drivername!='postgresql+psycopg'
                    or deployment_database.query.get('sslmode')!='verify-full'
                    or not deployment_database.query.get('sslrootcert')):
                raise ValueError('Production requires managed PostgreSQL with psycopg, verify-full TLS and an explicit root CA')
            from app.services.transport_security import https_origin, validate_mqtt
            https_origin(self.public_web_origin)
            https_origin(self.public_api_origin)
            if self.mqtt_enabled:validate_mqtt(self)
        return self
    telemetry_stale_after_seconds: int = 30
    # Shared database budgets per station/channel; HTTP and MQTT share the same budget.
    telemetry_ingest_per_minute: int = Field(default=120, ge=1, le=10000)
    rain_ingest_per_minute: int = Field(default=240, ge=1, le=10000)

    # Explicit opt-in. FCM requires valid project and ADC or a protected credential file.
    notification_ttl_seconds: int = Field(default=300,ge=60,le=3600)
    notification_receipt_days: int = Field(default=7,ge=1,le=30)
    notification_provider: str = "disabled"
    # R2 P0: external restore witness for send-capable workers (a directory OUTSIDE the
    # database and its backups). Required in production; see docs/delivery-recovery.md.
    delivery_ledger_path: str = ""
    firebase_project_id: str = ""
    firebase_credentials_path: str = ""

    mqtt_enabled: bool = False
    # Advisory forecast summary to station displays (MQTT owner only); never drives alerts.
    forecast_downlink_enabled: bool = True
    forecast_downlink_seconds: int = Field(default=30,ge=10,le=300)
    mqtt_external_subscriber: bool = False
    mqtt_status_path: str = ""
    api_tls_proxy_peer: str = ""
    read_model_cache_enabled: bool = True
    read_model_worker_enabled: bool = False
    read_model_seconds: int = Field(default=2,ge=1,le=5)
    # R2 pool/cache acceptance. Last-known grace is bounded and always labelled degraded with
    # original timestamps; it never extends freshness. Refresh-ahead rebuilds a still-fresh
    # snapshot once (single-flight) in its last half-life so readers are not left on expiry.
    read_model_stale_seconds: int = Field(default=2,ge=0,le=5)
    read_model_wait_seconds: float = Field(default=2,ge=0,le=5)
    read_model_refresh_ahead: bool = True
    # Per-process PostgreSQL pool (each API worker / background worker process has its own).
    # Budget: processes x (pool_size + max_overflow) must stay below server max_connections
    # minus reserved/admin slots; see docs/database-capacity.md.
    database_pool_size: int = Field(default=5,ge=1,le=50)
    database_max_overflow: int = Field(default=10,ge=0,le=50)
    database_pool_timeout_seconds: float = Field(default=10,ge=1,le=60)
    database_pool_recycle_seconds: int = Field(default=-1,ge=-1,le=86400)
    read_model_max_entries: int = Field(default=128,ge=8,le=512)
    read_model_max_stations: int = Field(default=200,ge=1,le=1000)
    read_model_max_points: int = Field(default=30000,ge=1200,le=100000)
    operations_required: list[Literal['monitoring','mqtt','rain','notifications','identity_mail','models','forecasting']] = ['monitoring']
    operations_min_free_bytes: int = Field(default=16777216,ge=1024)
    operations_queue_age_seconds: int = Field(default=60,ge=10,le=600)
    operations_probe_enabled: bool = False
    observability_scrape_token: SecretStr = SecretStr("")
    observability_enabled: bool = True
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_tls: bool = False
    mqtt_ca_file: str = ""
    mqtt_client_cert_file: str = ""
    mqtt_client_key_file: str = ""
    mqtt_username: str = ""
    mqtt_password: SecretStr = SecretStr("")
    mqtt_client_id: str = "agapay-backend-dev"
    mqtt_topic: str = "agapay/stations/+/telemetry"

    # Separate durable rain journal, never the operational telemetry database.
    rain_raw_retention_days: int = Field(default=30,ge=2,le=365)
    rain_archive_directory: str = "../data/rain-archives"
    rain_archive_batch: int = Field(default=5000,ge=100,le=10000)
    rain_gauge_enabled: bool = False
    rain_gauge_topic: str = "agapay/stations/+/rain"
    rain_gauge_store_path: str = "../data/live_rain/rain-events.sqlite3"
    # User confirmed 0.70 mm/tip on 2026-10-12; other stations require explicit configuration.
    rain_gauge_calibrations: dict[str,float] = {"STATION_001":0.70}
    rain_gauge_allow_simulator: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
