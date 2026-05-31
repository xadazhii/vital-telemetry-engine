import asyncio
import logging
import json
from datetime import datetime
import redis.asyncio as aioredis
from app.workers.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.models import Telemetry, Alert, MedicalInsight
from app.services.analysis import MedicalAnalysisService
from app.core.config import settings
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seerlinq_worker")

def log_event(event: str, data: dict, level="info"):
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
        result = await session.execute(select(Telemetry).where(Telemetry.id == telemetry_id))
        telemetry = result.scalar_one_or_none()

        if not telemetry:
            log_event("telemetry_not_found", {"id": telemetry_id}, level="error")
            return

        hist_result = await session.execute(
            select(Telemetry)
            .where(Telemetry.patient_id == telemetry.patient_id)
            .order_by(Telemetry.id.desc())
            .limit(10)
        )
        history = hist_result.scalars().all()
        hr_list = [h.heart_rate for h in history]

        alerts_added = []

        if telemetry.heart_rate > 130:
            log_event("anomaly_detected", {"patient_id": telemetry.patient_id, "type": "tachycardia", "val": telemetry.heart_rate}, level="warning")
            alert = Alert(patient_id=telemetry.patient_id, type="tachycardia", severity="high")
            session.add(alert)
            alerts_added.append(alert)
        elif telemetry.heart_rate > 0 and telemetry.heart_rate < 50:
            log_event("anomaly_detected", {"patient_id": telemetry.patient_id, "type": "bradycardia", "val": telemetry.heart_rate}, level="warning")
            alert = Alert(patient_id=telemetry.patient_id, type="bradycardia", severity="medium")
            session.add(alert)
            alerts_added.append(alert)

        if telemetry.spo2 is not None and telemetry.spo2 < 92:
            log_event("anomaly_detected", {"patient_id": telemetry.patient_id, "type": "low_oxygen", "val": telemetry.spo2}, level="warning")
            alert = Alert(patient_id=telemetry.patient_id, type="low oxygen saturation", severity="high")
            session.add(alert)
            alerts_added.append(alert)

        if telemetry.systolic and telemetry.diastolic:
            systolic = telemetry.systolic
            diastolic = telemetry.diastolic
            if systolic >= 140 or diastolic >= 90:
                log_event("anomaly_detected", {"patient_id": telemetry.patient_id, "type": "hypertension", "systolic": systolic, "diastolic": diastolic}, level="warning")
                alert = Alert(patient_id=telemetry.patient_id, type=f"Hypertension ({int(systolic)}/{int(diastolic)})", severity="high")
                session.add(alert)
                alerts_added.append(alert)
            elif systolic <= 90 or diastolic <= 60:
                log_event("anomaly_detected", {"patient_id": telemetry.patient_id, "type": "hypotension", "systolic": systolic, "diastolic": diastolic}, level="warning")
                alert = Alert(patient_id=telemetry.patient_id, type=f"Hypotension ({int(systolic)}/{int(diastolic)})", severity="medium")
                session.add(alert)
                alerts_added.append(alert)

        hrv = MedicalAnalysisService.calculate_hrv(hr_list)
        sdnn = MedicalAnalysisService.calculate_sdnn(hr_list)
        pnn50 = MedicalAnalysisService.calculate_pnn50(hr_list)
        stress = MedicalAnalysisService.calculate_stress_index(hrv)
        confidence = MedicalAnalysisService.calculate_snr(hr_list)

        bmi_status = ""
        bmi = 0.0
        if telemetry.weight and telemetry.height and telemetry.height > 0:
            height_m = telemetry.height / 100.0
            bmi = telemetry.weight / (height_m * height_m)
            if bmi < 18.5: bmi_status = "Underweight"
            elif bmi < 25: bmi_status = "Normal weight"
            elif bmi < 30: bmi_status = "Overweight"
            else: bmi_status = "Obese"

        analysis_parts = []
        if bmi_status:
            analysis_parts.append(f"BMI: {bmi:.1f} ({bmi_status}).")

        if telemetry.systolic and telemetry.diastolic:
            bp_val = f"{int(telemetry.systolic)}/{int(telemetry.diastolic)}"
            if telemetry.systolic >= 140 or telemetry.diastolic >= 90:
                analysis_parts.append(f"Blood pressure {bp_val} is HIGH (hypertension limit reached).")
            elif telemetry.systolic <= 90 or telemetry.diastolic <= 60:
                analysis_parts.append(f"Blood pressure {bp_val} is LOW.")
            else:
                analysis_parts.append(f"Blood pressure {bp_val} is Normal.")

        if stress == "High Stress":
            analysis_parts.append("Elevated stress index detected. Relaxation is recommended.")
        else:
            analysis_parts.append("Cardiac stress index is Normal.")

        insight_text = " ".join(analysis_parts) if analysis_parts else "Cardiac rhythm and health indicators are stable."

        insight = MedicalInsight(
            patient_id=telemetry.patient_id,
            hrv=round(hrv, 2),
            sdnn=round(sdnn, 2),
            pnn50=round(pnn50, 2),
            stress_index=stress,
            confidence_score=round(confidence, 3)
        )
        session.add(insight)

        await session.commit()

        try:
            await session.refresh(telemetry)
            for alert in alerts_added:
                await session.refresh(alert)
        except Exception as e:
            log_event("db_refresh_failed", {"error": str(e)}, level="warning")

        log_event("analysis_complete", {
            "patient_id": telemetry.patient_id,
            "rmssd": round(hrv, 2),
            "sdnn": round(sdnn, 2),
            "pnn50": round(pnn50, 2),
            "stress": stress,
            "snr": round(confidence, 3)
        })

        try:
            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

            payload = {
                "event": "telemetry_update",
                "patient_id": telemetry.patient_id,
                "telemetry": {
                    "heart_rate": telemetry.heart_rate,
                    "spo2": telemetry.spo2,
                    "systolic": telemetry.systolic,
                    "diastolic": telemetry.diastolic,
                    "age": telemetry.age,
                    "height": telemetry.height,
                    "weight": telemetry.weight,
                    "timestamp": telemetry.timestamp.isoformat() if telemetry.timestamp else datetime.utcnow().isoformat()
                },
                "insight": {
                    "hrv": round(hrv, 2),
                    "stress_index": stress,
                    "analysis_text": insight_text,
                    "confidence_score": confidence
                },
                "alerts": [
                    {
                        "type": a.type,
                        "severity": a.severity,
                        "created_at": a.created_at.isoformat() if a.created_at else datetime.utcnow().isoformat()
                    }
                    for a in alerts_added
                ]
            }

            await redis_client.publish(f"patient:{telemetry.patient_id}", json.dumps(payload))
            await redis_client.aclose()
        except Exception as e:
            log_event("redis_publish_failed", {"error": str(e)}, level="error")

@celery_app.task(name="app.workers.tasks.process_telemetry_task")
def process_telemetry_task(telemetry_id: int):
    asyncio.run(process_telemetry_analysis(telemetry_id))

@celery_app.task(name="app.workers.tasks.simulate_telemetry_task")
def simulate_telemetry_task():
    from app.models.models import Telemetry, Patient
    from app.db.session import AsyncSessionLocal
    import random

    async def _generate():
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            patient_check = await db.execute(select(Patient).where(Patient.id == 2))
            if not patient_check.scalar_one_or_none():
                bot = Patient(id=2, name="Demo Simulator (Bot)", age=30, gender="other")
                db.add(bot)
                await db.commit()

            hr = random.randint(65, 145)
            spo2 = round(random.uniform(94, 100), 1)

            new_telemetry = Telemetry(
                patient_id=2,
                heart_rate=float(hr),
                spo2=float(spo2)
            )
            db.add(new_telemetry)
            await db.commit()
            await db.refresh(new_telemetry)

            process_telemetry_task.delay(new_telemetry.id)
            log_event("simulator_generated", {"patient_id": 2, "heart_rate": hr, "spo2": spo2})

    asyncio.run(_generate())
