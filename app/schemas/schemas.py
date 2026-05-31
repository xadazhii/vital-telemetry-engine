from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, List


class PatientBase(BaseModel):
    name: str
    age: int
    gender: str


class PatientCreate(PatientBase):
    physician_id: Optional[int] = None


class PatientResponse(PatientBase):
    id: int
    physician_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TelemetryBase(BaseModel):
    patient_id: int
    heart_rate: float
    spo2: Optional[float] = None
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    timestamp: Optional[datetime] = None

    @field_validator("heart_rate")
    @classmethod
    def validate_heart_rate(cls, v: float) -> float:
        if not 20 <= v <= 300:
            raise ValueError("heart_rate must be between 20 and 300 BPM")
        return v

    @field_validator("spo2")
    @classmethod
    def validate_spo2(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not 70 <= v <= 100:
            raise ValueError("spo2 must be between 70 and 100 %")
        return v

    @field_validator("systolic")
    @classmethod
    def validate_systolic(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not 50 <= v <= 300:
            raise ValueError("systolic must be between 50 and 300 mmHg")
        return v

    @field_validator("diastolic")
    @classmethod
    def validate_diastolic(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not 30 <= v <= 200:
            raise ValueError("diastolic must be between 30 and 200 mmHg")
        return v


class TelemetryCreate(TelemetryBase):
    pass


class TelemetryResponse(TelemetryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AlertResponse(BaseModel):
    id: int
    patient_id: int
    type: str
    severity: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MedicalInsightResponse(BaseModel):
    id: int
    patient_id: int
    hrv: Optional[float] = None
    sdnn: Optional[float] = None
    pnn50: Optional[float] = None
    stress_index: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PhysicianCreate(BaseModel):
    name: str
    specialty: Optional[str] = None
    email: str
    password: str


class PhysicianResponse(BaseModel):
    id: int
    name: str
    specialty: Optional[str] = None
    email: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
