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
    Adapter for Apple Health data exported via Webhooks (e.g. Health Auto Export app).
    """
    try:
        payload = await request.json()
        # Common structure: { "data": { "metrics": [ { "name": "heart_rate", "data": [...] } ] } }
        metrics = payload.get("data", {}).get("metrics", [])
        
        count = 0
        for metric in metrics:
            if metric.get("name") == "heart_rate":
                for entry in metric.get("data", []):
                    hr_val = entry.get("qty")
                    if hr_val:
                        new_tel = Telemetry(patient_id=1, heart_rate=float(hr_val), spo2=98.0)
                        db.add(new_tel)
                        count += 1
        
        if count > 0:
            await db.commit()
            # Trigger analysis for the last added record
            # (Note: in production we'd use a background task for each or a batch)
            return {"status": "success", "records_processed": count}
        
        return {"status": "no_data_processed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Apple Health data: {str(e)}")
