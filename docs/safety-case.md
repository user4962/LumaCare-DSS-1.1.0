# Research safety case

## Intended use

LumaCare DSS demonstrates an explainable software architecture for collecting light-therapy device telemetry and assisting a trained operator with session monitoring. The included protocols, thresholds, patient records, and outcomes are synthetic research data. The application is not validated for diagnosis, treatment selection, or autonomous device control.

## Control layers

1. Input validation rejects malformed ranges and timestamps.
2. Data-quality rules evaluate telemetry freshness, device connectivity, contact, and calibration status.
3. Physiological and dose rules evaluate configurable research thresholds.
4. The engine selects the most conservative state produced by active rules. A safety interlock (`HOLD`) takes precedence over dose completion (`COMPLETE`), so an exhausted dose allowance cannot mask a fault.
5. The API persists the complete decision context before broadcasting the result.
6. The interface keeps HOLD and ADJUST states visible until the operator resolves or acknowledges the associated condition. COMPLETE is shown as the end of the prescribed exposure and raises no safety alert.

## Hazard-oriented scenarios

The automated suite covers elevated skin temperature, reduced oxygen saturation, contact loss, stale telemetry, expired calibration, cumulative dose limit, reported pain, and simultaneous faults. Boundary tests verify the exact threshold behavior and deterministic rule precedence.

## Limitations

The simulator does not model tissue optics, pharmacological photosensitization, comorbidity-specific contraindications, hardware failure distributions, or clinical outcomes. The safety engine is intended for software research and architecture evaluation. Clinical deployment would require a formally controlled requirements baseline, usability engineering, independent verification, clinical evaluation, and post-market processes.
