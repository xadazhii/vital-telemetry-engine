import pytest
from unittest.mock import patch
from sqlalchemy import select
from app.models.models import Patient, Telemetry, Alert, MedicalInsight
from app.workers.tasks import process_telemetry_analysis
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_process_telemetry_analysis_anomalies(db):
    """Verify that process_telemetry_analysis generates tachycardia and low oxygen alerts."""
    # We patch AsyncSessionLocal to point to our in-memory SQLite Session Maker
    with patch("app.workers.tasks.AsyncSessionLocal", new=TestingSessionLocal):
        # 1. Create Patient
        patient = Patient(name="Test Patient Tasks", age=50, gender="male")
        db.add(patient)
        await db.commit()
        await db.refresh(patient)

        # 2. Add Telemetry triggering BOTH tachycardia (>130) and low oxygen (<92)
        telemetry = Telemetry(patient_id=patient.id, heart_rate=135.0, spo2=90.0)
        db.add(telemetry)
        await db.commit()
        await db.refresh(telemetry)

        # 3. Execute the analysis logic synchronously
        await process_telemetry_analysis(telemetry.id)

        # 4. Assert alerts created in the test database (using fresh session to see updates)
        async with TestingSessionLocal() as session:
            alert_res = await session.execute(select(Alert).where(Alert.patient_id == patient.id))
            alerts = alert_res.scalars().all()
            assert len(alerts) == 2
            
            types = [a.type for a in alerts]
            assert "tachycardia" in types
            assert "low oxygen saturation" in types
            
            for alert in alerts:
                assert alert.severity == "high"

            # 5. Assert MedicalInsight created
            insight_res = await session.execute(select(MedicalInsight).where(MedicalInsight.patient_id == patient.id))
            insights = insight_res.scalars().all()
            assert len(insights) == 1
            assert insights[0].hrv == 0.0  # Only 1 record in history, HRV is 0.0
            assert insights[0].stress_index == "Unknown"  # HRV of 0 returns 'Unknown'


@pytest.mark.asyncio
async def test_process_telemetry_analysis_normal(db):
    """Verify normal telemetry telemetry processing generates no alerts and relaxed stress index."""
    with patch("app.workers.tasks.AsyncSessionLocal", new=TestingSessionLocal):
        patient = Patient(name="Healthy Patient", age=30, gender="female")
        db.add(patient)
        await db.commit()
        await db.refresh(patient)

        # To test normal HRV/Stress Index, we populate the history with 5 steady records.
        # R-R intervals for heart rates:
        # 60 BPM -> 1000ms
        # 55 BPM -> 1090ms
        # 50 BPM -> 1200ms
        # 48 BPM -> 1250ms
        # standard deviation will be ~95ms, which is >= 50 (Relaxed / Good).
        heart_rates = [60.0, 55.0, 50.0, 48.0, 60.0]
        
        for hr in heart_rates:
            tel = Telemetry(patient_id=patient.id, heart_rate=hr, spo2=98.0)
            db.add(tel)
        await db.commit()

        # The last inserted telemetry is 60.0 BPM (healthy)
        latest_res = await db.execute(
            select(Telemetry)
            .where(Telemetry.patient_id == patient.id)
            .order_by(Telemetry.id.desc())
            .limit(1)
        )
        latest_tel = latest_res.scalar_one()

        # Run analysis
        await process_telemetry_analysis(latest_tel.id)

        # Verify no alerts were created using fresh session
        async with TestingSessionLocal() as session:
            alert_res = await session.execute(select(Alert).where(Alert.patient_id == patient.id))
            alerts = alert_res.scalars().all()
            assert len(alerts) == 0

            # Verify medical insight has good stress index
            insight_res = await session.execute(
                select(MedicalInsight)
                .where(MedicalInsight.patient_id == patient.id)
                .order_by(MedicalInsight.created_at.desc())
                .limit(1)
            )
            insight = insight_res.scalar_one()
            assert insight.hrv > 50.0
            assert insight.stress_index == "Relaxed / Good"
            assert insight.confidence_score > 0.9  # SNR-based score, smooth signal → high confidence
