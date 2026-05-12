import time
import random
import httpx
import sys

API_URL = "http://localhost:8000"

def create_patient():
    print("Creating a test patient...")
    try:
        response = httpx.post(f"{API_URL}/patients/", json={
            "name": "John Doe",
            "age": 54,
            "gender": "male"
        })
        response.raise_for_status()
        patient = response.json()
        print(f"Patient created: ID={patient['id']}")
        return patient['id']
    except Exception as e:
        print(f"Error creating patient: {e}")
        sys.exit(1)

def simulate():
    patient_id = create_patient()
    print("Starting telemetry simulation. Press Ctrl+C to stop.")
    
    while True:
        # Generate random heart rate (occasionally > 130 for tachycardia)
        heart_rate = random.randint(60, 150)
        # Generate random SpO2 (occasionally < 92 for low oxygen)
        spo2 = random.uniform(88, 100)
        
        telemetry_data = {
            "patient_id": patient_id,
            "heart_rate": float(heart_rate),
            "spo2": float(round(spo2, 1))
        }
        
        try:
            response = httpx.post(f"{API_URL}/telemetry/", json=telemetry_data)
            response.raise_for_status()
            print(f"Sent Telemetry: Patient={patient_id}, Pulse={heart_rate}, SpO2={telemetry_data['spo2']}%")
        except Exception as e:
            print(f"Error sending telemetry: {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    simulate()
