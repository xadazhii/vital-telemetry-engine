"""
Example of Medical IoT Integration via Bluetooth Low Energy (BLE).
This service demonstrates how to connect to a medical device (e.g., Blood Pressure Monitor)
directly using the 'bleak' library.

Note: This requires 'bleak' to be installed and local Bluetooth hardware.
"""

import asyncio
import logging
from bleak import BleakScanner, BleakClient

# Mock UUIDs for a Heart Rate Monitor (Standard GATT Characteristics)
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medical_ble")

class MedicalBLEService:
    def __init__(self, target_address: str = None):
        self.target_address = target_address

    async def scan_devices(self):
        """Scan for nearby medical Bluetooth devices."""
        print("Scanning for medical devices...")
        devices = await BleakScanner.discover()
        for d in devices:
            print(f"Found device: {d.name} [{d.address}]")
        return devices

    def notification_handler(self, sender, data):
        """
        Handle incoming data from the medical device.
        Medical data is usually sent as byte arrays that need decoding.
        """
        # Simplified decoding of Heart Rate (per Bluetooth SIG specs)
        hr_val = data[1] 
        print(f"Мед-дані отримано через Bluetooth: Pulse = {hr_val}")
        # Тут ми б відправляли ці дані в наш API через httpx.post

    async def connect_and_monitor(self, address: str):
        """Connect to a specific medical device and subscribe to updates."""
        async with BleakClient(address) as client:
            print(f"Connected to {address}")
            # Start receiving notifications from the sensor
            await client.start_notify(HEART_RATE_MEASUREMENT_UUID, self.notification_handler)
            
            # Keep the connection alive
            await asyncio.sleep(60.0)
            await client.stop_notify(HEART_RATE_MEASUREMENT_UUID)

if __name__ == "__main__":
    # This is a demo entry point
    service = MedicalBLEService()
    # To run: asyncio.run(service.scan_devices())
    print("Bluetooth Service Initialized. Ready for Medical IoT Integration.")
