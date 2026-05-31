import numpy as np
from typing import List


class MedicalAnalysisService:

    @staticmethod
    def calculate_hrv(heart_rates: List[float]) -> float:
        if len(heart_rates) < 2:
            return 0.0
        intervals = [60000 / hr for hr in heart_rates]
        diffs = np.diff(intervals)
        return float(np.sqrt(np.mean(diffs ** 2)))

    @staticmethod
    def calculate_sdnn(heart_rates: List[float]) -> float:
        if len(heart_rates) < 2:
            return 0.0
        intervals = [60000 / hr for hr in heart_rates]
        return float(np.std(intervals))

    @staticmethod
    def calculate_pnn50(heart_rates: List[float]) -> float:
        if len(heart_rates) < 2:
            return 0.0
        intervals = [60000 / hr for hr in heart_rates]
        diffs = np.abs(np.diff(intervals))
        return float(np.sum(diffs > 50) / len(diffs) * 100)

    @staticmethod
    def calculate_snr(heart_rates: List[float]) -> float:
        if len(heart_rates) < 3:
            return 1.0
        arr = np.array(heart_rates, dtype=float)
        signal_power = float(np.mean(arr ** 2))
        noise_power = float(np.mean(np.diff(arr) ** 2))
        if noise_power == 0:
            return 1.0
        snr = signal_power / (signal_power + noise_power)
        return float(np.clip(snr, 0.0, 1.0))

    @staticmethod
    def calculate_stress_index(rmssd: float) -> str:
        if rmssd == 0:
            return "Unknown"
        if rmssd < 20:
            return "High Stress"
        if rmssd < 50:
            return "Moderate"
        return "Relaxed / Good"
