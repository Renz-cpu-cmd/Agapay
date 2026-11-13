from app.models import Station
from app.monitoring_schemas import AlertTier


SEVERITY_ORDER = {"NORMAL": 0, "ADVISORY": 1, "WARNING": 2, "EVACUATE": 3}


def classify_depth(station: Station, depth: float | None) -> AlertTier | None:
    """Classify a validated depth; missing data is unknown, never NORMAL."""
    if depth is None:
        return None
    if depth >= station.threshold_evacuate_cm:
        return "EVACUATE"
    if depth >= station.threshold_warning_cm:
        return "WARNING"
    if depth >= station.threshold_advisory_cm:
        return "ADVISORY"
    return "NORMAL"
