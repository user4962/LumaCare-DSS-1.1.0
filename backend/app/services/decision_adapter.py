from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from app.engine import DecisionEngine, PatientProfile
from app.engine import Prescription as EnginePrescription
from app.engine import Telemetry as EngineTelemetry

from ..models import Device, Patient, Prescription, TelemetrySample, TherapySession
from .readiness import ReadinessIssue


ENGINE_VERSION = "research-engine-1.1"

# Remaining target dose at or below this value is treated as delivered.
TARGET_DOSE_TOLERANCE_J_CM2 = 1e-9
# Minimum engine target duration when a positive target dose remains.
MIN_TARGET_DURATION_SECONDS = 0.001
# Factor applied to the irradiance envelope before a measured value forces HOLD.
HARD_IRRADIANCE_FACTOR = 1.25
# Strength assigned to the measured-irradiance tolerance rule.
TOLERANCE_RULE_STRENGTH = 0.55


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    action: str
    risk_level: str
    risk_score: float
    confidence: float
    explanation: str
    reason_codes: list[str]
    fired_rules: list[dict[str, Any]]
    recommended_irradiance_mw_cm2: float
    recommended_duration_seconds: float
    estimated_additional_dose_j_cm2: float
    engine_version: str = ENGINE_VERSION


def _age_years(birth_date: date, today: date) -> int:
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class DecisionEngineAdapter:
    """Translate persistence entities into the engine's stable public contract."""

    def __init__(self) -> None:
        self._engine = DecisionEngine()

    def evaluate(
        self,
        *,
        patient: Patient,
        device: Device,
        prescription: Prescription,
        session: TherapySession,
        telemetry: TelemetrySample,
        readiness_issues: list[ReadinessIssue] | None = None,
        now: datetime | None = None,
    ) -> DecisionOutcome:
        evaluated_at = _utc(now or datetime.now(timezone.utc))
        captured_at = _utc(telemetry.captured_at)
        data_age_seconds = max(0.0, (evaluated_at - captured_at).total_seconds())
        calibration_valid = (
            device.calibration_due_at is not None
            and _utc(device.calibration_due_at) > evaluated_at
        )

        engine_patient = PatientProfile(
            patient_id=patient.id,
            age_years=_age_years(patient.date_of_birth, evaluated_at.date()),
            photosensitivity_risk=0.0,
            thermal_sensitivity=0.0,
            max_skin_temperature_c=prescription.max_skin_temperature_c,
            min_spo2_percent=prescription.min_spo2_percent,
        )
        maximum_irradiance = prescription.target_irradiance_mw_cm2 * (
            1.0 + prescription.irradiance_tolerance_percent / 100.0
        )
        remaining_duration = min(
            prescription.max_duration_seconds,
            session.planned_duration_seconds,
        )
        remaining_target_dose = prescription.target_dose_j_cm2 - telemetry.cumulative_dose_j_cm2
        target_dose_delivered = remaining_target_dose <= TARGET_DOSE_TOLERANCE_J_CM2
        dose_limited_duration = (
            max(0.0, remaining_target_dose) * 1000.0 / prescription.target_irradiance_mw_cm2
        )
        engine_prescription = EnginePrescription(
            prescription_id=prescription.id,
            target_irradiance_mw_cm2=prescription.target_irradiance_mw_cm2,
            target_duration_seconds=float(
                max(
                    MIN_TARGET_DURATION_SECONDS,
                    min(remaining_duration, session.planned_duration_seconds, dose_limited_duration),
                )
            ),
            max_irradiance_mw_cm2=maximum_irradiance,
            max_duration_seconds=float(prescription.max_duration_seconds),
            max_session_dose_j_cm2=prescription.max_session_dose_j_cm2,
            max_cumulative_dose_j_cm2=prescription.max_session_dose_j_cm2,
        )
        engine_telemetry = EngineTelemetry(
            skin_temperature_c=telemetry.skin_temperature_c,
            spo2_percent=telemetry.spo2_percent,
            pain_score=0,
            adverse_event_detected=False,
            device_connected=device.connectivity == "online",
            calibration_valid=calibration_valid,
            data_age_seconds=min(data_age_seconds, 86_400.0),
            cumulative_dose_j_cm2=telemetry.cumulative_dose_j_cm2,
            session_dose_j_cm2=telemetry.cumulative_dose_j_cm2,
            contact_detected=telemetry.contact_detected,
        )
        raw = self._engine.evaluate(engine_patient, engine_prescription, engine_telemetry).to_dict()

        action = str(raw["state"])
        risk_score = float(raw["risk_score"])
        confidence = float(raw["confidence"])
        reasons = [str(reason) for reason in raw["reasons"]]
        fired_rules = [dict(rule) for rule in raw["fired_rules"]]
        reason_codes = [str(rule["rule_id"]) for rule in fired_rules]
        recommended_irradiance = float(raw["recommended_irradiance_mw_cm2"])
        # Durations keep the engine resolution (three decimals) instead of
        # being truncated to whole seconds.
        recommended_duration = max(0.0, float(raw["recommended_duration_seconds"]))
        estimated_dose = float(raw["estimated_additional_dose_j_cm2"])

        if target_dose_delivered and action != "HOLD":
            action = "COMPLETE"
            risk_score = 0.0
            confidence = 1.0
            recommended_irradiance = 0.0
            recommended_duration = 0.0
            estimated_dose = 0.0
            completion_rule = {
                "rule_id": "TARGET_DOSE_DELIVERED",
                "severity": "COMPLETE",
                "strength": 1.0,
                "message": "The prescribed target dose has been delivered.",
                "observed": f"{telemetry.cumulative_dose_j_cm2:.6g} J/cm2",
                "threshold": f">= {prescription.target_dose_j_cm2:.6g} J/cm2",
            }
            fired_rules.append(completion_rule)
            reason_codes.append(completion_rule["rule_id"])
            reasons.append(str(completion_rule["message"]))

        wavelength_delta = abs(telemetry.wavelength_nm - prescription.target_wavelength_nm)
        if wavelength_delta > prescription.wavelength_tolerance_nm:
            action = "HOLD"
            risk_score = 1.0
            confidence = 1.0
            recommended_irradiance = 0.0
            recommended_duration = 0.0
            estimated_dose = 0.0
            wavelength_rule = {
                "rule_id": "OBSERVED_WAVELENGTH_MISMATCH",
                "severity": "HOLD",
                "strength": 1.0,
                "message": "Observed wavelength is outside the research protocol tolerance.",
                "observed": f"{telemetry.wavelength_nm:.6g} nm",
                "threshold": (
                    f"{prescription.target_wavelength_nm - prescription.wavelength_tolerance_nm:.6g}"
                    f" to {prescription.target_wavelength_nm + prescription.wavelength_tolerance_nm:.6g} nm"
                ),
            }
            fired_rules.append(wavelength_rule)
            reason_codes.append(wavelength_rule["rule_id"])
            reasons.append(str(wavelength_rule["message"]))

        # The observed-output gate belongs to the adapter because the pure engine
        # evaluates prescribed setpoints and intentionally omits measured irradiance.
        if telemetry.irradiance_mw_cm2 > maximum_irradiance * HARD_IRRADIANCE_FACTOR:
            action = "HOLD"
            risk_score = 1.0
            confidence = 1.0
            recommended_irradiance = 0.0
            recommended_duration = 0.0
            estimated_dose = 0.0
            observed_rule = {
                "rule_id": "OBSERVED_IRRADIANCE_HARD_LIMIT",
                "severity": "HOLD",
                "strength": 1.0,
                "message": "Observed irradiance exceeded the research protocol hard limit.",
                "observed": f"{telemetry.irradiance_mw_cm2:.6g} mW/cm2",
                "threshold": f"<= {maximum_irradiance * HARD_IRRADIANCE_FACTOR:.6g} mW/cm2",
            }
            fired_rules.append(observed_rule)
            reason_codes.append(observed_rule["rule_id"])
            reasons.append("Observed irradiance exceeded the research protocol hard limit.")
        elif telemetry.irradiance_mw_cm2 > maximum_irradiance and action == "ALLOW":
            # Indices follow the engine definitions: the tolerance rule is the
            # only acting rule, so risk equals its strength and confidence is
            # 0.75 + 0.25 * strength.
            action = "ADJUST"
            risk_score = max(0.5, TOLERANCE_RULE_STRENGTH)
            confidence = 0.75 + 0.25 * TOLERANCE_RULE_STRENGTH
            recommended_irradiance = prescription.target_irradiance_mw_cm2
            observed_rule = {
                "rule_id": "OBSERVED_IRRADIANCE_TOLERANCE",
                "severity": "ADJUST",
                "strength": TOLERANCE_RULE_STRENGTH,
                "message": "Observed irradiance exceeded the configured research tolerance.",
                "observed": f"{telemetry.irradiance_mw_cm2:.6g} mW/cm2",
                "threshold": f"<= {maximum_irradiance:.6g} mW/cm2",
            }
            fired_rules.append(observed_rule)
            reason_codes.append(observed_rule["rule_id"])
            reasons.append("Observed irradiance exceeded the configured research tolerance.")

        for issue in readiness_issues or []:
            if issue.code not in reason_codes:
                fired_rules.append(issue.as_rule())
                reason_codes.append(issue.code)
                reasons.append(issue.message)
            action = "HOLD"
            risk_score = 1.0
            confidence = 1.0
            recommended_irradiance = 0.0
            recommended_duration = 0.0
            estimated_dose = 0.0

        risk_level = self._risk_level(action, risk_score)
        return DecisionOutcome(
            action=action,
            risk_level=risk_level,
            risk_score=round(risk_score, 3),
            confidence=round(confidence, 3),
            explanation=" ".join(reasons),
            reason_codes=list(dict.fromkeys(reason_codes)),
            fired_rules=fired_rules,
            recommended_irradiance_mw_cm2=round(recommended_irradiance, 3),
            recommended_duration_seconds=round(recommended_duration, 3),
            estimated_additional_dose_j_cm2=round(estimated_dose, 6),
        )

    @staticmethod
    def _risk_level(action: str, score: float) -> str:
        if action == "HOLD":
            return "critical"
        if action == "ADJUST" and score >= 0.75:
            return "high"
        if action == "ADJUST":
            return "moderate"
        return "low"
