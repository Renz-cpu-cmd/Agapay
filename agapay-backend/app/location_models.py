"""Migration 0009: structured precision of a station's registry position (A7.1).

`coordinates_verified` records that an operator confirmed the pair at commissioning. It
says nothing about how precise the pair is. A bench rig located at campus level and a
surveyed river installation can both be "confirmed", so clients must not present every
confirmed pair as an exact installation point.

This table holds the precision separately, beside the station (not on the commissioned
identity, so recording it never re-commissions the device or revokes its credential).
No row means the precision was never recorded: existing presentation is kept, nothing
is relabelled as approximate by inference, and free-text datum notes are never parsed.
"""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import utc_now

LOCATION_BASES = ('surveyed', 'owner_confirmed', 'estimated')
# A surveyed pair at or below this radius may be shown as an exact installation point.
PRECISE_RADIUS_M = 50


class StationLocationPrecision(Base):
    __tablename__ = 'station_location_precision'
    __table_args__ = (
        CheckConstraint('precision_m >= 1 AND precision_m <= 100000', name='ck_station_location_precision_range'),
        CheckConstraint("basis IN ('surveyed','owner_confirmed','estimated')", name='ck_station_location_precision_basis'),
    )
    station_id: Mapped[str] = mapped_column(ForeignKey('stations.station_id'), primary_key=True)
    # Radius, in metres, within which the true installation point is expected to lie.
    precision_m: Mapped[int] = mapped_column(Integer)
    basis: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
