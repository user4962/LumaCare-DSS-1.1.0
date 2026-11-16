"""Reusable deterministic helpers for crisp and fuzzy rule evaluation."""

from __future__ import annotations

from .models import FiredRule, RuleSeverity


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """Clamp ``value`` to a closed interval."""

    return max(lower, min(upper, value))


def rising_membership(value: float, start: float, full: float) -> float:
    """Linear membership that rises from zero at ``start`` to one at ``full``."""

    if full <= start:
        raise ValueError("full must be greater than start")
    return clamp((value - start) / (full - start))


def falling_membership(value: float, full: float, end: float) -> float:
    """Linear membership that falls from one at ``full`` to zero at ``end``."""

    if end <= full:
        raise ValueError("end must be greater than full")
    return clamp((end - value) / (end - full))


def fired_rule(
    rule_id: str,
    severity: RuleSeverity,
    strength: float,
    message: str,
    observed: str,
    threshold: str,
) -> FiredRule:
    """Construct a rule while normalizing floating-point membership strength."""

    return FiredRule(
        rule_id=rule_id,
        severity=severity,
        strength=round(clamp(strength), 6),
        message=message,
        observed=observed,
        threshold=threshold,
    )
