"""Deterministic rule-based and fuzzy decision support for light therapy."""

from __future__ import annotations

from math import floor

from .models import (
    EngineConfig,
    FiredRule,
    PatientProfile,
    Prescription,
    RuleSeverity,
    SafetyDecision,
    SafetyState,
    Telemetry,
)
from .rules import clamp, falling_membership, fired_rule, rising_membership


class DecisionEngine:
    """Evaluate a patient, prescription, and telemetry snapshot.

    Crisp rules implement hard interlocks.  Fuzzy memberships within warning
    zones produce continuous reductions to irradiance or duration.  No clock,
    random source, persistence layer, or external service is consulted, so
    equal inputs and configuration always produce equal outputs.
    """

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()

    def evaluate(
        self,
        patient: PatientProfile,
        prescription: Prescription,
        telemetry: Telemetry,
    ) -> SafetyDecision:
        """Return a safe setpoint recommendation with a complete explanation."""

        if self.config.spo2_hold_margin_percent > patient.min_spo2_percent:
            raise ValueError(
                "spo2_hold_margin_percent must not exceed the patient SpO2 clear threshold"
            )
        if self.config.skin_temperature_warning_margin_c >= patient.max_skin_temperature_c:
            raise ValueError(
                "skin_temperature_warning_margin_c must be below the patient temperature limit"
            )
        if self.config.pain_adjust_score >= patient.pain_hold_score:
            raise ValueError("pain_adjust_score must be below the patient pain hold score")

        hard_rules = self._evaluate_hard_rules(patient, prescription, telemetry)
        if any(rule.severity is RuleSeverity.HOLD for rule in hard_rules):
            return self._zero_output_decision(SafetyState.HOLD, hard_rules)
        if hard_rules:
            return self._zero_output_decision(SafetyState.COMPLETE, hard_rules)

        irradiance = prescription.target_irradiance_mw_cm2
        duration = prescription.target_duration_seconds
        rules: list[FiredRule] = []

        if irradiance > prescription.max_irradiance_mw_cm2:
            rules.append(
                fired_rule(
                    "RX_IRRADIANCE_CAP",
                    RuleSeverity.ADJUST,
                    1.0,
                    "Target irradiance exceeds the prescription ceiling.",
                    f"{irradiance:.6g} mW/cm2",
                    f"<= {prescription.max_irradiance_mw_cm2:.6g} mW/cm2",
                )
            )
            irradiance = prescription.max_irradiance_mw_cm2

        if duration > prescription.max_duration_seconds:
            rules.append(
                fired_rule(
                    "RX_DURATION_CAP",
                    RuleSeverity.ADJUST,
                    1.0,
                    "Target duration exceeds the prescription ceiling.",
                    f"{duration:.6g} s",
                    f"<= {prescription.max_duration_seconds:.6g} s",
                )
            )
            duration = prescription.max_duration_seconds

        fuzzy_rules, irradiance_factor, duration_factor, fuzzy_risk = self._evaluate_fuzzy_rules(
            patient, prescription, telemetry, irradiance, duration
        )
        rules.extend(fuzzy_rules)
        irradiance *= irradiance_factor
        duration *= duration_factor

        remaining_session = prescription.max_session_dose_j_cm2 - telemetry.session_dose_j_cm2
        remaining_cumulative = (
            prescription.max_cumulative_dose_j_cm2 - telemetry.cumulative_dose_j_cm2
        )
        allowed_dose = min(remaining_session, remaining_cumulative)
        estimated_dose = self._dose(irradiance, duration)

        if estimated_dose > allowed_dose:
            rules.append(
                fired_rule(
                    "DOSE_HEADROOM_CAP",
                    RuleSeverity.ADJUST,
                    1.0,
                    "Recommended duration was capped by the remaining dose allowance.",
                    f"requested {estimated_dose:.6g} J/cm2",
                    f"<= {allowed_dose:.6g} J/cm2",
                )
            )
            duration = self._floor_to_precision(
                allowed_dose * 1000.0 / irradiance,
                self.config.output_precision,
            )
            estimated_dose = self._dose(irradiance, duration)

        precision = self.config.output_precision
        unquantized_irradiance = irradiance
        unquantized_duration = duration
        irradiance = self._floor_to_precision(irradiance, precision)
        duration = self._floor_to_precision(duration, precision)
        quantization_tolerance = 10 ** (-(precision + 6))
        if (
            unquantized_irradiance - irradiance > quantization_tolerance
            or unquantized_duration - duration > quantization_tolerance
        ):
            rules.append(
                fired_rule(
                    "OUTPUT_RESOLUTION_FLOOR",
                    RuleSeverity.INFO,
                    1.0,
                    "The recommended setpoint was conservatively quantized to the configured output resolution.",
                    (
                        f"{unquantized_irradiance:.9g} mW/cm2 for "
                        f"{unquantized_duration:.9g} s"
                    ),
                    f"floor to {precision} decimal places",
                )
            )

        # The final guard protects the dose invariant from floating-point error.
        rounded_dose = self._dose(irradiance, duration)
        if rounded_dose > allowed_dose:
            duration = self._floor_to_precision(allowed_dose * 1000.0 / irradiance, precision)
            rounded_dose = self._dose(irradiance, duration)

        if irradiance <= 0.0 or duration <= 0.0:
            rules.append(
                fired_rule(
                    "SETPOINT_BELOW_OUTPUT_RESOLUTION",
                    RuleSeverity.COMPLETE,
                    1.0,
                    "The remaining dose allowance is below the configured output resolution.",
                    f"{irradiance:.6g} mW/cm2 for {duration:.6g} s",
                    f"positive values at {precision} decimal places",
                )
            )
            return self._zero_output_decision(SafetyState.COMPLETE, rules)

        acting_rules = [rule for rule in rules if rule.severity is RuleSeverity.ADJUST]
        state = SafetyState.ADJUST if acting_rules else SafetyState.ALLOW
        max_strength = max((rule.strength for rule in acting_rules), default=0.0)
        # This is an algorithmic escalation index, not a calibrated probability
        # of injury. Deterministic adjustments begin at 0.5; fuzzy warnings may
        # raise the value according to their maximum membership strength.
        # Informational rules (quantization) change neither index.
        risk_score = max(0.5, fuzzy_risk) if acting_rules else 0.0
        confidence = 1.0 if state is SafetyState.ALLOW else 0.75 + 0.25 * max_strength

        reasons = tuple(rule.message for rule in rules)
        if not reasons:
            reasons = ("No hard limit or fuzzy warning zone was activated.",)

        return SafetyDecision(
            state=state,
            recommended_irradiance_mw_cm2=irradiance,
            recommended_duration_seconds=duration,
            estimated_additional_dose_j_cm2=rounded_dose,
            reasons=reasons,
            fired_rules=tuple(rules),
            confidence=round(clamp(confidence), 3),
            risk_score=round(clamp(risk_score), 3),
        )

    def _evaluate_hard_rules(
        self,
        patient: PatientProfile,
        prescription: Prescription,
        telemetry: Telemetry,
    ) -> list[FiredRule]:
        rules: list[FiredRule] = []
        hold_spo2 = patient.min_spo2_percent - self.config.spo2_hold_margin_percent

        if patient.contraindication_present:
            rules.append(
                fired_rule(
                    "PATIENT_CONTRAINDICATION",
                    RuleSeverity.HOLD,
                    1.0,
                    "The patient profile contains an active contraindication.",
                    "present",
                    "absent",
                )
            )
        if telemetry.adverse_event_detected:
            rules.append(
                fired_rule(
                    "ADVERSE_EVENT",
                    RuleSeverity.HOLD,
                    1.0,
                    "An adverse event was reported during treatment.",
                    "detected",
                    "not detected",
                )
            )
        if not telemetry.device_connected:
            rules.append(
                fired_rule(
                    "DEVICE_DISCONNECTED",
                    RuleSeverity.HOLD,
                    1.0,
                    "The device connection is unavailable.",
                    "disconnected",
                    "connected",
                )
            )
        if not telemetry.contact_detected:
            rules.append(
                fired_rule(
                    "APPLICATOR_CONTACT_LOST",
                    RuleSeverity.HOLD,
                    1.0,
                    "Applicator contact with the treatment area is unavailable.",
                    "not detected",
                    "detected",
                )
            )
        if not telemetry.calibration_valid:
            rules.append(
                fired_rule(
                    "CALIBRATION_INVALID",
                    RuleSeverity.HOLD,
                    1.0,
                    "Device calibration is missing, invalid, or expired.",
                    "invalid",
                    "valid",
                )
            )
        if telemetry.data_age_seconds >= self.config.telemetry_hold_age_seconds:
            rules.append(
                fired_rule(
                    "TELEMETRY_STALE",
                    RuleSeverity.HOLD,
                    1.0,
                    "Telemetry age reached the hard freshness limit.",
                    f"{telemetry.data_age_seconds:.6g} s",
                    f"< {self.config.telemetry_hold_age_seconds:.6g} s",
                )
            )
        if telemetry.skin_temperature_c >= patient.max_skin_temperature_c:
            rules.append(
                fired_rule(
                    "SKIN_TEMPERATURE_HIGH",
                    RuleSeverity.HOLD,
                    1.0,
                    "Skin temperature reached the patient-specific hard limit.",
                    f"{telemetry.skin_temperature_c:.6g} C",
                    f"< {patient.max_skin_temperature_c:.6g} C",
                )
            )
        if telemetry.spo2_percent <= hold_spo2:
            rules.append(
                fired_rule(
                    "SPO2_CRITICAL",
                    RuleSeverity.HOLD,
                    1.0,
                    "SpO2 reached the hard lower limit.",
                    f"{telemetry.spo2_percent:.6g}%",
                    f"> {hold_spo2:.6g}%",
                )
            )
        if telemetry.pain_score >= patient.pain_hold_score:
            rules.append(
                fired_rule(
                    "PAIN_SEVERE",
                    RuleSeverity.HOLD,
                    1.0,
                    "Pain reached the patient-specific interruption score.",
                    str(telemetry.pain_score),
                    f"< {patient.pain_hold_score}",
                )
            )
        if telemetry.session_dose_j_cm2 >= prescription.max_session_dose_j_cm2:
            rules.append(
                fired_rule(
                    "SESSION_DOSE_EXHAUSTED",
                    RuleSeverity.COMPLETE,
                    1.0,
                    "The active session has no remaining dose allowance.",
                    f"{telemetry.session_dose_j_cm2:.6g} J/cm2",
                    f"< {prescription.max_session_dose_j_cm2:.6g} J/cm2",
                )
            )
        if telemetry.cumulative_dose_j_cm2 >= prescription.max_cumulative_dose_j_cm2:
            rules.append(
                fired_rule(
                    "CUMULATIVE_DOSE_EXHAUSTED",
                    RuleSeverity.COMPLETE,
                    1.0,
                    "The prescription has no remaining cumulative dose allowance.",
                    f"{telemetry.cumulative_dose_j_cm2:.6g} J/cm2",
                    f"< {prescription.max_cumulative_dose_j_cm2:.6g} J/cm2",
                )
            )
        return rules

    def _evaluate_fuzzy_rules(
        self,
        patient: PatientProfile,
        prescription: Prescription,
        telemetry: Telemetry,
        irradiance: float,
        duration: float,
    ) -> tuple[list[FiredRule], float, float, float]:
        config = self.config
        rules: list[FiredRule] = []
        irradiance_factors = [1.0]
        duration_factors = [1.0]
        strengths: list[float] = []

        temperature_warning = (
            patient.max_skin_temperature_c - config.skin_temperature_warning_margin_c
        )
        temperature = rising_membership(
            telemetry.skin_temperature_c,
            temperature_warning,
            patient.max_skin_temperature_c,
        )
        temperature = self._activate_fuzzy(
            rules,
            strengths,
            "THERMAL_WARNING",
            temperature,
            "Skin temperature is within the thermal warning zone.",
            f"{telemetry.skin_temperature_c:.6g} C",
            f"warning {temperature_warning:.6g} C; hold {patient.max_skin_temperature_c:.6g} C",
        )
        irradiance_factors.append(1.0 - config.temperature_irradiance_reduction * temperature)

        hold_spo2 = patient.min_spo2_percent - config.spo2_hold_margin_percent
        oxygen = falling_membership(telemetry.spo2_percent, hold_spo2, patient.min_spo2_percent)
        oxygen = self._activate_fuzzy(
            rules,
            strengths,
            "SPO2_WARNING",
            oxygen,
            "SpO2 is within the oxygen-saturation warning zone.",
            f"{telemetry.spo2_percent:.6g}%",
            f"hold {hold_spo2:.6g}%; clear {patient.min_spo2_percent:.6g}%",
        )
        duration_factors.append(1.0 - config.oxygen_duration_reduction * oxygen)

        pain_warning_score = min(
            float(config.pain_adjust_score),
            float(patient.pain_hold_score - 1),
        )
        pain = rising_membership(
            float(telemetry.pain_score),
            pain_warning_score,
            float(patient.pain_hold_score),
        )
        pain = self._activate_fuzzy(
            rules,
            strengths,
            "PAIN_WARNING",
            pain,
            "Pain is within the treatment-adjustment zone.",
            str(telemetry.pain_score),
            f"adjust > {pain_warning_score:.6g}; hold >= {patient.pain_hold_score}",
        )
        duration_factors.append(1.0 - config.pain_duration_reduction * pain)

        freshness = rising_membership(
            telemetry.data_age_seconds,
            config.telemetry_warning_age_seconds,
            config.telemetry_hold_age_seconds,
        )
        freshness = self._activate_fuzzy(
            rules,
            strengths,
            "TELEMETRY_AGE_WARNING",
            freshness,
            "Telemetry is within the freshness warning zone.",
            f"{telemetry.data_age_seconds:.6g} s",
            (
                f"warning {config.telemetry_warning_age_seconds:.6g} s; "
                f"hold {config.telemetry_hold_age_seconds:.6g} s"
            ),
        )
        irradiance_factors.append(1.0 - config.freshness_irradiance_reduction * freshness)
        duration_factors.append(1.0 - config.freshness_duration_reduction * freshness)

        photosensitivity = patient.photosensitivity_risk
        photosensitivity = self._activate_fuzzy(
            rules,
            strengths,
            "PHOTOSENSITIVITY_RISK",
            photosensitivity,
            "The clinician-assessed photosensitivity risk requires a lower irradiance.",
            f"{photosensitivity:.6g}",
            "0 (none) to 1 (maximum)",
        )
        irradiance_factors.append(
            1.0 - config.photosensitivity_irradiance_reduction * photosensitivity
        )

        thermal_sensitivity = patient.thermal_sensitivity
        thermal_sensitivity = self._activate_fuzzy(
            rules,
            strengths,
            "THERMAL_SENSITIVITY",
            thermal_sensitivity,
            "The clinician-assessed thermal sensitivity requires a lower irradiance.",
            f"{thermal_sensitivity:.6g}",
            "0 (none) to 1 (maximum)",
        )
        irradiance_factors.append(
            1.0 - config.thermal_sensitivity_irradiance_reduction * thermal_sensitivity
        )

        proposed_dose = self._dose(irradiance, duration)
        projected_session_ratio = (
            telemetry.session_dose_j_cm2 + proposed_dose
        ) / prescription.max_session_dose_j_cm2
        projected_cumulative_ratio = (
            telemetry.cumulative_dose_j_cm2 + proposed_dose
        ) / prescription.max_cumulative_dose_j_cm2
        projected_ratio = max(projected_session_ratio, projected_cumulative_ratio)
        dose_pressure = rising_membership(projected_ratio, config.dose_warning_ratio, 1.0)
        dose_pressure = self._activate_fuzzy(
            rules,
            strengths,
            "DOSE_WARNING",
            dose_pressure,
            "The requested exposure enters the dose-headroom warning zone.",
            f"projected utilization {projected_ratio:.6g}",
            f"warning > {config.dose_warning_ratio:.6g}; full at 1; headroom limit applies above",
        )
        duration_factors.append(1.0 - config.dose_duration_reduction * dose_pressure)

        return (
            rules,
            min(irradiance_factors),
            min(duration_factors),
            max(strengths, default=0.0),
        )

    def _activate_fuzzy(
        self,
        rules: list[FiredRule],
        strengths: list[float],
        rule_id: str,
        strength: float,
        message: str,
        observed: str,
        threshold: str,
    ) -> float:
        if strength <= self.config.fuzzy_activation_threshold:
            return 0.0
        strengths.append(strength)
        rules.append(
            fired_rule(
                rule_id,
                RuleSeverity.ADJUST,
                strength,
                message,
                observed,
                threshold,
            )
        )
        return strength

    def _zero_output_decision(self, state: SafetyState, rules: list[FiredRule]) -> SafetyDecision:
        """Return HOLD or COMPLETE with zero outputs.

        HOLD carries the maximum escalation index.  COMPLETE ends delivery
        because the dose allowance has been used and carries no escalation.
        """

        return SafetyDecision(
            state=state,
            recommended_irradiance_mw_cm2=0.0,
            recommended_duration_seconds=0.0,
            estimated_additional_dose_j_cm2=0.0,
            reasons=tuple(rule.message for rule in rules),
            fired_rules=tuple(rules),
            confidence=1.0,
            risk_score=1.0 if state is SafetyState.HOLD else 0.0,
        )

    @staticmethod
    def _dose(irradiance_mw_cm2: float, duration_seconds: float) -> float:
        return irradiance_mw_cm2 * duration_seconds / 1000.0

    @staticmethod
    def _floor_to_precision(value: float, precision: int) -> float:
        factor = 10**precision
        return floor(max(0.0, value) * factor) / factor
