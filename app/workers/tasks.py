import asyncio
import logging
import json
from datetime import datetime
from app.workers.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.models import Telemetry, Alert, MedicalInsight
from app.services.analysis import MedicalAnalysisService
from sqlalchemy import select

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seerlinq_worker")

def log_event(event: str, data: dict, level="info"):
    """Structured log helper matching Seerlinq observability needs."""
    msg = json.dumps({
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        "payload": data
    })
    if level == "warning": logger.warning(msg)
    elif level == "error": logger.error(msg)
    else: logger.info(msg)

async def process_telemetry_analysis(telemetry_id: int):
    async with AsyncSessionLocal() as session:
        # Fetch the current telemetry
        result = await session.execute(select(Telemetry).where(Telemetry.id == telemetry_id))
        telemetry = result.scalar_one_or_none()
        
        if not telemetry:
            log_event("telemetry_not_found", {"id": telemetry_id}, level="error")
            return

        # Fetch last 10 records for this patient to do signal analysis
        hist_result = await session.execute(
            select(Telemetry)
            .where(Telemetry.patient_id == telemetry.patient_id)
            .order_by(Telemetry.id.desc())
            .limit(10)
        )
        history = hist_result.scalars().all()
        hr_list = [h.heart_rate for h in history]

        # 1. Basic Anomaly Detection (Alerts)
        if telemetry.heart_rate > 130:
            log_event("anomaly_detected", {"patient_id": telemetry.patient_id, "type": "tachycardia", "val": telemetry.heart_rate}, level="warning")
            session.add(Alert(patient_id=telemetry.patient_id, type="tachycardia", severity="high"))

        if telemetry.spo2 < 92:
            log_event("anomaly_detected", {"patient_id": telemetry.patient_id, "type": "low_oxygen", "val": telemetry.spo2}, level="warning")
            session.add(Alert(patient_id=telemetry.patient_id, type="low oxygen saturation", severity="high"))

        # 2. Advanced Signal Processing (Medical Insights)
        hrv = MedicalAnalysisService.calculate_hrv(hr_list)
        stress = MedicalAnalysisService.calculate_stress_index(hrv)
        confidence = MedicalAnalysisService.detect_signal_noise(hr_list)

        insight = MedicalInsight(
            patient_id=telemetry.patient_id,
            hrv=hrv,
            stress_index=stress,
            confidence_score=confidence
        )
        session.add(insight)
        
        await session.commit()
        log_event("analysis_complete", {
            "patient_id": telemetry.patient_id, 
            "hrv": round(hrv, 2), 
            "stress": stress,
            "confidence": confidence
        })

@celery_app.task(name="app.workers.tasks.process_telemetry_task")
def process_telemetry_task(telemetry_id: int):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        new_loop = asyncio.new_event_loop()
        new_loop.run_until_complete(process_telemetry_analysis(telemetry_id))
    else:
        loop.run_until_complete(process_telemetry_analysis(telemetry_id))
