# Light-therapy decision engine

This package implements a deterministic and explainable safety layer for a
research prototype. It combines hard interlock rules with linear fuzzy
memberships. It does not diagnose a condition or create a prescription.
Clinical limits must be approved and configured by the responsible clinician
and validated for the target device and jurisdiction before clinical use.

## Public API

```python
from app.engine import DecisionEngine, PatientProfile, Prescription, Telemetry

decision = DecisionEngine().evaluate(patient, prescription, telemetry)
payload = decision.to_dict()
```

The output contains `state` (`ALLOW`, `ADJUST`, `COMPLETE`, or `HOLD`), recommended
irradiance and duration, estimated additional dose, ordered reasons, all fired
rules, a confidence value, and a normalized risk score.

## Default assumptions

- The patient-specific hard skin-temperature limit defaults to 41 C. The fuzzy
  warning zone begins 2 C below that limit.
- The patient-specific clear SpO2 threshold defaults to 94%. A fuzzy warning
  zone extends four percentage points below it; the lower boundary triggers
  `HOLD`.
- Pain above 3 enters a fuzzy warning zone. A patient-specific score of 7 or
  higher triggers `HOLD` by default.
- Telemetry older than 30 seconds enters a fuzzy warning zone. Age of 120
  seconds or more, device disconnection, loss of applicator contact, and
  invalid calibration trigger `HOLD`.
- Reaching either session or cumulative dose ceiling returns `COMPLETE` with
  zero output. A recommendation that would exceed remaining dose is shortened
  and never rounded above the ceiling. Dose headroom below the configured
  output resolution also returns `COMPLETE`.
- Any safety interlock takes precedence: when a safety rule and a dose
  allowance rule fire together, the state is `HOLD` and both rules are listed.
- `OUTPUT_RESOLUTION_FLOOR` has severity `INFO`. It documents conservative
  quantization but does not turn `ALLOW` into `ADJUST` and does not change the
  risk or confidence values.
- `cumulative_dose_j_cm2` includes active-session exposure, and
  `session_dose_j_cm2` is its active-session component.
- Confidence describes rule activation certainty. It is not a probability of
  treatment success or absence of injury.
- Risk score is a deterministic escalation index: `0` for `ALLOW` and
  `COMPLETE`, at least `0.5` for `ADJUST`, and `1` for `HOLD`. It is not a calibrated estimate of
  injury probability or clinical outcome.
- Numeric inputs reject strings and booleans. Accepted real values are
  normalized to floats before evaluation.
- `output_precision` supplies one conservative decimal resolution for the
  research simulator. A hardware adapter must replace it with independently
  validated irradiance and duration step sizes for the target device.

All thresholds and fuzzy reduction coefficients are explicit in
`EngineConfig`. Equal inputs and configuration produce byte-equivalent
`to_dict()` results.
