"""The durable journal is authoritative; water-envelope rainfall is never a panel input."""
from pathlib import Path
import sqlite3
from app.services.rain_gauge_service import RainGaugeStore
from app.services.station_security import utc


def rainfall_product(station_id,settings,now,channel):
    unavailable=dict(product="current_hour_received_tips",rainfall_mm=None,tip_count=None,
        interval_start=None,interval_end=None,quality="unknown",source="physical_rain_gauge",
        coverage_complete=False,coverage="Independent rain journal unavailable",calibration_version=None,mm_per_tip=None)
    if not settings.rain_gauge_enabled or not Path(settings.rain_gauge_store_path).is_file():
        return unavailable
    try:
        snapshot=RainGaugeStore(Path(settings.rain_gauge_store_path),read_only=True,raw_retention_days=settings.rain_raw_retention_days).snapshot(station_id,"physical_rain_gauge",now=now)
    except (sqlite3.Error,OSError,ValueError,KeyError):
        return unavailable
    product=snapshot.get("current_hour_product")
    if not product:
        return unavailable
    product={**product,"observed_at":snapshot.get('last_received_at'),"age_seconds":snapshot.get('age_seconds')}
    if channel['state']!="healthy":
        product.update(rainfall_mm=None,tip_count=None,quality="unknown",coverage=channel['reason'])
    return product
