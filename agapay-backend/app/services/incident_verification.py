"""R4: shared, fail-closed verification of recorded sensor incidents.

One definition serves the staff operational command queue and the resident community
feed. Evidence comes only from server-side records written at ingestion time: the
registry-verified provenance of each observation and the reviewed configuration whose
hash the authenticated observation applied. Firmware-reported labels never grant it.

``operational`` means "recorded by a registry-verified physical device under an
internally field_reviewed installation configuration" (and, while ACTIVE, the station
is still eligible). It is NOT LGU authorization or an official evacuation order.
Everything else, including legacy rows without evidence, is ``unverified``.
"""
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import aliased

from app.device_config import OPERATIONAL_VALIDATION, StationConfiguration
from app.models import Alert, Station, StationIdentity, StationSourceRegistry, Telemetry, TelemetryProvenance

OPERATIONAL, UNVERIFIED = "operational", "unverified"


def recorded_evidence(telemetry_column, *, require_reviewed_configuration):
    """The observation itself was registry-verified physical/operational traffic and,
    when required, was measured under a field_reviewed configuration revision (by its
    applied hash). A later review never promotes an earlier observation."""
    p, registry, sample = aliased(TelemetryProvenance), aliased(StationSourceRegistry), aliased(Telemetry)
    conditions = [p.telemetry_id == telemetry_column,
                  p.source_class == "physical_device", p.stream == "operational",
                  registry.source_class == "physical_device", registry.stream == "operational"]
    if require_reviewed_configuration:
        config = aliased(StationConfiguration)
        conditions.append(exists(select(config.id).where(
            config.station_id == sample.station_id, config.config_hash == sample.applied_config_hash,
            config.validation_status == OPERATIONAL_VALIDATION)))
    return exists(select(p.telemetry_id).join(sample, sample.id == p.telemetry_id).join(registry,
        and_(registry.station_id == sample.station_id, registry.config_version == p.registry_version,
             registry.device_id == p.ingress_identity)).where(*conditions))


def currently_eligible(station_id_column):
    """Station is active, commissioned and its CURRENT configuration is field_reviewed."""
    revisions, current = aliased(StationConfiguration), aliased(StationConfiguration)
    latest = select(func.max(revisions.revision)).where(revisions.station_id == station_id_column).scalar_subquery()
    reviewed = exists(select(current.id).where(current.station_id == station_id_column, current.revision == latest,
                                              current.validation_status == OPERATIONAL_VALIDATION))
    # Aliases keep these subqueries independent of an outer query that also selects Station.
    identity, station = aliased(StationIdentity), aliased(Station)
    commissioned = exists(select(identity.station_id).where(
        identity.station_id == station_id_column, identity.state == "commissioned"))
    active = exists(select(station.id).where(station.station_id == station_id_column, station.status == "active"))
    return and_(reviewed, commissioned, active)


def verification_column():
    """Resident-facing verification, independent of the review-required setting."""
    recorded = and_(recorded_evidence(Alert.trigger_telemetry_id, require_reviewed_configuration=True),
                    recorded_evidence(Alert.latest_telemetry_id, require_reviewed_configuration=True))
    verified = and_(recorded, or_(Alert.status != "ACTIVE", currently_eligible(Alert.station_id)))
    return case((verified, OPERATIONAL), else_=UNVERIFIED).label("verification")
