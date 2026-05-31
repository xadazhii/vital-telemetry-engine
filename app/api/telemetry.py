from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timezone
import asyncio
import logging
import redis.asyncio as aioredis
from app.core.config import settings
from app.db.session import get_db
from app.models.models import Telemetry, Patient, MedicalInsight
from app.schemas.schemas import TelemetryCreate, TelemetryResponse
from app.workers.tasks import process_telemetry_task
from app.core.security import get_current_physician
from app.models.models import Physician

logger = logging.getLogger("seerlinq_api")

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

@router.post("/", response_model=TelemetryResponse)
async def create_telemetry(telemetry: TelemetryCreate, db: AsyncSession = Depends(get_db)):
    patient_result = await db.execute(select(Patient).where(Patient.id == telemetry.patient_id))
    if not patient_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")

    db_telemetry = Telemetry(**telemetry.model_dump())
    db.add(db_telemetry)
    await db.commit()
    await db.refresh(db_telemetry)

    process_telemetry_task.delay(db_telemetry.id)

    return db_telemetry

@router.get("/{patient_id}", response_model=List[TelemetryResponse])
async def list_telemetry(
    patient_id: int,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    since: Optional[datetime] = Query(None, description="Filter records after this datetime (ISO 8601)"),
    db: AsyncSession = Depends(get_db),
    _: Physician = Depends(get_current_physician),
):
    q = select(Telemetry).where(Telemetry.patient_id == patient_id)
    if since:
        q = q.where(Telemetry.timestamp >= since)
    q = q.order_by(Telemetry.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()

@router.get("/insights/{patient_id}")
async def get_insights(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    _: Physician = Depends(get_current_physician),
):
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
    Adapter for Apple Health data.
    Receives user profile (age, height, weight) and health metrics (systolic, diastolic, heart_rate, spo2).
    """
    try:
        payload = await request.json()
        patient_name = (payload.get("name") or "").strip() or "Apple Watch User"
        logger.info(f"Received Apple Health payload, name='{patient_name}'")

        patient_check = await db.execute(select(Patient).where(Patient.id == 1))
        existing = patient_check.scalar_one_or_none()
        if not existing:
            new_patient = Patient(id=1, name=patient_name, age=payload.get("age", 25), gender="female")
            db.add(new_patient)
            await db.commit()
        elif existing.name != patient_name:
            existing.name = patient_name
            await db.commit()

        new_tel = Telemetry(
            patient_id=1,
            heart_rate=float(payload.get("heart_rate", 0.0)),
            spo2=float(payload["spo2"]) if payload.get("spo2") else None,
            age=payload.get("age"),
            height=payload.get("height"),
            weight=payload.get("weight"),
            systolic=payload.get("systolic"),
            diastolic=payload.get("diastolic")
        )

        db.add(new_tel)
        await db.commit()
        await db.refresh(new_tel)

        process_telemetry_task.delay(new_tel.id)

        return {"status": "success", "processed_id": new_tel.id}
    except Exception as e:
        logger.error(f"Apple Health Adapter failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to process telemetry data: {str(e)}")

@router.post("/history-import")
async def history_import(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Bulk import of historical heart rate data from Apple Health.
    Expects: { name, readings: [{heart_rate, timestamp}] }
    Skips records that already exist by timestamp to prevent duplicates.
    """
    try:
        payload = await request.json()
        readings = payload.get("readings", [])
        patient_name = (payload.get("name") or "").strip() or "Apple Watch User"

        if not readings:
            return {"status": "success", "imported": 0}

        patient_check = await db.execute(select(Patient).where(Patient.id == 1))
        existing = patient_check.scalar_one_or_none()
        if not existing:
            db.add(Patient(id=1, name=patient_name, age=25, gender="female"))
            await db.commit()
        elif existing.name != patient_name:
            existing.name = patient_name
            await db.commit()

        existing_ts_result = await db.execute(
            select(Telemetry.timestamp).where(Telemetry.patient_id == 1)
        )
        existing_timestamps = {row[0].replace(tzinfo=timezone.utc) if row[0].tzinfo is None else row[0]
                               for row in existing_ts_result.fetchall()}

        imported = 0
        last_id = None
        for r in readings:
            try:
                ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                ts_utc = ts.astimezone(timezone.utc)
                if ts_utc in existing_timestamps:
                    continue
                tel = Telemetry(patient_id=1, heart_rate=float(r["heart_rate"]), spo2=98.0, timestamp=ts)
                db.add(tel)
                existing_timestamps.add(ts_utc)
                imported += 1
            except Exception:
                continue

        await db.commit()

        if imported > 0:
            latest = await db.execute(
                select(Telemetry)
                .where(Telemetry.patient_id == 1)
                .order_by(Telemetry.timestamp.desc())
                .limit(1)
            )
            last_tel = latest.scalar_one_or_none()
            if last_tel:
                process_telemetry_task.delay(last_tel.id)

        logger.info(f"History import: {imported} records imported for patient 1")
        return {"status": "success", "imported": imported}
    except Exception as e:
        logger.error(f"History import failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.websocket("/ws/{patient_id}")
async def websocket_endpoint(websocket: WebSocket, patient_id: int):
    await websocket.accept()

    async def listen_to_client(ws: WebSocket):
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            raise

    async def listen_to_redis(ws: WebSocket, pid: int):
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"patient:{pid}")
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    await ws.send_text(message["data"])
        finally:
            await pubsub.unsubscribe(f"patient:{pid}")
            await pubsub.close()
            await redis_client.close()

    try:
        await asyncio.gather(
            listen_to_client(websocket),
            listen_to_redis(websocket, patient_id)
        )
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
