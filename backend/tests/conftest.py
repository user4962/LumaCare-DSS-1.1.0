from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "test-light-dss.db"


@pytest.fixture()
def client(database_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        seed_demo_data=True,
        simulator_interval_seconds=0.05,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture()
def headers() -> dict[str, str]:
    return {"X-Actor": "test-researcher", "X-Role": "investigator"}


def create_resource_graph(
    client: TestClient,
    headers: dict[str, str],
    planned_duration_seconds: int = 300,
) -> dict[str, dict]:
    patient = client.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "medical_record_number": "TEST-PT-100",
            "given_name": "Iryna",
            "family_name": "Testova",
            "date_of_birth": "1992-03-04",
            "administrative_sex": "female",
            "timezone": "Europe/Kyiv",
        },
    )
    assert patient.status_code == 201, patient.text
    patient_data = patient.json()

    device = client.post(
        "/api/v1/devices",
        headers=headers,
        json={
            "patient_id": patient_data["id"],
            "serial_number": "TEST-DEV-100",
            "manufacturer": "Synthetic Device Lab",
            "model_name": "Research Emitter",
            "firmware_version": "test-1",
            "wavelength_nm": 660,
            "status": "assigned",
            "connectivity": "online",
            "calibration_due_at": "2099-01-01T00:00:00Z",
        },
    )
    assert device.status_code == 201, device.text
    device_data = device.json()

    prescription = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json={
            "patient_id": patient_data["id"],
            "device_id": device_data["id"],
            "protocol_name": "Test research protocol",
            "indication_code": "research-demo",
            "target_wavelength_nm": 660,
            "target_irradiance_mw_cm2": 20,
            "target_dose_j_cm2": 4,
            "max_duration_seconds": 600,
            "max_skin_temperature_c": 41,
            "min_spo2_percent": 94,
            "irradiance_tolerance_percent": 10,
            "research_use_only": True,
        },
    )
    assert prescription.status_code == 201, prescription.text
    prescription_data = prescription.json()

    session = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "patient_id": patient_data["id"],
            "device_id": device_data["id"],
            "protocol_id": prescription_data["id"],
            "planned_duration_seconds": planned_duration_seconds,
            "simulator_seed": 42,
        },
    )
    assert session.status_code == 201, session.text
    return {
        "patient": patient_data,
        "device": device_data,
        "prescription": prescription_data,
        "session": session.json(),
    }
