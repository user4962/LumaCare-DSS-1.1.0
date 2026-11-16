from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from .models import (
    Alert,
    AuditEvent,
    DecisionRecord,
    Device,
    Patient,
    Prescription,
    TelemetrySample,
    TherapySession,
)


SEED_PATIENT_ID = "10000000-0000-4000-8000-000000000001"
SEED_PATIENT_2_ID = "10000000-0000-4000-8000-000000000002"
SEED_DEVICE_ID = "20000000-0000-4000-8000-000000000001"
SEED_DEVICE_2_ID = "20000000-0000-4000-8000-000000000002"
SEED_PRESCRIPTION_ID = "30000000-0000-4000-8000-000000000001"
SEED_PRESCRIPTION_2_ID = "30000000-0000-4000-8000-000000000002"
SEED_SESSION_ID = "40000000-0000-4000-8000-000000000001"
SEED_SESSION_2_ID = "40000000-0000-4000-8000-000000000002"


def dt(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 7, 13, hour, minute, second, tzinfo=timezone.utc)


def seed_demo_data(db: Session) -> None:
    """Insert an idempotent, deterministic dataset for UI and API demonstrations."""

    if db.get(Patient, SEED_PATIENT_ID) is not None:
        seeded_session = db.get(TherapySession, SEED_SESSION_ID)
        if seeded_session is not None and seeded_session.status == "running":
            seeded_session.status = "completed"
            seeded_session.ended_at = dt(9, 20)
            seeded_session.stop_reason = "seed_snapshot_completed"
            seeded_session.updated_at = dt(9, 20)
            db.commit()
        return

    patient = Patient(
        id=SEED_PATIENT_ID,
        medical_record_number="DEMO-PT-001",
        given_name="Olena",
        family_name="Koval",
        date_of_birth=date(1987, 4, 18),
        administrative_sex="female",
        timezone="Europe/Kyiv",
        notes="Synthetic research-demonstration record.",
        created_at=dt(8),
        updated_at=dt(8),
    )
    patient_2 = Patient(
        id=SEED_PATIENT_2_ID,
        medical_record_number="DEMO-PT-002",
        given_name="Andrii",
        family_name="Melnyk",
        date_of_birth=date(1976, 11, 2),
        administrative_sex="male",
        timezone="Europe/Kyiv",
        notes="Synthetic research-demonstration record.",
        created_at=dt(8, 1),
        updated_at=dt(8, 1),
    )
    device = Device(
        id=SEED_DEVICE_ID,
        patient_id=SEED_PATIENT_ID,
        serial_number="LTX-DEMO-0001",
        manufacturer="Research Prototype Lab",
        model_name="LumaNode R1",
        firmware_version="0.9.3-demo",
        wavelength_nm=660.0,
        status="assigned",
        connectivity="online",
        last_seen_at=dt(9, 15),
        calibration_due_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        created_at=dt(8, 2),
        updated_at=dt(9, 15),
    )
    device_2 = Device(
        id=SEED_DEVICE_2_ID,
        patient_id=SEED_PATIENT_2_ID,
        serial_number="LTX-DEMO-0002",
        manufacturer="Research Prototype Lab",
        model_name="LumaNode R1",
        firmware_version="0.9.3-demo",
        wavelength_nm=850.0,
        status="assigned",
        connectivity="offline",
        last_seen_at=dt(7, 30),
        calibration_due_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        created_at=dt(8, 3),
        updated_at=dt(8, 3),
    )
    prescription = Prescription(
        id=SEED_PRESCRIPTION_ID,
        patient_id=SEED_PATIENT_ID,
        device_id=SEED_DEVICE_ID,
        protocol_name="Research protocol A - red-light exposure",
        indication_code="research-demo",
        target_wavelength_nm=660.0,
        wavelength_tolerance_nm=5.0,
        target_irradiance_mw_cm2=24.0,
        target_dose_j_cm2=4.0,
        max_session_dose_j_cm2=5.0,
        max_duration_seconds=900,
        max_skin_temperature_c=41.0,
        min_spo2_percent=94.0,
        irradiance_tolerance_percent=10.0,
        status="active",
        valid_from=dt(8, 5),
        instructions="Research-demonstration settings; clinician validation is required before any clinical use.",
        research_use_only=True,
        protocol_version="demo-1.0",
        created_at=dt(8, 5),
        updated_at=dt(8, 5),
    )
    prescription_2 = Prescription(
        id=SEED_PRESCRIPTION_2_ID,
        patient_id=SEED_PATIENT_2_ID,
        device_id=SEED_DEVICE_2_ID,
        protocol_name="Research protocol B - near-infrared exposure",
        indication_code="research-demo",
        target_wavelength_nm=850.0,
        wavelength_tolerance_nm=5.0,
        target_irradiance_mw_cm2=18.0,
        target_dose_j_cm2=3.0,
        max_session_dose_j_cm2=3.75,
        max_duration_seconds=720,
        max_skin_temperature_c=40.5,
        min_spo2_percent=93.0,
        irradiance_tolerance_percent=8.0,
        status="active",
        valid_from=dt(8, 6),
        instructions="Synthetic protocol data for software evaluation.",
        research_use_only=True,
        protocol_version="demo-1.0",
        created_at=dt(8, 6),
        updated_at=dt(8, 6),
    )
    therapy_session = TherapySession(
        id=SEED_SESSION_ID,
        patient_id=SEED_PATIENT_ID,
        device_id=SEED_DEVICE_ID,
        prescription_id=SEED_PRESCRIPTION_ID,
        status="completed",
        started_at=dt(9, 10),
        ended_at=dt(9, 20),
        stop_reason="seed_snapshot_completed",
        planned_duration_seconds=600,
        delivered_dose_j_cm2=0.36,
        simulator_seed=20260713,
        active_scenario="nominal",
        created_at=dt(9, 9),
        updated_at=dt(9, 20),
    )
    completed_session = TherapySession(
        id=SEED_SESSION_2_ID,
        patient_id=SEED_PATIENT_2_ID,
        device_id=SEED_DEVICE_2_ID,
        prescription_id=SEED_PRESCRIPTION_2_ID,
        status="completed",
        started_at=dt(7, 10),
        ended_at=dt(7, 20),
        stop_reason="planned_duration_elapsed",
        planned_duration_seconds=600,
        delivered_dose_j_cm2=0.18,
        simulator_seed=20260714,
        active_scenario="nominal",
        created_at=dt(7, 9),
        updated_at=dt(7, 20),
    )
    db.add_all(
        [
            patient,
            patient_2,
            device,
            device_2,
            prescription,
            prescription_2,
            therapy_session,
            completed_session,
        ]
    )
    db.flush()

    sample = TelemetrySample(
        session_id=SEED_SESSION_ID,
        sequence=0,
        captured_at=dt(9, 15),
        wavelength_nm=660.0,
        irradiance_mw_cm2=24.1,
        cumulative_dose_j_cm2=0.36,
        skin_temperature_c=36.7,
        spo2_percent=97.8,
        contact_detected=True,
        battery_percent=95.0,
        signal_quality=0.99,
        raw_payload={"source": "deterministic-seed"},
    )
    db.add(sample)
    db.flush()
    decision = DecisionRecord(
        id="50000000-0000-4000-8000-000000000001",
        session_id=SEED_SESSION_ID,
        telemetry_sample_id=sample.id,
        created_at=dt(9, 15),
        action="ALLOW",
        risk_level="low",
        risk_score=0.0,
        confidence=1.0,
        explanation="No configured research rule was activated.",
        reason_codes=[],
        fired_rules=[],
        recommended_irradiance_mw_cm2=24.0,
        recommended_duration_seconds=600,
        estimated_additional_dose_j_cm2=4.0,
        engine_version="research-engine-1.0",
        protocol_version="demo-1.0",
        research_use_only=True,
    )
    alert = Alert(
        id="60000000-0000-4000-8000-000000000001",
        session_id=SEED_SESSION_2_ID,
        patient_id=SEED_PATIENT_2_ID,
        severity="warning",
        code="DEVICE_CONNECTIVITY_REVIEW",
        message="The synthetic device connectivity state changed to offline after session completion.",
        status="open",
        created_at=dt(7, 21),
    )
    audit = AuditEvent(
        id="70000000-0000-4000-8000-000000000001",
        actor_id="demo-seeder",
        actor_role="system",
        event_type="dataset.seeded",
        entity_type="dataset",
        entity_id="deterministic-demo-v1",
        occurred_at=dt(8),
        details={"synthetic": True, "research_use_only": True},
    )
    db.add_all([decision, alert, audit])
    db.commit()
