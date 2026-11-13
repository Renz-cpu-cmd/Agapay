"""Import the complete schema for offline tools; importing never creates tables."""
from app import models, device_config, governance_models, operations_models
from app import identity_models, sos_response_models, resource_models
from app import runtime_models,delivery_models
from app import forecast_models, privacy_models
from app import exercise_models
from app import recovery_models
from app import location_models
from app import tracking_models
from app.database import Base

metadata = Base.metadata
