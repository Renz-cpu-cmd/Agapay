"""Reviewed bindings and immutable published forecasts; experiments never write here."""
from sqlalchemy import DateTime,ForeignKey,Integer,JSON,String,UniqueConstraint,event
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime
from app.database import Base
from app.models import utc_now

class ForecastModel(Base):
    __tablename__='forecast_models'
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    bundle:Mapped[dict]=mapped_column(JSON)
    registered_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)

class ForecastApproval(Base):
    __tablename__='forecast_approvals'
    model_id:Mapped[str]=mapped_column(ForeignKey('forecast_models.id'),primary_key=True)
    version:Mapped[int]=mapped_column(Integer,default=0)
    state:Mapped[str]=mapped_column(String(20),default='draft')
    reviewer_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    evidence_sha256:Mapped[str|None]=mapped_column(String(64),nullable=True)

class ForecastDeployment(Base):
    __tablename__='forecast_deployments'
    station_id:Mapped[str]=mapped_column(ForeignKey('stations.station_id'),primary_key=True)
    version:Mapped[int]=mapped_column(Integer,default=0)
    model_id:Mapped[str|None]=mapped_column(ForeignKey('forecast_models.id'),nullable=True)
    model_review_version:Mapped[int|None]=mapped_column(Integer,nullable=True)
    configuration_hash:Mapped[str|None]=mapped_column(String(64),nullable=True)
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)

class PublishedForecast(Base):
    __tablename__='published_forecasts'
    __table_args__=(UniqueConstraint('station_id','input_fingerprint'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    station_id:Mapped[str]=mapped_column(ForeignKey('stations.station_id'),index=True)
    input_fingerprint:Mapped[str]=mapped_column(String(64))
    generated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    valid_until:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    payload:Mapped[dict]=mapped_column(JSON)

@event.listens_for(ForecastModel,'before_update')
@event.listens_for(ForecastModel,'before_delete')
@event.listens_for(PublishedForecast,'before_update')
@event.listens_for(PublishedForecast,'before_delete')
def immutable(*_):raise ValueError('Model bundles and forecast products are immutable')

TABLES=[ForecastModel.__table__,ForecastApproval.__table__,ForecastDeployment.__table__,PublishedForecast.__table__]
