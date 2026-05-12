from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class PatientBase(BaseModel):
    name: str
    age: int
    gender: str

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class TelemetryBase(BaseModel):
    patient_id: int
    heart_rate: float
    spo2: float
    timestamp: Optional[datetime] = None

class TelemetryCreate(TelemetryBase):
    pass

class TelemetryResponse(TelemetryBase):
    id: int
    class Config:
        from_attributes = True

class AlertResponse(BaseModel):
    id: int
    patient_id: int
    type: str
    severity: str
    created_at: datetime
    class Config:
        from_attributes = True
