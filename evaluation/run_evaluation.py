#!/usr/bin/env python3
"""Run deterministic scenario and latency evaluation for the decision engine.

The labels in this harness express software requirements. They are not clinical
ground truth and must not be interpreted as evidence of treatment efficacy.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import statistics
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.engine import (  # noqa: E402
    DecisionEngine,
    PatientProfile,
    Prescription,
    SafetyState,
    Telemetry,
)


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    expected: SafetyState
    patient: PatientProfile
    prescription: Prescription
    telemetry: Telemetry
    requirement: str


EXPECTED_RULES: dict[str, str | None] = {
    "nominal": None,
    "thermal_warning": "THERMAL_WARNING",
    "thermal_limit": "SKIN_TEMPERATURE_HIGH",
    "spo2_warning": "SPO2_WARNING",
    "spo2_limit": "SPO2_CRITICAL",
    "pain_warning": "PAIN_WARNING",
    "pain_limit": "PAIN_SEVERE",
    "adverse_event": "ADVERSE_EVENT",
    "device_disconnect": "DEVICE_DISCONNECTED",
    "contact_loss": "APPLICATOR_CONTACT_LOST",
    "invalid_calibration": "CALIBRATION_INVALID",
    "telemetry_warning": "TELEMETRY_AGE_WARNING",
    "telemetry_stale": "TELEMETRY_STALE",
    "dose_headroom": "DOSE_HEADROOM_CAP",
    "session_dose_exhausted": "SESSION_DOSE_EXHAUSTED",
    "cumulative_dose_exhausted": "CUMULATIVE_DOSE_EXHAUSTED",
    "photosensitivity_risk": "PHOTOSENSITIVITY_RISK",
    "thermal_sensitivity": "THERMAL_SENSITIVITY",
    "prescription_caps": "RX_IRRADIANCE_CAP",
    "fractional_output_resolution": "OUTPUT_RESOLUTION_FLOOR",
    "setpoint_below_resolution": "SETPOINT_BELOW_OUTPUT_RESOLUTION",
    "active_contraindication": "PATIENT_CONTRAINDICATION",
    "simultaneous_faults": "DEVICE_DISCONNECTED",
    "fault_with_exhausted_dose": "APPLICATOR_CONTACT_LOST",
}


def base_inputs() -> tuple[PatientProfile, Prescription, Telemetry]:
    patient = PatientProfile(
        patient_id="eval-patient",
        age_years=44,
        photosensitivity_risk=0.0,
        thermal_sensitivity=0.0,
        max_skin_temperature_c=41.0,
        min_spo2_percent=94.0,
        pain_hold_score=7,
        contraindication_present=False,
    )
    prescription = Prescription(
        prescription_id="eval-protocol-v1",
        target_irradiance_mw_cm2=20.0,
        target_duration_seconds=60.0,
        max_irradiance_mw_cm2=25.0,
        max_duration_seconds=120.0,
        max_session_dose_j_cm2=5.0,
        max_cumulative_dose_j_cm2=20.0,
    )
    telemetry = Telemetry(
        skin_temperature_c=36.8,
        spo2_percent=98.0,
        pain_score=0,
        adverse_event_detected=False,
        device_connected=True,
        contact_detected=True,
        calibration_valid=True,
        data_age_seconds=1.0,
        cumulative_dose_j_cm2=6.0,
        session_dose_j_cm2=1.0,
    )
    return patient, prescription, telemetry


def build_scenarios() -> list[Scenario]:
    patient, prescription, telemetry = base_inputs()

    def item(
        scenario_id: str,
        expected: SafetyState,
        requirement: str,
        *,
        p: PatientProfile | None = None,
        rx: Prescription | None = None,
        t: Telemetry | None = None,
    ) -> Scenario:
        return Scenario(
            scenario_id,
            expected,
            p or patient,
            rx or prescription,
            t or telemetry,
            requirement,
        )

    return [
        item("nominal", SafetyState.ALLOW, "No active rule permits the prescribed setpoint."),
        item(
            "thermal_warning",
            SafetyState.ADJUST,
            "Thermal warning membership reduces irradiance.",
            t=replace(telemetry, skin_temperature_c=40.0),
        ),
        item(
            "thermal_limit",
            SafetyState.HOLD,
            "Patient-specific temperature limit interrupts delivery.",
            t=replace(telemetry, skin_temperature_c=41.0),
        ),
        item(
            "spo2_warning",
            SafetyState.ADJUST,
            "Oxygen-saturation warning membership reduces duration.",
            t=replace(telemetry, spo2_percent=92.0),
        ),
        item(
            "spo2_limit",
            SafetyState.HOLD,
            "Hard oxygen-saturation boundary interrupts delivery.",
            t=replace(telemetry, spo2_percent=90.0),
        ),
        item(
            "pain_warning",
            SafetyState.ADJUST,
            "Reported pain within the warning zone reduces duration.",
            t=replace(telemetry, pain_score=5),
        ),
        item(
            "pain_limit",
            SafetyState.HOLD,
            "Patient-specific pain boundary interrupts delivery.",
            t=replace(telemetry, pain_score=7),
        ),
        item(
            "adverse_event",
            SafetyState.HOLD,
            "An adverse-event signal interrupts delivery.",
            t=replace(telemetry, adverse_event_detected=True),
        ),
        item(
            "device_disconnect",
            SafetyState.HOLD,
            "Loss of device connectivity interrupts delivery.",
            t=replace(telemetry, device_connected=False),
        ),
        item(
            "contact_loss",
            SafetyState.HOLD,
            "Loss of applicator contact interrupts delivery.",
            t=replace(telemetry, contact_detected=False),
        ),
        item(
            "invalid_calibration",
            SafetyState.HOLD,
            "Invalid or expired calibration interrupts delivery.",
            t=replace(telemetry, calibration_valid=False),
        ),
        item(
            "telemetry_warning",
            SafetyState.ADJUST,
            "Aging telemetry reduces irradiance and duration.",
            t=replace(telemetry, data_age_seconds=60.0),
        ),
        item(
            "telemetry_stale",
            SafetyState.HOLD,
            "Telemetry at the hard freshness boundary interrupts delivery.",
            t=replace(telemetry, data_age_seconds=120.0),
        ),
        item(
            "dose_headroom",
            SafetyState.ADJUST,
            "Duration is capped to the remaining per-session dose.",
            t=replace(telemetry, cumulative_dose_j_cm2=9.5, session_dose_j_cm2=4.5),
        ),
        item(
            "session_dose_exhausted",
            SafetyState.COMPLETE,
            "Exhausted per-session dose completes delivery without a safety event.",
            t=replace(telemetry, cumulative_dose_j_cm2=10.0, session_dose_j_cm2=5.0),
        ),
        item(
            "cumulative_dose_exhausted",
            SafetyState.COMPLETE,
            "Exhausted cumulative dose completes delivery without a safety event.",
            t=replace(telemetry, cumulative_dose_j_cm2=20.0, session_dose_j_cm2=1.0),
        ),
        item(
            "photosensitivity_risk",
            SafetyState.ADJUST,
            "Clinician-assessed photosensitivity reduces irradiance.",
            p=replace(patient, photosensitivity_risk=0.7),
        ),
        item(
            "thermal_sensitivity",
            SafetyState.ADJUST,
            "Clinician-assessed thermal sensitivity reduces irradiance.",
            p=replace(patient, thermal_sensitivity=0.6),
        ),
        item(
            "prescription_caps",
            SafetyState.ADJUST,
            "Prescription ceilings cap irradiance and duration.",
            rx=replace(
                prescription,
                target_irradiance_mw_cm2=30.0,
                target_duration_seconds=150.0,
            ),
        ),
        item(
            "fractional_output_resolution",
            SafetyState.ALLOW,
            "Fractional setpoints are quantized downward and recorded without changing the action.",
            rx=Prescription(
                prescription_id="eval-fractional",
                target_irradiance_mw_cm2=1.2346,
                target_duration_seconds=10.2346,
                max_irradiance_mw_cm2=1.2346,
                max_duration_seconds=10.2346,
                max_session_dose_j_cm2=5.0,
                max_cumulative_dose_j_cm2=20.0,
            ),
        ),
        item(
            "setpoint_below_resolution",
            SafetyState.COMPLETE,
            "Dose headroom below the configured setpoint resolution completes delivery.",
            t=replace(
                telemetry,
                cumulative_dose_j_cm2=19.999999,
                session_dose_j_cm2=1.0,
            ),
        ),
        item(
            "active_contraindication",
            SafetyState.HOLD,
            "An active contraindication interrupts delivery.",
            p=replace(patient, contraindication_present=True),
        ),
        item(
            "simultaneous_faults",
            SafetyState.HOLD,
            "Multiple hard faults preserve conservative precedence and explanations.",
            t=replace(
                telemetry,
                skin_temperature_c=42.0,
                spo2_percent=88.0,
                device_connected=False,
                contact_detected=False,
                calibration_valid=False,
            ),
        ),
        item(
            "fault_with_exhausted_dose",
            SafetyState.HOLD,
            "A safety interlock takes precedence over dose completion.",
            t=replace(
                telemetry,
                cumulative_dose_j_cm2=10.0,
                session_dose_j_cm2=5.0,
                contact_detected=False,
            ),
        ),
    ]


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def engine_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted((BACKEND / "app" / "engine").glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def invariant_errors(scenario: Scenario, decision: Any) -> list[str]:
    errors: list[str] = []
    irradiance = decision.recommended_irradiance_mw_cm2
    duration = decision.recommended_duration_seconds
    estimated_dose = decision.estimated_additional_dose_j_cm2

    if decision.state in (SafetyState.HOLD, SafetyState.COMPLETE):
        if irradiance != 0.0 or duration != 0.0 or estimated_dose != 0.0:
            errors.append("HOLD/COMPLETE must publish zero irradiance, duration, and additional dose")
        if decision.state is SafetyState.COMPLETE and decision.risk_score != 0.0:
            errors.append("COMPLETE must not carry an escalation index")
        return errors

    if irradiance <= 0.0 or duration <= 0.0:
        errors.append("ALLOW/ADJUST must publish positive irradiance and duration")
    if irradiance > scenario.prescription.max_irradiance_mw_cm2:
        errors.append("recommended irradiance exceeds the prescription maximum")
    if duration > scenario.prescription.max_duration_seconds:
        errors.append("recommended duration exceeds the prescription maximum")

    actual_dose = irradiance * duration / 1000.0
    session_headroom = (
        scenario.prescription.max_session_dose_j_cm2 - scenario.telemetry.session_dose_j_cm2
    )
    cumulative_headroom = (
        scenario.prescription.max_cumulative_dose_j_cm2
        - scenario.telemetry.cumulative_dose_j_cm2
    )
    if actual_dose > min(session_headroom, cumulative_headroom) + 1e-12:
        errors.append("recommended setpoint exceeds available dose headroom")
    if abs(actual_dose - estimated_dose) > 1e-12:
        errors.append("estimated additional dose differs from the published setpoint dose")
    return errors


def run(iterations: int, output_dir: Path) -> dict[str, Any]:
    engine = DecisionEngine()
    scenarios = build_scenarios()
    rows: list[dict[str, Any]] = []
    observed_rule_ids: set[str] = set()

    for scenario in scenarios:
        decision = engine.evaluate(scenario.patient, scenario.prescription, scenario.telemetry)
        repeated = engine.evaluate(scenario.patient, scenario.prescription, scenario.telemetry)
        deterministic = decision.to_dict() == repeated.to_dict()
        rule_ids = [rule.rule_id for rule in decision.fired_rules]
        observed_rule_ids.update(rule_ids)
        expected_rule = EXPECTED_RULES[scenario.scenario_id]
        expected_rule_observed = expected_rule is None or expected_rule in rule_ids
        errors = invariant_errors(scenario, decision)
        action_matches = decision.state is scenario.expected
        passed = action_matches and expected_rule_observed and deterministic and not errors
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "expected_action": scenario.expected.value,
                "observed_action": decision.state.value,
                "expected_rule": expected_rule or "",
                "expected_rule_observed": expected_rule_observed,
                "action_matches": action_matches,
                "invariants_passed": not errors,
                "invariant_errors": "|".join(errors),
                "passed": passed,
                "deterministic": deterministic,
                "risk_score": decision.risk_score,
                "confidence": decision.confidence,
                "recommended_irradiance_mw_cm2": decision.recommended_irradiance_mw_cm2,
                "recommended_duration_seconds": decision.recommended_duration_seconds,
                "estimated_additional_dose_j_cm2": decision.estimated_additional_dose_j_cm2,
                "fired_rules": "|".join(rule_ids),
                "requirement": scenario.requirement,
            }
        )

    latencies_us: list[float] = []
    for index in range(iterations):
        scenario = scenarios[index % len(scenarios)]
        start = perf_counter_ns()
        engine.evaluate(scenario.patient, scenario.prescription, scenario.telemetry)
        latencies_us.append((perf_counter_ns() - start) / 1000.0)

    expected_holds = [row for row in rows if row["expected_action"] == "HOLD"]
    expected_completions = [row for row in rows if row["expected_action"] == "COMPLETE"]
    expected_non_holds = [row for row in rows if row["expected_action"] != "HOLD"]
    hold_requirement_pass_rate = (
        sum(bool(row["passed"]) for row in expected_holds) / len(expected_holds)
    )
    nonhold_requirement_pass_rate = (
        sum(bool(row["passed"]) for row in expected_non_holds)
        / len(expected_non_holds)
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "scenario_results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_type": "software requirements verification",
        "clinical_ground_truth": False,
        "engine_sha256": engine_digest(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "scenario_count": len(rows),
        "passed_scenarios": sum(bool(row["passed"]) for row in rows),
        "deterministic_scenarios": sum(bool(row["deterministic"]) for row in rows),
        "action_accuracy_against_requirements": sum(bool(row["passed"]) for row in rows)
        / len(rows),
        "hold_requirement_pass_rate": hold_requirement_pass_rate,
        "completion_requirement_pass_rate": (
            sum(bool(row["passed"]) for row in expected_completions) / len(expected_completions)
        ),
        "action_counts": {
            state.value: sum(row["observed_action"] == state.value for row in rows)
            for state in SafetyState
        },
        "nonhold_requirement_pass_rate": nonhold_requirement_pass_rate,
        "observed_rule_count": len(observed_rule_ids),
        "observed_rule_ids": sorted(observed_rule_ids),
        "latency": {
            "iterations": iterations,
            "unit": "microseconds",
            "median": round(statistics.median(latencies_us), 3),
            "p95": round(percentile(latencies_us, 0.95), 3),
            "p99": round(percentile(latencies_us, 0.99), 3),
            "maximum": round(max(latencies_us), 3),
        },
        "limitations": [
            "Scenario labels encode software requirements and are not clinical outcome labels.",
            "Latency is measured on one local runtime and is not a real-time certification result.",
            "The harness does not model sensor error distributions, tissue optics, or treatment efficacy.",
        ],
        "scenario_results_file": csv_path.name,
    }
    summary_path = output_dir / "evaluation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=50_000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    args = parser.parse_args()
    if args.iterations < 100:
        parser.error("--iterations must be at least 100")
    summary = run(args.iterations, args.output_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if (
        summary["passed_scenarios"] == summary["scenario_count"]
        and summary["deterministic_scenarios"] == summary["scenario_count"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
