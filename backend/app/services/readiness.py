from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import utcnow
from ..models import Device, Patient, Prescription, TherapySession


@dataclass(frozen=True, slots=True)
class ReadinessIssue:
    code: str
    message: str
    observed: str
    threshold: str

    def as_detail(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "observed": self.observed,
            "threshold": self.threshold,
        }

    def as_rule(self) -> dict[str, object]:
        return {
            "rule_id": self.code,
            "severity": "HOLD",
            "strength": 1.0,
            "message": self.message,
            "observed": self.observed,
            "threshold": self.threshold,
        }


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_prescription_interval(
    valid_from: datetime, valid_until: datetime | None
) -> ReadinessIssue | None:
    if valid_until is not None and as_utc(valid_until) <= as_utc(valid_from):
        return ReadinessIssue(
            "PRESCRIPTION_INTERVAL_INVALID",
            "The prescription validity interval is empty or reversed.",
            f"{as_utc(valid_from).isoformat()} to {as_utc(valid_until).isoformat()}",
            "valid_until must be later than valid_from",
        )
    return None


def assess_readiness(
    db: Session,
    *,
    patient: Patient,
    device: Device,
    prescription: Prescription,
    exclude_session_id: str | None = None,
    at: datetime | None = None,
) -> list[ReadinessIssue]:
    evaluated_at = as_utc(at or utcnow())
    issues: list[ReadinessIssue] = []

    if prescription.patient_id != patient.id:
        issues.append(ReadinessIssue(
            "PRESCRIPTION_PATIENT_MISMATCH",
            "The prescription is assigned to another patient.",
            prescription.patient_id,
            patient.id,
        ))
    if prescription.device_id not in (None, device.id):
        issues.append(ReadinessIssue(
            "PRESCRIPTION_DEVICE_MISMATCH",
            "The prescription is assigned to another device.",
            str(prescription.device_id),
            device.id,
        ))
    if device.patient_id not in (None, patient.id):
        issues.append(ReadinessIssue(
            "DEVICE_PATIENT_MISMATCH",
            "The device is assigned to another patient.",
            str(device.patient_id),
            patient.id,
        ))
    if prescription.status != "active":
        issues.append(ReadinessIssue(
            "PRESCRIPTION_NOT_ACTIVE",
            "The prescription is not active.",
            prescription.status,
            "active",
        ))
    interval_issue = validate_prescription_interval(
        prescription.valid_from, prescription.valid_until
    )
    if interval_issue:
        issues.append(interval_issue)
    if as_utc(prescription.valid_from) > evaluated_at:
        issues.append(ReadinessIssue(
            "PRESCRIPTION_NOT_YET_VALID",
            "The prescription validity period has not started.",
            evaluated_at.isoformat(),
            f">= {as_utc(prescription.valid_from).isoformat()}",
        ))
    if prescription.valid_until is not None and evaluated_at >= as_utc(prescription.valid_until):
        issues.append(ReadinessIssue(
            "PRESCRIPTION_EXPIRED",
            "The prescription validity period has ended.",
            evaluated_at.isoformat(),
            f"< {as_utc(prescription.valid_until).isoformat()}",
        ))
    if device.status in {"maintenance", "retired"}:
        issues.append(ReadinessIssue(
            "DEVICE_NOT_READY",
            "The device lifecycle status prevents a session.",
            device.status,
            "available or assigned",
        ))
    if device.connectivity != "online":
        issues.append(ReadinessIssue(
            "DEVICE_NOT_CONNECTED",
            "The stored device connectivity state is not online.",
            device.connectivity,
            "online",
        ))
    if device.calibration_due_at is None:
        issues.append(ReadinessIssue(
            "CALIBRATION_MISSING",
            "No calibration-validity timestamp is recorded for the device.",
            "missing",
            "future calibration_due_at",
        ))
    elif as_utc(device.calibration_due_at) <= evaluated_at:
        issues.append(ReadinessIssue(
            "CALIBRATION_EXPIRED",
            "The recorded device calibration validity has ended.",
            as_utc(device.calibration_due_at).isoformat(),
            f"> {evaluated_at.isoformat()}",
        ))

    conflict_query = select(TherapySession).where(
        TherapySession.status == "running",
        or_(
            TherapySession.device_id == device.id,
            TherapySession.patient_id == patient.id,
        ),
    )
    if exclude_session_id:
        conflict_query = conflict_query.where(TherapySession.id != exclude_session_id)
    conflict = db.scalar(conflict_query.limit(1))
    if conflict is not None:
        issues.append(ReadinessIssue(
            "ACTIVE_SESSION_CONFLICT",
            "Another running session uses this patient or device.",
            conflict.id,
            "no conflicting active session",
        ))
    return issues
