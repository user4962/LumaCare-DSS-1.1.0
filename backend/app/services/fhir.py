from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import utcnow
from ..models import (
    Alert,
    DecisionRecord,
    Device,
    Patient,
    Prescription,
    TelemetrySample,
    TherapySession,
)


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _entry(resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "fullUrl": f"urn:light-dss:{resource['resourceType']}:{resource['id']}",
        "resource": resource,
    }


def patient_resource(patient: Patient) -> dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": patient.id,
        "meta": {"tag": [{"system": "urn:light-dss", "code": "synthetic-research"}]},
        "identifier": [
            {"system": "urn:light-dss:medical-record-number", "value": patient.medical_record_number}
        ],
        "name": [{"use": "official", "family": patient.family_name, "given": [patient.given_name]}],
        "gender": patient.administrative_sex,
        "birthDate": _iso(patient.date_of_birth),
    }


def device_resource(device: Device) -> dict[str, Any]:
    resource: dict[str, Any] = {
        "resourceType": "Device",
        "id": device.id,
        "meta": {"tag": [{"system": "urn:light-dss", "code": "research-prototype"}]},
        "identifier": [{"system": "urn:light-dss:serial-number", "value": device.serial_number}],
        "status": "active" if device.status != "retired" else "inactive",
        "manufacturer": device.manufacturer,
        "deviceName": [{"name": device.model_name, "type": "model-name"}],
        "version": [{"value": device.firmware_version}],
    }
    if device.patient_id:
        resource["patient"] = {"reference": f"Patient/{device.patient_id}"}
    return resource


def prescription_resource(prescription: Prescription) -> dict[str, Any]:
    return {
        "resourceType": "ServiceRequest",
        "id": prescription.id,
        "meta": {"tag": [{"system": "urn:light-dss", "code": "research-protocol"}]},
        "status": "active" if prescription.status == "active" else "on-hold",
        "intent": "plan",
        "code": {
            "coding": [
                {
                    "system": "urn:light-dss:protocol",
                    "code": prescription.indication_code,
                    "display": prescription.protocol_name,
                }
            ]
        },
        "subject": {"reference": f"Patient/{prescription.patient_id}"},
        "orderDetail": [
            {
                "text": (
                    f"Research wavelength setting: {prescription.target_wavelength_nm:g} nm "
                    f"with +/- {prescription.wavelength_tolerance_nm:g} nm tolerance"
                )
            },
            {
                "text": (
                    f"Target dose: {prescription.target_dose_j_cm2:g} J/cm2; research ceiling: "
                    f"{prescription.max_session_dose_j_cm2:g} J/cm2"
                )
            },
        ],
        "occurrencePeriod": {
            "start": _iso(prescription.valid_from),
            **({"end": _iso(prescription.valid_until)} if prescription.valid_until else {}),
        },
        "note": [
            {
                "text": (
                    "Research/demo protocol values; this export does not represent a validated "
                    "clinical order."
                )
            }
        ],
    }


def session_resource(session: TherapySession) -> dict[str, Any]:
    status_map = {
        "planned": "preparation",
        "running": "in-progress",
        "completed": "completed",
        "stopped": "stopped",
        "safety_hold": "on-hold",
    }
    return {
        "resourceType": "Procedure",
        "id": session.id,
        "meta": {"tag": [{"system": "urn:light-dss", "code": "research-session"}]},
        "status": status_map[session.status],
        "code": {"text": "Research light-therapy simulation session"},
        "subject": {"reference": f"Patient/{session.patient_id}"},
        "basedOn": [{"reference": f"ServiceRequest/{session.prescription_id}"}],
        "usedReference": [{"reference": f"Device/{session.device_id}"}],
        "performedPeriod": {
            **({"start": _iso(session.started_at)} if session.started_at else {}),
            **({"end": _iso(session.ended_at)} if session.ended_at else {}),
        },
        "note": [{"text": "Synthetic research-demonstration session."}],
    }


