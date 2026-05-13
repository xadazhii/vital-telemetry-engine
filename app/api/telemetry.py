from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.db.session import get_db
from app.models.models import Telemetry, Patient, MedicalInsight
from app.schemas.schemas import TelemetryCreate, TelemetryResponse
from app.workers.tasks import process_telemetry_task

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

@router.post("/", response_model=TelemetryResponse)
async def create_telemetry(telemetry: TelemetryCreate, db: AsyncSession = Depends(get_db)):
    # Check if patient exists
    patient_result = await db.execute(select(Patient).where(Patient.id == telemetry.patient_id))
    if not patient_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")
    
    db_telemetry = Telemetry(**telemetry.model_dump())
    db.add(db_telemetry)
    await db.commit()
    await db.refresh(db_telemetry)
    
    # Trigger async processing
    process_telemetry_task.delay(db_telemetry.id)
    
    return db_telemetry

@router.get("/{patient_id}", response_model=List[TelemetryResponse])
async def list_telemetry(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Telemetry)
        .where(Telemetry.patient_id == patient_id)
        .order_by(Telemetry.timestamp.desc())
    )
    return result.scalars().all()

@router.get("/insights/{patient_id}")
async def get_insights(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MedicalInsight)
        .where(MedicalInsight.patient_id == patient_id)
        .order_by(MedicalInsight.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

@router.post("/apple-health")
async def apple_health_adapter(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Adapter for Apple Health data exported via Webhooks.
    More robust parsing for different field names and structures.
    """
    try:
        payload = await request.json()
        print(f"DEBUG: FULL PAYLOAD: {payload}")
        
        # Support both 'data' wrapper and flat structure
        metrics_container = payload.get("data", payload)
        metrics = metrics_container.get("metrics", [])
        
        if not metrics:
             print(f"DEBUG: No metrics found in payload: {payload}")

        count = 0
        for metric in metrics:
            metric_name = metric.get("name", "").lower()
            # Support 'heart_rate', 'heart rate', etc.
            if "heart" in metric_name and "rate" in metric_name:
                for entry in metric.get("data", []):
                    # Support 'qty', 'value', or 'Avg'/'Min'/'Max'
                    hr_val = entry.get("qty") or entry.get("value") or entry.get("Avg") or entry.get("Min") or entry.get("Max")
                    if hr_val:
                        # Add telemetry for patient 1 (demo)
                        new_tel = Telemetry(patient_id=1, heart_rate=float(hr_val), spo2=98.0)
                        db.add(new_tel)
                        count += 1
        
        if count > 0:
            await db.commit()
            await db.refresh(new_tel)
            # Trigger analysis for the last added record
            process_telemetry_task.delay(new_tel.id)
            
            print(f"DEBUG: Successfully processed {count} records and triggered analysis for ID {new_tel.id}")
            return {"status": "success", "records_processed": count}
        
        return {"status": "no_data_processed", "received_keys": list(payload.keys())}
    except Exception as e:
        print(f"ERROR: Apple Health Adapter failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to parse Apple Health data: {str(e)}")
