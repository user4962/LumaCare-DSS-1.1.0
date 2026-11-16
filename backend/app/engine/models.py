"""Typed input and output models for the light-therapy decision engine.

The models deliberately use only the Python standard library.  They can be
constructed by a web adapter after request validation and can be serialized
with :meth:`SafetyDecision.to_dict`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from math import isfinite
from numbers import Real
from typing import Any


def _require_finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")


def _require_between(name: str, value: float, lower: float, upper: float) -> None:
    _require_finite(name, value)
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be between {lower} and {upper}")


def _require_positive(name: str, value: float) -> None:
    _require_finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _require_bool(name: str, value: bool) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be a bool")


def _normalize_real_fields(instance: object, names: tuple[str, ...]) -> None:
    """Validate real-valued fields and store a stable float representation."""

    for name in names:
        value = getattr(instance, name)
        _require_finite(name, value)
        object.__setattr__(instance, name, float(value))


class SafetyState(str, Enum):
    """Treatment state returned by the decision engine.

    ``COMPLETE`` ends delivery because the prescribed dose allowance has been
    used.  It shares the zero-output invariant of ``HOLD`` but is not a safety
    event.  ``HOLD`` takes precedence when both apply.
    """

    ALLOW = "ALLOW"
    ADJUST = "ADJUST"
    COMPLETE = "COMPLETE"
    HOLD = "HOLD"


class RuleSeverity(str, Enum):
    """Effect that a fired rule has on treatment.

    ``INFO`` records a change of representation, such as quantization to the
    output resolution, that does not alter the action.
    """

    INFO = "INFO"
    ADJUST = "ADJUST"
    COMPLETE = "COMPLETE"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class PatientProfile:
    """Patient-specific safety limits and clinician-assessed sensitivities.

    ``photosensitivity_risk`` and ``thermal_sensitivity`` are normalized
    clinician inputs in the closed interval [0, 1].  The engine does not infer
    them from age, diagnosis, medication names, or skin phototype.
    """

    patient_id: str
    age_years: int
    photosensitivity_risk: float = 0.0
    thermal_sensitivity: float = 0.0
    max_skin_temperature_c: float = 41.0
    min_spo2_percent: float = 94.0
    pain_hold_score: int = 7
    contraindication_present: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.patient_id, str):
            raise TypeError("patient_id must be a string")
        if not self.patient_id.strip():
            raise ValueError("patient_id must not be empty")
        if type(self.age_years) is not int:
            raise TypeError("age_years must be an int")
        if not 0 <= self.age_years <= 130:
            raise ValueError("age_years must be between 0 and 130")
        _normalize_real_fields(
            self,
            (
                "photosensitivity_risk",
                "thermal_sensitivity",
                "max_skin_temperature_c",
                "min_spo2_percent",
            ),
        )
        _require_between("photosensitivity_risk", self.photosensitivity_risk, 0.0, 1.0)
        _require_between("thermal_sensitivity", self.thermal_sensitivity, 0.0, 1.0)
        _require_between("max_skin_temperature_c", self.max_skin_temperature_c, 35.0, 45.0)
        _require_between("min_spo2_percent", self.min_spo2_percent, 80.0, 100.0)
        if type(self.pain_hold_score) is not int:
            raise TypeError("pain_hold_score must be an int")
        if not 1 <= self.pain_hold_score <= 10:
            raise ValueError("pain_hold_score must be between 1 and 10")
        _require_bool("contraindication_present", self.contraindication_present)


@dataclass(frozen=True, slots=True)
class Prescription:
    """Clinician-approved target settings and dose ceilings."""

    prescription_id: str
    target_irradiance_mw_cm2: float
    target_duration_seconds: float
    max_irradiance_mw_cm2: float
    max_duration_seconds: float
    max_session_dose_j_cm2: float
    max_cumulative_dose_j_cm2: float

    def __post_init__(self) -> None:
        if not isinstance(self.prescription_id, str):
            raise TypeError("prescription_id must be a string")
        if not self.prescription_id.strip():
            raise ValueError("prescription_id must not be empty")
        numeric_fields = (
            "target_irradiance_mw_cm2",
            "target_duration_seconds",
            "max_irradiance_mw_cm2",
            "max_duration_seconds",
            "max_session_dose_j_cm2",
            "max_cumulative_dose_j_cm2",
        )
        _normalize_real_fields(self, numeric_fields)
        for name in numeric_fields:
            _require_positive(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class Telemetry:
    """Snapshot consumed by one deterministic evaluation.

    Data freshness is supplied explicitly instead of being computed from the
    wall clock.  ``cumulative_dose_j_cm2`` includes the dose already delivered
    in the active session, while ``session_dose_j_cm2`` contains only the
    active-session component.
    """

    skin_temperature_c: float
    spo2_percent: float
    pain_score: int
    adverse_event_detected: bool
    device_connected: bool
    calibration_valid: bool
    data_age_seconds: float
    cumulative_dose_j_cm2: float
    session_dose_j_cm2: float = 0.0
    contact_detected: bool = True

    def __post_init__(self) -> None:
        _normalize_real_fields(
            self,
            (
                "skin_temperature_c",
                "spo2_percent",
                "data_age_seconds",
                "cumulative_dose_j_cm2",
                "session_dose_j_cm2",
            ),
        )
        _require_between("skin_temperature_c", self.skin_temperature_c, 0.0, 60.0)
        _require_between("spo2_percent", self.spo2_percent, 0.0, 100.0)
        if type(self.pain_score) is not int:
            raise TypeError("pain_score must be an int")
        if not 0 <= self.pain_score <= 10:
            raise ValueError("pain_score must be between 0 and 10")
        for name in (
            "adverse_event_detected",
            "device_connected",
            "calibration_valid",
            "contact_detected",
        ):
            _require_bool(name, getattr(self, name))
        _require_between("data_age_seconds", self.data_age_seconds, 0.0, 86_400.0)
        _require_between(
            "cumulative_dose_j_cm2", self.cumulative_dose_j_cm2, 0.0, 1_000_000.0
        )
        _require_between("session_dose_j_cm2", self.session_dose_j_cm2, 0.0, 1_000_000.0)
        if self.session_dose_j_cm2 > self.cumulative_dose_j_cm2:
            raise ValueError("session_dose_j_cm2 cannot exceed cumulative_dose_j_cm2")


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Auditable thresholds and fuzzy-output coefficients."""

    skin_temperature_warning_margin_c: float = 2.0
    spo2_hold_margin_percent: float = 4.0
    pain_adjust_score: int = 3
    telemetry_warning_age_seconds: float = 30.0
    telemetry_hold_age_seconds: float = 120.0
    dose_warning_ratio: float = 0.80
    fuzzy_activation_threshold: float = 0.01
    temperature_irradiance_reduction: float = 0.60
    oxygen_duration_reduction: float = 0.55
    pain_duration_reduction: float = 0.50
    photosensitivity_irradiance_reduction: float = 0.45
    thermal_sensitivity_irradiance_reduction: float = 0.35
    freshness_irradiance_reduction: float = 0.25
    freshness_duration_reduction: float = 0.25
    dose_duration_reduction: float = 0.30
    output_precision: int = 3

    def __post_init__(self) -> None:
        numeric_fields = (
            "skin_temperature_warning_margin_c",
            "spo2_hold_margin_percent",
            "telemetry_warning_age_seconds",
            "telemetry_hold_age_seconds",
            "dose_warning_ratio",
            "fuzzy_activation_threshold",
            "temperature_irradiance_reduction",
            "oxygen_duration_reduction",
            "pain_duration_reduction",
            "photosensitivity_irradiance_reduction",
            "thermal_sensitivity_irradiance_reduction",
            "freshness_irradiance_reduction",
            "freshness_duration_reduction",
            "dose_duration_reduction",
        )
        _normalize_real_fields(self, numeric_fields)
        _require_positive(
            "skin_temperature_warning_margin_c", self.skin_temperature_warning_margin_c
        )
        _require_positive("spo2_hold_margin_percent", self.spo2_hold_margin_percent)
        if type(self.pain_adjust_score) is not int:
            raise TypeError("pain_adjust_score must be an int")
        if not 0 <= self.pain_adjust_score <= 9:
            raise ValueError("pain_adjust_score must be between 0 and 9")
        _require_positive("telemetry_warning_age_seconds", self.telemetry_warning_age_seconds)
        _require_positive("telemetry_hold_age_seconds", self.telemetry_hold_age_seconds)
        if self.telemetry_warning_age_seconds >= self.telemetry_hold_age_seconds:
            raise ValueError("telemetry warning age must be less than telemetry hold age")
        _require_between("dose_warning_ratio", self.dose_warning_ratio, 0.0, 0.999999)
        if not 0.0 <= self.fuzzy_activation_threshold < 1.0:
            raise ValueError("fuzzy_activation_threshold must be at least 0 and less than 1")
        for name in (
            "temperature_irradiance_reduction",
            "oxygen_duration_reduction",
            "pain_duration_reduction",
            "photosensitivity_irradiance_reduction",
            "thermal_sensitivity_irradiance_reduction",
            "freshness_irradiance_reduction",
            "freshness_duration_reduction",
            "dose_duration_reduction",
        ):
            _require_between(name, getattr(self, name), 0.0, 0.95)
        if type(self.output_precision) is not int:
            raise TypeError("output_precision must be an int")
        if not 0 <= self.output_precision <= 9:
            raise ValueError("output_precision must be between 0 and 9")


@dataclass(frozen=True, slots=True)
class FiredRule:
    """One explainable rule activation."""

    rule_id: str
    severity: RuleSeverity
    strength: float
    message: str
    observed: str
    threshold: str

    def __post_init__(self) -> None:
        _normalize_real_fields(self, ("strength",))
        _require_between("strength", self.strength, 0.0, 1.0)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["severity"] = self.severity.value
        return result


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    """Complete recommendation and its rule-level explanation."""

    state: SafetyState
    recommended_irradiance_mw_cm2: float
    recommended_duration_seconds: float
    estimated_additional_dose_j_cm2: float
    reasons: tuple[str, ...]
    fired_rules: tuple[FiredRule, ...]
    confidence: float
    risk_score: float

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation with stable field names."""

        return {
            "state": self.state.value,
            "recommended_irradiance_mw_cm2": self.recommended_irradiance_mw_cm2,
            "recommended_duration_seconds": self.recommended_duration_seconds,
            "estimated_additional_dose_j_cm2": self.estimated_additional_dose_j_cm2,
            "reasons": list(self.reasons),
            "fired_rules": [rule.to_dict() for rule in self.fired_rules],
            "confidence": self.confidence,
            "risk_score": self.risk_score,
        }
