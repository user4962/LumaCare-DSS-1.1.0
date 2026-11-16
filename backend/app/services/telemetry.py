from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..database import utcnow
from ..models import Alert, DecisionRecord, Device, Patient, Prescription, TelemetrySample, TherapySession
from ..schemas import ActorContext, TelemetryIn
from .audit import add_audit_event
from .decision_adapter import DecisionEngineAdapter
from .readiness import as_utc, assess_readiness


@dataclass(slots=True)
class IngestionResult:
    telemetry: TelemetrySample
    decision: DecisionRecord
    alerts: list[Alert]
    session_status: str


class IngestionError(ValueError):
    pass


def ingest_telemetry(
    db: Session,
    *,
    session: TherapySession,
    payload: TelemetryIn,
    actor: ActorContext,
    adapter: DecisionEngineAdapter,
    future_tolerance_seconds: float = 5.0,
) -> IngestionResult:
    if session.status != "running":
        raise IngestionError("Telemetry is accepted only while the session is running")

    patient = db.get(Patient, session.patient_id)
    device = db.get(Device, session.device_id)
    prescription = db.get(Prescription, session.prescription_id)
    if patient is None or device is None or prescription is None:
        raise IngestionError("Session references are incomplete")

    now = utcnow()
    captured_at = as_utc(payload.captured_at or now)
    if captured_at > now + timedelta(seconds=future_tolerance_seconds):
        raise IngestionError(
            f"Telemetry timestamp exceeds the {future_tolerance_seconds:g}-second future tolerance"
        )
    if session.started_at is not None and captured_at < as_utc(session.started_at):
        raise IngestionError("Telemetry timestamp precedes the session start")

    previous = db.scalar(
        select(TelemetrySample)
        .where(TelemetrySample.session_id == session.id)
        .order_by(desc(TelemetrySample.sequence))
        .limit(1)
    )
    expected_sequence = 0 if previous is None else previous.sequence + 1
    sequence = expected_sequence if payload.sequence is None else payload.sequence
    if sequence != expected_sequence:
        raise IngestionError(
            f"Telemetry sequence must be exactly {expected_sequence}; received {sequence}"
        )
    if previous is not None:
        if captured_at <= as_utc(previous.captured_at):
            raise IngestionError("Telemetry timestamps must increase strictly")
        if payload.cumulative_dose_j_cm2 < previous.cumulative_dose_j_cm2:
            raise IngestionError("Cumulative dose must be monotonic non-decreasing")

    readiness_issues = assess_readiness(
        db,
        patient=patient,
        device=device,
        prescription=prescription,
        exclude_session_id=session.id,
        at=now,
    )
    sample = TelemetrySample(
        session_id=session.id,
        sequence=sequence,
        captured_at=captured_at,
        wavelength_nm=payload.wavelength_nm,
        irradiance_mw_cm2=payload.irradiance_mw_cm2,
        cumulative_dose_j_cm2=payload.cumulative_dose_j_cm2,
        skin_temperature_c=payload.skin_temperature_c,
        spo2_percent=payload.spo2_percent,
        contact_detected=payload.contact_detected,
        battery_percent=payload.battery_percent,
        signal_quality=payload.signal_quality,
        raw_payload=payload.raw_payload,
    )
    db.add(sample)
    db.flush()

    outcome = adapter.evaluate(
        patient=patient,
        device=device,
        prescription=prescription,
        session=session,
        telemetry=sample,
        readiness_issues=readiness_issues,
        now=now,
    )
    decision = DecisionRecord(
        session_id=session.id,
        telemetry_sample_id=sample.id,
        action=outcome.action,
        risk_level=outcome.risk_level,
        risk_score=outcome.risk_score,
        confidence=outcome.confidence,
        explanation=outcome.explanation,
        reason_codes=outcome.reason_codes,
        fired_rules=outcome.fired_rules,
        recommended_irradiance_mw_cm2=outcome.recommended_irradiance_mw_cm2,
        recommended_duration_seconds=outcome.recommended_duration_seconds,
        estimated_additional_dose_j_cm2=outcome.estimated_additional_dose_j_cm2,
        engine_version=outcome.engine_version,
        protocol_version=prescription.protocol_version,
        research_use_only=True,
    )
    db.add(decision)

    session.delivered_dose_j_cm2 = payload.cumulative_dose_j_cm2
    device.last_seen_at = sample.captured_at
    alerts: list[Alert] = []
    if outcome.action == "HOLD":
        session.status = "safety_hold"
        session.stop_reason = "research_safety_rule"
        session.ended_at = utcnow()
        alert = Alert(
            session_id=session.id,
            patient_id=session.patient_id,
            severity="critical" if outcome.risk_level == "critical" else "high",
            code=outcome.reason_codes[0] if outcome.reason_codes else "RESEARCH_SAFETY_HOLD",
            message=outcome.explanation,
        )
        db.add(alert)
        alerts.append(alert)
    elif outcome.action == "COMPLETE":
        # Dose completion ends the session without a safety alert.
        completion_reason = (
            "target_dose_delivered"
            if "TARGET_DOSE_DELIVERED" in outcome.reason_codes
            else "dose_allowance_reached"
        )
        session.status = "completed"
        session.stop_reason = completion_reason
        session.ended_at = now
        add_audit_event(
            db,
            actor,
            event_type="session.completed",
            entity_type="therapy_session",
            entity_id=session.id,
            details={"reason": completion_reason, "reason_codes": outcome.reason_codes},
        )
    elif session.started_at is not None and (
        captured_at - as_utc(session.started_at)
    ).total_seconds() >= session.planned_duration_seconds:
        session.status = "completed"
        session.stop_reason = "planned_duration_elapsed"
        session.ended_at = now
        add_audit_event(
            db,
            actor,
            event_type="session.completed",
            entity_type="therapy_session",
            entity_id=session.id,
            details={"reason": "planned_duration_elapsed"},
        )

    add_audit_event(
        db,
        actor,
        event_type="telemetry.decision_recorded",
        entity_type="therapy_session",
        entity_id=session.id,
        details={
            "sequence": sequence,
            "decision_action": outcome.action,
            "research_use_only": True,
        },
    )
    db.commit()
    db.refresh(sample)
    db.refresh(decision)
    for alert in alerts:
        db.refresh(alert)
    return IngestionResult(sample, decision, alerts, session.status)
