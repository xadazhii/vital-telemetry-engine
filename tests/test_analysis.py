import pytest
from app.services.analysis import MedicalAnalysisService


def test_calculate_hrv_empty_and_short():
    assert MedicalAnalysisService.calculate_hrv([]) == 0.0
    assert MedicalAnalysisService.calculate_hrv([72.0]) == 0.0


def test_calculate_hrv_rmssd():
    assert MedicalAnalysisService.calculate_hrv([60.0, 60.0, 60.0]) == 0.0

    assert pytest.approx(MedicalAnalysisService.calculate_hrv([60.0, 120.0])) == 500.0


def test_calculate_sdnn():
    assert MedicalAnalysisService.calculate_sdnn([60.0, 60.0, 60.0]) == 0.0

    assert pytest.approx(MedicalAnalysisService.calculate_sdnn([60.0, 120.0])) == 250.0


def test_calculate_pnn50():
    assert MedicalAnalysisService.calculate_pnn50([]) == 0.0
    assert MedicalAnalysisService.calculate_pnn50([70.0]) == 0.0

    assert MedicalAnalysisService.calculate_pnn50([60.0, 120.0]) == 100.0

    assert MedicalAnalysisService.calculate_pnn50([70.0, 71.0]) == 0.0


def test_calculate_stress_index():
    assert MedicalAnalysisService.calculate_stress_index(0.0) == "Unknown"
    assert MedicalAnalysisService.calculate_stress_index(15.0) == "High Stress"
    assert MedicalAnalysisService.calculate_stress_index(19.9) == "High Stress"
    assert MedicalAnalysisService.calculate_stress_index(20.0) == "Moderate"
    assert MedicalAnalysisService.calculate_stress_index(45.0) == "Moderate"
    assert MedicalAnalysisService.calculate_stress_index(50.0) == "Relaxed / Good"
    assert MedicalAnalysisService.calculate_stress_index(85.0) == "Relaxed / Good"


def test_calculate_snr():
    assert MedicalAnalysisService.calculate_snr([60.0, 70.0]) == 1.0

    snr_smooth = MedicalAnalysisService.calculate_snr([70.0, 71.0, 72.0, 71.0, 70.0])
    assert snr_smooth > 0.9

    snr_noisy = MedicalAnalysisService.calculate_snr([70.0, 140.0, 40.0, 130.0, 50.0])
    assert snr_noisy < snr_smooth
