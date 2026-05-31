import asyncio
import logging
from bleak import BleakScanner, BleakClient

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
        if len(data) < 2:
            logger.warning(f"BLE packet too short ({len(data)} bytes), skipping")
            return
        hr_val = data[1]
        logger.info(f"BLE heart rate received: {hr_val} BPM")

    async def connect_and_monitor(self, address: str):
        """Connect to a specific medical device and subscribe to updates."""
        async with BleakClient(address) as client:
            print(f"Connected to {address}")
            await client.start_notify(HEART_RATE_MEASUREMENT_UUID, self.notification_handler)
            await asyncio.sleep(60.0)
            await client.stop_notify(HEART_RATE_MEASUREMENT_UUID)

if __name__ == "__main__":
    service = MedicalBLEService()
    print("Bluetooth Service Initialized. Ready for Medical IoT Integration.")
