from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base

class Physician(Base):
    __tablename__ = "physicians"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    specialty = Column(String)

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    gender = Column(String)
    physician_id = Column(Integer, ForeignKey("physicians.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    heart_rate = Column(Float)
    spo2 = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    type = Column(String)  # e.g., "tachycardia", "low oxygen"
    severity = Column(String) # e.g., "high", "medium"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MedicalInsight(Base):
    __tablename__ = "medical_insights"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    hrv = Column(Float)
    stress_index = Column(String)
    confidence_score = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
