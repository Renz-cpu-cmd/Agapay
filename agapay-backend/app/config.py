from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGAPAY_",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite:///./agapay_dev.db"
    session_days: int = 7
    cors_origins: list[str] = ["http://localhost:8080", "http://127.0.0.1:8080"]
    prediction_preview_enabled: bool = True
    local_admin_setup_enabled: bool = True
    telemetry_stale_after_seconds: int = 30

    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_tls: bool = False
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_client_id: str = "agapay-backend-dev"
    mqtt_topic: str = "agapay/stations/+/telemetry"


@lru_cache
def get_settings() -> Settings:
    return Settings()
