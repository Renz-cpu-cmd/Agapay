"""Configuration independent of application settings and database credentials."""
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import re

DATA_ROOT = Path(__file__).resolve().parents[4] / "data"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = {
    "precipitation": ("precipitation_mm", "mm"),
    "rain": ("rainfall_mm", "mm"),
    "temperature_2m": ("temperature_c", "°C"),
    "relative_humidity_2m": ("relative_humidity_pct", "%"),
}
SOURCES = ("open_meteo", "philsensors", "pagasa", "nasa_gpm", "agapay_esp32")


def safe_label(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Identifiers must contain 1-80 letters, digits, underscores or hyphens")
    return value


def create_layout(root: Path) -> None:
    for name in SOURCES:
        (root / "raw" / name).mkdir(parents=True, exist_ok=True)
    for name in ("processed", "metadata", "reports"):
        (root / name).mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class RainfallConfig:
    latitude: float = 15.97430
    longitude: float = 120.56906
    location_id: str = "urdaneta_example"
    start: date = date(2020, 1, 1)
    end: date = date(2025, 12, 31)
    batch_days: int = 366
    timeout: float = 60
    attempts: int = 3
    root: Path = DATA_ROOT

    def __post_init__(self) -> None:
        safe_label(self.location_id)
        if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
            raise ValueError("Coordinates outside WGS84 bounds")
        if self.end < self.start or self.batch_days < 1 or self.attempts < 1 or self.timeout <= 0:
            raise ValueError("Invalid date range, batch size, attempts or timeout")

    def batches(self):
        start = self.start
        while start <= self.end:
            end = min(start + timedelta(days=self.batch_days - 1), self.end)
            yield start, end
            start = end + timedelta(days=1)
