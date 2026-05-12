import numpy as np
from typing import List

class MedicalAnalysisService:
    @staticmethod
    def calculate_hrv(heart_rates: List[float]) -> float:
        """
        Calculates Heart Rate Variability (HRV) as the standard deviation 
        of the intervals between heartbeats.
        Note: In real PPG/ECG this would be R-R intervals, but for this demo 
        we simulate it using pulse variation.
        """
        if len(heart_rates) < 2:
            return 0.0
        
        # Simulate RR intervals (approximate)
        # If pulse is 60 BPM, interval is 1000ms
        intervals = [60000 / hr for hr in heart_rates]
        return float(np.std(intervals))

    @staticmethod
    def calculate_stress_index(hrv: float) -> str:
        """
        Simple classification based on HRV.
        Lower HRV usually indicates higher stress/fatigue in medical context.
        """
        if hrv == 0: return "Unknown"
        if hrv < 20: return "High Stress"
        if hrv < 50: return "Moderate"
        return "Relaxed / Good"

    @staticmethod
    def detect_signal_noise(heart_rates: List[float]) -> float:
        """
        Detects if the signal is too erratic (simulating sensor noise).
        Returns a confidence score 0.0 - 1.0.
        """
        if len(heart_rates) < 5:
            return 1.0
        
        # If changes are too drastic (>30% per second), confidence drops
        changes = np.abs(np.diff(heart_rates))
        max_change = np.max(changes)
        
        if max_change > 40:
            return 0.4
        return 1.0
