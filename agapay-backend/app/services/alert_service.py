from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, AlertTransition, Station, Telemetry
from app.services.alert_classifier import SEVERITY_ORDER, classify_depth


def process_sensor_alert(db: Session, station: Station, telemetry: Telemetry) -> None:
    """Process a newly flushed sample inside the ingestion transaction/lock.

    Never commit here: telemetry, the episode, and its transition must succeed
    together. Administrative station status does not stand in for water depth.
    """
    if telemetry.sensor_quality != "valid" or telemetry.water_depth_cm is None:
        return
    severity = classify_depth(station, telemetry.water_depth_cm)
    episode = db.scalar(select(Alert).where(
        Alert.station_id == station.station_id, Alert.status == "ACTIVE",
    ))
    previous = episode.current_severity if episode else "NORMAL"
    if episode is None:
        if severity == "NORMAL":
            return
        episode = Alert(
            station_id=station.station_id, current_severity=severity,
            highest_severity=severity, status="ACTIVE", source="sensor",
            trigger_telemetry_id=telemetry.id, trigger_sequence_no=telemetry.sequence_no,
            trigger_depth_cm=telemetry.water_depth_cm, triggered_at=telemetry.recorded_at,
            last_transition_at=telemetry.recorded_at,
        )
        db.add(episode)

    episode.latest_telemetry_id = telemetry.id
    episode.latest_sequence_no = telemetry.sequence_no
    episode.latest_depth_cm = telemetry.water_depth_cm
    if severity == previous:
        return  # Update the latest observation without inventing a transition.

    episode.current_severity = severity
    if SEVERITY_ORDER[severity] > SEVERITY_ORDER[episode.highest_severity]:
        episode.highest_severity = severity
    episode.last_transition_at = telemetry.recorded_at
    if severity == "NORMAL":
        episode.status = "RESOLVED"
        episode.resolved_at = telemetry.recorded_at
    db.flush()  # Assign a new episode ID before inserting its first transition.
    db.add(AlertTransition(
        alert_id=episode.id, station_id=station.station_id,
        telemetry_id=telemetry.id, sequence_no=telemetry.sequence_no,
        previous_severity=previous, new_severity=severity,
        water_depth_cm=telemetry.water_depth_cm, transitioned_at=telemetry.recorded_at,
    ))
