import pytest
from unittest.mock import patch
from sqlalchemy import select
from app.models.models import Patient, Telemetry, Alert, MedicalInsight
from app.workers.tasks import process_telemetry_analysis
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_process_telemetry_analysis_anomalies(db):
    with patch("app.workers.tasks.AsyncSessionLocal", new=TestingSessionLocal):
        patient = Patient(name="Test Patient Tasks", age=50, gender="male")
        db.add(patient)
        await db.commit()
        await db.refresh(patient)

        telemetry = Telemetry(patient_id=patient.id, heart_rate=135.0, spo2=90.0)
        db.add(telemetry)
        await db.commit()
        await db.refresh(telemetry)

        await process_telemetry_analysis(telemetry.id)

        async with TestingSessionLocal() as session:
            alert_res = await session.execute(select(Alert).where(Alert.patient_id == patient.id))
            alerts = alert_res.scalars().all()
            assert len(alerts) == 2

            types = [a.type for a in alerts]
            assert "tachycardia" in types
            assert "low oxygen saturation" in types

            for alert in alerts:
                assert alert.severity == "high"

            insight_res = await session.execute(select(MedicalInsight).where(MedicalInsight.patient_id == patient.id))
            insights = insight_res.scalars().all()
            assert len(insights) == 1
            assert insights[0].hrv == 0.0
            assert insights[0].stress_index == "Unknown"


@pytest.mark.asyncio
async def test_process_telemetry_analysis_normal(db):
    with patch("app.workers.tasks.AsyncSessionLocal", new=TestingSessionLocal):
        patient = Patient(name="Healthy Patient", age=30, gender="female")
        db.add(patient)
        await db.commit()
        await db.refresh(patient)

        heart_rates = [60.0, 55.0, 50.0, 48.0, 60.0]

        for hr in heart_rates:
            tel = Telemetry(patient_id=patient.id, heart_rate=hr, spo2=98.0)
            db.add(tel)
        await db.commit()

        latest_res = await db.execute(
            select(Telemetry)
            .where(Telemetry.patient_id == patient.id)
            .order_by(Telemetry.id.desc())
            .limit(1)
        )
        latest_tel = latest_res.scalar_one()

        await process_telemetry_analysis(latest_tel.id)

        async with TestingSessionLocal() as session:
            alert_res = await session.execute(select(Alert).where(Alert.patient_id == patient.id))
            alerts = alert_res.scalars().all()
            assert len(alerts) == 0

            insight_res = await session.execute(
                select(MedicalInsight)
                .where(MedicalInsight.patient_id == patient.id)
                .order_by(MedicalInsight.created_at.desc())
                .limit(1)
            )
            insight = insight_res.scalar_one()
            assert insight.hrv > 50.0
            assert insight.stress_index == "Relaxed / Good"
            assert insight.confidence_score > 0.9
