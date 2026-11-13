"""Additive lifecycle fences and account preferences; never rewrite observations."""
from datetime import datetime
from sqlalchemy import Boolean,DateTime,ForeignKey,Integer,String
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base
from app.models import utc_now


class StationOperation(Base):
    __tablename__="station_operations"
    station_id:Mapped[str]=mapped_column(ForeignKey('stations.station_id'),primary_key=True)
    revision:Mapped[int]=mapped_column(Integer,default=0)
    notification_epoch:Mapped[int]=mapped_column(Integer,default=0)
    reason:Mapped[str]=mapped_column(String(500))
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)


class StationDeliveryGate(Base):
    __tablename__="station_delivery_gates"
    event_id:Mapped[int]=mapped_column(ForeignKey('notification_events.id'),primary_key=True)
    notification_epoch:Mapped[int]=mapped_column(Integer)
    external_allowed:Mapped[bool]=mapped_column(Boolean)
    lifecycle_state:Mapped[str]=mapped_column(String(30))


class AccountPreference(Base):
    __tablename__="account_preferences"
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    revision:Mapped[int]=mapped_column(Integer,default=0)
    notifications_enabled:Mapped[bool]=mapped_column(Boolean,default=True)
    locale:Mapped[str]=mapped_column(String(10),default='en')
    resident_area_id:Mapped[str|None]=mapped_column(ForeignKey('verified_areas.id'),nullable=True)
    requested_language:Mapped[str|None]=mapped_column(String(80),nullable=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)


TABLES=[StationOperation.__table__,StationDeliveryGate.__table__,AccountPreference.__table__]
