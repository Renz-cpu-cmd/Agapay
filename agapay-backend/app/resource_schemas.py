from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import Field, StringConstraints, field_validator, model_validator
from app.account_schemas import AccountInput
from app.identity_schemas import Reason

Text = Annotated[str,StringConstraints(strip_whitespace=True,min_length=3,max_length=2000)]
ResourceId = Annotated[str,StringConstraints(pattern=r'^[A-Za-z0-9_-]{3,80}$')]


class Point(AccountInput):
    latitude: float = Field(ge=-90,le=90,allow_inf_nan=False)
    longitude: float = Field(ge=-180,le=180,allow_inf_nan=False)


class ResourceContact(AccountInput):
    name: str = Field(min_length=3,max_length=120)
    contact: str = Field(min_length=3,max_length=150)
    hours: str = Field(min_length=3,max_length=150)


class ShelterData(AccountInput):
    name: str = Field(min_length=3,max_length=150)
    address: Text
    point: Point
    state: Literal['inactive','active','full'] = 'inactive'
    activated_at: datetime | None = None
    capacity: int | None = Field(default=None,ge=0,le=100000)
    occupancy: int | None = Field(default=None,ge=0,le=100000)
    capacity_observed_at: datetime | None = None
    wheelchair_accessible: bool | None = None
    services: list[str] = Field(default_factory=list,max_length=20)
    access_constraints: Text
    instructions: Text
    contacts: list[ResourceContact] = Field(min_length=1,max_length=10)

    @model_validator(mode='after')
    def times(self):
        for value in (self.activated_at,self.capacity_observed_at):
            if value is not None and value.tzinfo is None: raise ValueError('Resource timestamps require a timezone')
        if self.state!='inactive' and self.activated_at is None: raise ValueError('Active/full shelter needs its recorded activation time')
        if (self.capacity is not None or self.occupancy is not None) and self.capacity_observed_at is None:
            raise ValueError('Capacity/occupancy needs an observation time')
        if any(len(s.strip())<2 or len(s)>100 for s in self.services): raise ValueError('Invalid service label')
        return self


class RoadData(AccountInput):
    name: str = Field(min_length=3,max_length=150)
    state: Literal['closed','restricted','reopened']
    geometry: list[Point] = Field(min_length=2,max_length=50)
    access_constraints: Text
    instructions: Text
    contacts: list[ResourceContact] = Field(min_length=1,max_length=10)


class PreparednessData(AccountInput):
    name: str = Field(min_length=3,max_length=150)
    instructions: Text
    contacts: list[ResourceContact] = Field(min_length=1,max_length=10)


class ResourceWrite(AccountInput):
    id: ResourceId
    kind: Literal['shelter','road','preparedness']
    authority_id: str = Field(min_length=3,max_length=50)
    area_ids: list[str] = Field(min_length=1,max_length=50)
    mode: Literal['Actual','Exercise'] = 'Actual'
    expected_version: int = Field(ge=0)
    reason: Reason
    source: str = Field(min_length=3,max_length=1200)
    data: dict

    @model_validator(mode='after')
    def typed_data(self):
        schema={'shelter':ShelterData,'road':RoadData,'preparedness':PreparednessData}[self.kind]
        self.data=schema.model_validate(self.data).model_dump(mode='json')
        return self


class ResourceReview(AccountInput):
    expected_version: int = Field(ge=1)
    action: Literal['verify','withdraw']
    reason: Reason
    expires_at: datetime | None = None

    @field_validator('expires_at')
    @classmethod
    def utc_time(cls,value):
        if value is None:return None
        if value.tzinfo is None:raise ValueError('Expiry requires timezone')
        return value.astimezone(timezone.utc)
