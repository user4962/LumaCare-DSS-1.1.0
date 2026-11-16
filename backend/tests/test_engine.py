"""Boundary and determinism tests for the light-therapy decision engine."""

from __future__ import annotations

import unittest

from app.engine import (
    DecisionEngine,
    EngineConfig,
    PatientProfile,
    Prescription,
    RuleSeverity,
    SafetyState,
    Telemetry,
)


class DecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DecisionEngine()
        self.patient = PatientProfile(patient_id="P-001", age_years=42)
        self.prescription = Prescription(
            prescription_id="RX-001",
            target_irradiance_mw_cm2=20.0,
            target_duration_seconds=100.0,
            max_irradiance_mw_cm2=25.0,
            max_duration_seconds=180.0,
            max_session_dose_j_cm2=5.0,
            max_cumulative_dose_j_cm2=50.0,
        )
        self.telemetry = Telemetry(
            skin_temperature_c=36.5,
            spo2_percent=98.0,
            pain_score=0,
            adverse_event_detected=False,
            device_connected=True,
            calibration_valid=True,
            data_age_seconds=5.0,
            cumulative_dose_j_cm2=10.0,
            session_dose_j_cm2=0.0,
        )

    def telemetry_with(self, **changes: object) -> Telemetry:
        values = {
            "skin_temperature_c": self.telemetry.skin_temperature_c,
            "spo2_percent": self.telemetry.spo2_percent,
            "pain_score": self.telemetry.pain_score,
            "adverse_event_detected": self.telemetry.adverse_event_detected,
            "device_connected": self.telemetry.device_connected,
            "calibration_valid": self.telemetry.calibration_valid,
            "data_age_seconds": self.telemetry.data_age_seconds,
            "cumulative_dose_j_cm2": self.telemetry.cumulative_dose_j_cm2,
            "session_dose_j_cm2": self.telemetry.session_dose_j_cm2,
            "contact_detected": self.telemetry.contact_detected,
        }
        values.update(changes)
        return Telemetry(**values)  # type: ignore[arg-type]

    def test_nominal_snapshot_is_allowed_without_setpoint_change(self) -> None:
        decision = self.engine.evaluate(self.patient, self.prescription, self.telemetry)

        self.assertEqual(decision.state, SafetyState.ALLOW)
        self.assertEqual(decision.recommended_irradiance_mw_cm2, 20.0)
        self.assertEqual(decision.recommended_duration_seconds, 100.0)
        self.assertEqual(decision.estimated_additional_dose_j_cm2, 2.0)
        self.assertEqual(decision.fired_rules, ())
        self.assertEqual(decision.confidence, 1.0)

    def test_thermal_warning_continuously_reduces_irradiance(self) -> None:
        decision = self.engine.evaluate(
            self.patient,
            self.prescription,
            self.telemetry_with(skin_temperature_c=40.0),
        )

        self.assertEqual(decision.state, SafetyState.ADJUST)
        self.assertAlmostEqual(decision.recommended_irradiance_mw_cm2, 14.0)
        self.assertEqual(decision.recommended_duration_seconds, 100.0)
        self.assertIn("THERMAL_WARNING", [rule.rule_id for rule in decision.fired_rules])

    def test_skin_temperature_at_hard_limit_holds(self) -> None:
        decision = self.engine.evaluate(
            self.patient,
            self.prescription,
            self.telemetry_with(skin_temperature_c=41.0),
        )

        self.assert_hold(decision, "SKIN_TEMPERATURE_HIGH")

    def test_spo2_at_lower_boundary_holds(self) -> None:
        decision = self.engine.evaluate(
            self.patient,
            self.prescription,
            self.telemetry_with(spo2_percent=90.0),
        )

        self.assert_hold(decision, "SPO2_CRITICAL")

    def test_spo2_inside_warning_zone_shortens_duration(self) -> None:
        decision = self.engine.evaluate(
            self.patient,
            self.prescription,
            self.telemetry_with(spo2_percent=92.0),
        )

        self.assertEqual(decision.state, SafetyState.ADJUST)
        self.assertAlmostEqual(decision.recommended_duration_seconds, 72.5)
        self.assertIn("SPO2_WARNING", [rule.rule_id for rule in decision.fired_rules])

    def test_adverse_event_and_severe_pain_are_both_explained(self) -> None:
        decision = self.engine.evaluate(
            self.patient,
            self.prescription,
            self.telemetry_with(adverse_event_detected=True, pain_score=7),
        )

        self.assert_hold(decision, "ADVERSE_EVENT")
        self.assertIn("PAIN_SEVERE", [rule.rule_id for rule in decision.fired_rules])

    def test_connectivity_and_calibration_are_hard_interlocks(self) -> None:
        for field, rule_id in (
            ("device_connected", "DEVICE_DISCONNECTED"),
            ("contact_detected", "APPLICATOR_CONTACT_LOST"),
            ("calibration_valid", "CALIBRATION_INVALID"),
        ):
            with self.subTest(field=field):
                decision = self.engine.evaluate(
                    self.patient,
                    self.prescription,
                    self.telemetry_with(**{field: False}),
                )
                self.assert_hold(decision, rule_id)

    def test_freshness_warning_and_exact_hold_boundary(self) -> None:
        warning = self.engine.evaluate(
            self.patient,
            self.prescription,
            self.telemetry_with(data_age_seconds=75.0),
        )
        boundary = self.engine.evaluate(
            self.patient,
            self.prescription,
            self.telemetry_with(data_age_seconds=120.0),
        )

        self.assertEqual(warning.state, SafetyState.ADJUST)
        self.assertIn("TELEMETRY_AGE_WARNING", [r.rule_id for r in warning.fired_rules])
        self.assert_hold(boundary, "TELEMETRY_STALE")

    def test_exhausted_cumulative_dose_completes(self) -> None:
        decision = self.engine.evaluate(
            self.patient,
            self.prescription,
            self.telemetry_with(cumulative_dose_j_cm2=50.0),
        )

        self.assert_complete(decision, "CUMULATIVE_DOSE_EXHAUSTED")

    def test_remaining_session_dose_caps_duration_without_overshoot(self) -> None:
        telemetry = self.telemetry_with(
            cumulative_dose_j_cm2=14.8,
            session_dose_j_cm2=4.8,
        )
        decision = self.engine.evaluate(self.patient, self.prescription, telemetry)

        self.assertEqual(decision.state, SafetyState.ADJUST)
        self.assertLessEqual(decision.estimated_additional_dose_j_cm2, 0.2)
        self.assertIn("DOSE_HEADROOM_CAP", [rule.rule_id for rule in decision.fired_rules])

    def test_dose_headroom_below_output_resolution_completes(self) -> None:
        telemetry = self.telemetry_with(cumulative_dose_j_cm2=49.999999)
        decision = self.engine.evaluate(self.patient, self.prescription, telemetry)

        self.assert_complete(decision, "SETPOINT_BELOW_OUTPUT_RESOLUTION")

    def test_final_dose_guard_cannot_publish_zero_duration_adjustment(self) -> None:
        telemetry = self.telemetry_with(cumulative_dose_j_cm2=49.99998)
        decision = self.engine.evaluate(self.patient, self.prescription, telemetry)

        self.assert_complete(decision, "SETPOINT_BELOW_OUTPUT_RESOLUTION")

    def test_safety_interlock_takes_precedence_over_completion(self) -> None:
        telemetry = self.telemetry_with(cumulative_dose_j_cm2=50.0, contact_detected=False)
        decision = self.engine.evaluate(self.patient, self.prescription, telemetry)

        self.assert_hold(decision, "APPLICATOR_CONTACT_LOST")
        self.assertIn("CUMULATIVE_DOSE_EXHAUSTED", [r.rule_id for r in decision.fired_rules])
        self.assertEqual(decision.risk_score, 1.0)

    def test_completion_carries_no_escalation(self) -> None:
        telemetry = self.telemetry_with(cumulative_dose_j_cm2=10.0, session_dose_j_cm2=5.0)
        decision = self.engine.evaluate(self.patient, self.prescription, telemetry)

        self.assert_complete(decision, "SESSION_DOSE_EXHAUSTED")
        self.assertEqual(decision.risk_score, 0.0)
        self.assertEqual(decision.confidence, 1.0)

    def test_quantization_note_does_not_change_indices_of_an_adjustment(self) -> None:
        decision = self.engine.evaluate(
            self.patient,
            self.prescription,
            self.telemetry_with(data_age_seconds=60.0),
        )

        self.assertEqual(decision.state, SafetyState.ADJUST)
        rules = {rule.rule_id: rule for rule in decision.fired_rules}
        self.assertEqual(rules["OUTPUT_RESOLUTION_FLOOR"].severity, RuleSeverity.INFO)
        self.assertEqual(decision.risk_score, 0.5)
        self.assertEqual(decision.confidence, 0.833)

    def test_fractional_maxima_are_never_exceeded_by_quantization(self) -> None:
        prescription = Prescription(
            prescription_id="RX-FRACTIONAL",
            target_irradiance_mw_cm2=1.2346,
            target_duration_seconds=10.2346,
            max_irradiance_mw_cm2=1.2346,
            max_duration_seconds=10.2346,
            max_session_dose_j_cm2=5.0,
            max_cumulative_dose_j_cm2=50.0,
        )
        decision = self.engine.evaluate(self.patient, prescription, self.telemetry)

        self.assertEqual(decision.state, SafetyState.ALLOW)
        self.assertEqual(decision.risk_score, 0.0)
        self.assertEqual(decision.confidence, 1.0)
        self.assertEqual(decision.recommended_irradiance_mw_cm2, 1.234)
        self.assertEqual(decision.recommended_duration_seconds, 10.234)
        self.assertLessEqual(
            decision.recommended_irradiance_mw_cm2,
            prescription.max_irradiance_mw_cm2,
        )
        self.assertLessEqual(
            decision.recommended_duration_seconds,
            prescription.max_duration_seconds,
        )
        self.assertIn("OUTPUT_RESOLUTION_FLOOR", [r.rule_id for r in decision.fired_rules])

    def test_clinician_assessed_photosensitivity_is_explainable(self) -> None:
        patient = PatientProfile(
            patient_id="P-002",
            age_years=30,
            photosensitivity_risk=0.5,
        )
        decision = self.engine.evaluate(patient, self.prescription, self.telemetry)

        self.assertEqual(decision.state, SafetyState.ADJUST)
        self.assertAlmostEqual(decision.recommended_irradiance_mw_cm2, 15.5)
        self.assertIn("PHOTOSENSITIVITY_RISK", [r.rule_id for r in decision.fired_rules])

    def test_subthreshold_fuzzy_membership_does_not_silently_change_setpoint(self) -> None:
        patient = PatientProfile(
            patient_id="P-003",
            age_years=30,
            photosensitivity_risk=0.005,
        )
        decision = self.engine.evaluate(patient, self.prescription, self.telemetry)

        self.assertEqual(decision.state, SafetyState.ALLOW)
        self.assertEqual(decision.recommended_irradiance_mw_cm2, 20.0)
        self.assertEqual(decision.fired_rules, ())

    def test_equal_inputs_produce_equal_serialized_outputs(self) -> None:
        first = self.engine.evaluate(self.patient, self.prescription, self.telemetry).to_dict()
        second = self.engine.evaluate(self.patient, self.prescription, self.telemetry).to_dict()

        self.assertEqual(first, second)
        self.assertEqual(first["state"], "ALLOW")

    def test_invalid_telemetry_is_rejected_at_the_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "session_dose_j_cm2"):
            self.telemetry_with(cumulative_dose_j_cm2=1.0, session_dose_j_cm2=2.0)

        with self.assertRaisesRegex(TypeError, "device_connected"):
            self.telemetry_with(device_connected="yes")

        with self.assertRaisesRegex(TypeError, "skin_temperature_c"):
            self.telemetry_with(skin_temperature_c=True)

        with self.assertRaisesRegex(TypeError, "target_irradiance_mw_cm2"):
            Prescription(
                prescription_id="RX-INVALID",
                target_irradiance_mw_cm2="20",  # type: ignore[arg-type]
                target_duration_seconds=100.0,
                max_irradiance_mw_cm2=25.0,
                max_duration_seconds=180.0,
                max_session_dose_j_cm2=5.0,
                max_cumulative_dose_j_cm2=50.0,
            )

    def test_incompatible_or_disabled_fuzzy_configuration_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "fuzzy_activation_threshold"):
            EngineConfig(fuzzy_activation_threshold=1.0)

        incompatible_oxygen = DecisionEngine(EngineConfig(spo2_hold_margin_percent=95.0))
        with self.assertRaisesRegex(ValueError, "spo2_hold_margin_percent"):
            incompatible_oxygen.evaluate(self.patient, self.prescription, self.telemetry)

        patient = PatientProfile(patient_id="P-LOW-PAIN", age_years=42, pain_hold_score=3)
        with self.assertRaisesRegex(ValueError, "pain_adjust_score"):
            self.engine.evaluate(patient, self.prescription, self.telemetry)

    def test_recommended_setpoints_always_satisfy_output_invariants(self) -> None:
        temperatures = (35.0, 39.0, 40.5, 41.0)
        saturations = (90.0, 92.0, 94.0, 98.0)
        pain_scores = (0, 4, 6, 7)
        dose_values = (10.0, 45.0, 49.0, 49.99998, 50.0)
        for temperature in temperatures:
            for saturation in saturations:
                for pain in pain_scores:
                    for cumulative_dose in dose_values:
                        with self.subTest(
                            temperature=temperature,
                            saturation=saturation,
                            pain=pain,
                            cumulative_dose=cumulative_dose,
                        ):
                            decision = self.engine.evaluate(
                                self.patient,
                                self.prescription,
                                self.telemetry_with(
                                    skin_temperature_c=temperature,
                                    spo2_percent=saturation,
                                    pain_score=pain,
                                    cumulative_dose_j_cm2=cumulative_dose,
                                ),
                            )
                            if decision.state in (SafetyState.HOLD, SafetyState.COMPLETE):
                                self.assertEqual(decision.recommended_irradiance_mw_cm2, 0.0)
                                self.assertEqual(decision.recommended_duration_seconds, 0.0)
                                continue
                            self.assertGreater(decision.recommended_irradiance_mw_cm2, 0.0)
                            self.assertGreater(decision.recommended_duration_seconds, 0.0)
                            self.assertLessEqual(
                                decision.recommended_irradiance_mw_cm2,
                                self.prescription.max_irradiance_mw_cm2,
                            )
                            self.assertLessEqual(
                                decision.recommended_duration_seconds,
                                self.prescription.max_duration_seconds,
                            )
                            actual_dose = (
                                decision.recommended_irradiance_mw_cm2
                                * decision.recommended_duration_seconds
                                / 1000.0
                            )
                            self.assertLessEqual(
                                actual_dose,
                                self.prescription.max_cumulative_dose_j_cm2 - cumulative_dose + 1e-12,
                            )
                            self.assertAlmostEqual(
                                decision.estimated_additional_dose_j_cm2,
                                actual_dose,
                                places=12,
                            )

    def assert_complete(self, decision: object, expected_rule_id: str) -> None:
        self.assertEqual(decision.state, SafetyState.COMPLETE)  # type: ignore[attr-defined]
        self.assertEqual(decision.recommended_irradiance_mw_cm2, 0.0)  # type: ignore[attr-defined]
        self.assertEqual(decision.recommended_duration_seconds, 0.0)  # type: ignore[attr-defined]
        self.assertEqual(decision.estimated_additional_dose_j_cm2, 0.0)  # type: ignore[attr-defined]
        rule_ids = [rule.rule_id for rule in decision.fired_rules]  # type: ignore[attr-defined]
        self.assertIn(expected_rule_id, rule_ids)

    def assert_hold(self, decision: object, expected_rule_id: str) -> None:
        self.assertEqual(decision.state, SafetyState.HOLD)  # type: ignore[attr-defined]
        self.assertEqual(decision.recommended_irradiance_mw_cm2, 0.0)  # type: ignore[attr-defined]
        self.assertEqual(decision.recommended_duration_seconds, 0.0)  # type: ignore[attr-defined]
        rule_ids = [rule.rule_id for rule in decision.fired_rules]  # type: ignore[attr-defined]
        self.assertIn(expected_rule_id, rule_ids)


if __name__ == "__main__":
    unittest.main()
