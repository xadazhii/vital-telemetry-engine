import pytest
from unittest.mock import patch
from app.models.models import Patient, Telemetry, Alert

@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Verify that root endpoint returns the running message."""
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Cardio Monitoring API is running"}

@pytest.mark.asyncio
async def test_patients_crud(client):
    """Verify CRUD operations on /patients/ endpoint."""
    # 1. List patients (initially empty)
    response = await client.get("/patients/")
    assert response.status_code == 200
    assert response.json() == []

    # 2. Create patient
    patient_data = {"name": "Test Patient", "age": 45, "gender": "male"}
    response = await client.post("/patients/", json=patient_data)
    assert response.status_code == 200
    created = response.json()
    assert created["id"] is not None
    assert created["name"] == "Test Patient"
    assert created["age"] == 45
    assert created["gender"] == "male"
    
    patient_id = created["id"]

    # 3. Get single patient
    response = await client.get(f"/patients/{patient_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Test Patient"

    # 4. Get non-existing patient (404)
    response = await client.get("/patients/9999")
    assert response.status_code == 404

    # 5. Delete patient
    response = await client.delete(f"/patients/{patient_id}")
    assert response.status_code == 200
    assert response.json() == {"message": "Patient deleted"}

    # 6. Verify patient is deleted
    response = await client.get(f"/patients/{patient_id}")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_telemetry_endpoints(client, db):
    """Verify telemetry creation and listing with mocked Celery task delay."""
    # 1. Create a patient first
    patient = Patient(name="Kristina", age=25, gender="female")
    db.add(patient)
    await db.commit()
    await db.refresh(patient)

    # 2. Add telemetry for this patient (mock Celery's process_telemetry_task)
    with patch("app.api.telemetry.process_telemetry_task.delay") as mock_delay:
        telemetry_data = {"patient_id": patient.id, "heart_rate": 82.0, "spo2": 97.0}
        response = await client.post("/telemetry/", json=telemetry_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["patient_id"] == patient.id
        assert result["heart_rate"] == 82.0
        assert result["spo2"] == 97.0
        
        # Verify that Celery delay was triggered
        mock_delay.assert_called_once_with(result["id"])

    # 3. Add telemetry for non-existing patient (should return 404)
    response = await client.post("/telemetry/", json={"patient_id": 999, "heart_rate": 70, "spo2": 99})
    assert response.status_code == 404

    # 4. Get telemetry list
    response = await client.get(f"/telemetry/{patient.id}")
    assert response.status_code == 200
    telemetry_list = response.json()
    assert len(telemetry_list) == 1
    assert telemetry_list[0]["heart_rate"] == 82.0

@pytest.mark.asyncio
async def test_apple_health_adapter(client, db):
    """Verify Apple Health webhook adapter parses metrics and inserts telemetry."""
    # The adapter reads flat keys directly from the payload
    payload = {
        "name": "Kristina (Apple Watch)",
        "heart_rate": 78.5,
        "spo2": 97.0,
        "age": 25,
        "height": 165.0,
        "weight": 60.0,
        "systolic": 120.0,
        "diastolic": 80.0
    }

    with patch("app.api.telemetry.process_telemetry_task.delay") as mock_delay:
        response = await client.post("/telemetry/apple-health", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert "processed_id" in result

        # Verify that Patient 1 was automatically created
        patient_resp = await client.get("/patients/1")
        assert patient_resp.status_code == 200
        assert patient_resp.json()["name"] == "Kristina (Apple Watch)"

        # Verify telemetry was added
        telemetry_resp = await client.get("/telemetry/1")
        assert telemetry_resp.status_code == 200
        telemetry_list = telemetry_resp.json()
        assert len(telemetry_list) == 1
        assert telemetry_list[0]["heart_rate"] == 78.5
        assert telemetry_list[0]["spo2"] == 97.0

        # Verify Celery was triggered
        mock_delay.assert_called_once()

@pytest.mark.asyncio
async def test_alerts_endpoint(client, db):
    """Verify alerts endpoint lists generated alerts."""
    # 1. Create Patient
    patient = Patient(name="Bob", age=60, gender="male")
    db.add(patient)
    await db.commit()
    await db.refresh(patient)

    # 2. Add an alert manually
    alert = Alert(patient_id=patient.id, type="tachycardia", severity="high")
    db.add(alert)
    await db.commit()

    # 3. Retrieve alerts via endpoint
    response = await client.get("/alerts/")
    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) == 1
    assert alerts[0]["type"] == "tachycardia"
    assert alerts[0]["patient_id"] == patient.id

def test_websocket_endpoint():
    """Verify that WebSocket endpoint accepts connections and forwards Redis Pub/Sub messages."""
    from fastapi.testclient import TestClient
    from app.main import app
    import asyncio
    from unittest.mock import patch, AsyncMock, MagicMock

    async def mock_get_message(*args, **kwargs):
        if not hasattr(mock_get_message, "called"):
            mock_get_message.called = True
            return {"data": '{"event": "telemetry_update", "patient_id": 1, "telemetry": {"heart_rate": 80, "spo2": 98, "timestamp": "2026-05-30T18:40:51"}}'}
        raise asyncio.CancelledError()

    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = mock_get_message
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    
    mock_redis = AsyncMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    mock_redis.close = AsyncMock()
    
    with patch("app.api.telemetry.aioredis.from_url", return_value=mock_redis):
        client = TestClient(app)
        with client.websocket_connect("/telemetry/ws/1") as websocket:
            data = websocket.receive_json()
            assert data["event"] == "telemetry_update"
            assert data["telemetry"]["heart_rate"] == 80
            assert data["telemetry"]["spo2"] == 98