def observation_resource(sample: TelemetrySample) -> dict[str, Any]:
    components = [
        ("irradiance", sample.irradiance_mw_cm2, "mW/cm2"),
        ("cumulative-dose", sample.cumulative_dose_j_cm2, "J/cm2"),
        ("skin-temperature", sample.skin_temperature_c, "Cel"),
        ("spo2", sample.spo2_percent, "%"),
    ]
    return {
        "resourceType": "Observation",
        "id": f"telemetry-{sample.id}",
        "meta": {"tag": [{"system": "urn:light-dss", "code": "device-telemetry"}]},
        "status": "final",
        "code": {"text": "Light-therapy device telemetry panel"},
        "subject": {"reference": f"Patient/{sample.session.patient_id}"},
        "focus": [{"reference": f"Procedure/{sample.session_id}"}],
        "effectiveDateTime": _iso(sample.captured_at),
        "component": [
            {
                "code": {"coding": [{"system": "urn:light-dss:telemetry", "code": code}]},
                "valueQuantity": {"value": value, "unit": unit},
            }
            for code, value, unit in components
        ]
        + [
            {
                "code": {
                    "coding": [{"system": "urn:light-dss:telemetry", "code": "contact-detected"}]
                },
                "valueBoolean": sample.contact_detected,
            }
        ],
    }


def detected_issue_resource(decision: DecisionRecord) -> dict[str, Any]:
    severity_map = {"low": "low", "moderate": "moderate", "high": "high", "critical": "high"}
    return {
        "resourceType": "DetectedIssue",
        "id": decision.id,
        "meta": {"tag": [{"system": "urn:light-dss", "code": "research-decision"}]},
        "status": "final",
        "severity": severity_map[decision.risk_level],
        "code": {"text": f"Decision-support action: {decision.action}"},
        "identifiedDateTime": _iso(decision.created_at),
        "implicated": [
            {"reference": f"Procedure/{decision.session_id}"},
            {"reference": f"Observation/telemetry-{decision.telemetry_sample_id}"},
        ],
        "detail": decision.explanation,
        "mitigation": [
            {
                "action": {
                    "text": (
                        f"Research recommendation: {decision.recommended_irradiance_mw_cm2:g} "
                        f"mW/cm2 for {decision.recommended_duration_seconds:g} seconds"
                    )
                },
                "date": _iso(decision.created_at),
            }
        ],
    }


def build_patient_bundle(db: Session, patient: Patient) -> dict[str, Any]:
    devices = list(db.scalars(select(Device).where(Device.patient_id == patient.id)))
    prescriptions = list(
        db.scalars(select(Prescription).where(Prescription.patient_id == patient.id))
    )
    sessions = list(
        db.scalars(select(TherapySession).where(TherapySession.patient_id == patient.id))
    )
    resources = [patient_resource(patient)]
    resources.extend(device_resource(item) for item in devices)
    resources.extend(prescription_resource(item) for item in prescriptions)
    resources.extend(session_resource(item) for item in sessions)
    return _bundle(resources)


def build_session_bundle(db: Session, session: TherapySession) -> dict[str, Any]:
    patient = db.get(Patient, session.patient_id)
    device = db.get(Device, session.device_id)
    prescription = db.get(Prescription, session.prescription_id)
    if patient is None or device is None or prescription is None:
        raise LookupError("Session references are incomplete")
    samples = list(
        db.scalars(
            select(TelemetrySample)
            .where(TelemetrySample.session_id == session.id)
            .order_by(TelemetrySample.sequence)
        )
    )
    decisions = list(
        db.scalars(
            select(DecisionRecord)
            .where(DecisionRecord.session_id == session.id)
            .order_by(DecisionRecord.created_at)
        )
    )
    resources = [
        patient_resource(patient),
        device_resource(device),
        prescription_resource(prescription),
        session_resource(session),
    ]
    resources.extend(observation_resource(item) for item in samples)
    resources.extend(detected_issue_resource(item) for item in decisions)
    return _bundle(resources)


def build_all_bundle(db: Session) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    resources.extend(patient_resource(item) for item in db.scalars(select(Patient)))
    resources.extend(device_resource(item) for item in db.scalars(select(Device)))
    resources.extend(prescription_resource(item) for item in db.scalars(select(Prescription)))
    resources.extend(session_resource(item) for item in db.scalars(select(TherapySession)))
    resources.extend(
        observation_resource(item)
        for item in db.scalars(select(TelemetrySample).order_by(TelemetrySample.id))
    )
    resources.extend(
        detected_issue_resource(item)
        for item in db.scalars(select(DecisionRecord).order_by(DecisionRecord.created_at))
    )
    return _bundle(resources)


def _bundle(resources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "id": "light-dss-research-export",
        "meta": {
            "lastUpdated": _iso(utcnow()),
            "tag": [{"system": "urn:light-dss", "code": "r4-aligned-research-export"}],
        },
        "type": "collection",
        "timestamp": _iso(utcnow()),
        "total": len(resources),
        "entry": [_entry(resource) for resource in resources],
    }
