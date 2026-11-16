# Changelog

## 1.1.0

### Decision engine

- New action `COMPLETE`. Exhausted session or cumulative dose allowances and a remaining allowance below the output resolution now return `COMPLETE` with zero output, risk `0` and confidence `1`. In `1.0.0` these cases returned `HOLD`.
- Safety interlocks take precedence over completion. When a safety rule and an allowance rule fire together, the result is `HOLD` and both rules are listed.
- New rule severity `INFO`. `OUTPUT_RESOLUTION_FLOOR` documents conservative quantization but no longer turns `ALLOW` into `ADJUST` and no longer enters the risk and confidence values.
- Rule severities are `INFO`, `ADJUST`, `COMPLETE` and `HOLD`.

### Service

- The decision adapter returns `COMPLETE` with rule `TARGET_DOSE_DELIVERED` when the delivered dose reaches the prescription target dose. Measured-value gates (wavelength, irradiance) still override this result with `HOLD`.
- Recommended durations keep the engine resolution of 0.001 s. Release `1.0.0` truncated them to whole seconds.
- The irradiance tolerance gate treats the observation as a graded rule with membership `0.55`: risk `0.55` and confidence `0.75 + 0.25 · 0.55`, stored as `0.887`.
- A `COMPLETE` decision closes the session with status `completed`, stop reason `target_dose_delivered` or `dose_allowance_reached`, and a `session.completed` audit event. No safety alert is created.
- Simulator: nominal skin warming levels off 0.6 °C above the starting value. In `1.0.0` it rose by 0.06 °C per sample and reached the 41 °C limit after about 77 s, before a 4 J/cm² session at 24 mW/cm² could finish. `temperature_rise` and `spo2_drop` now ramp from the last recorded value, so a scenario switched on during a session produces a ramp instead of a jump.
- Engine identifier `research-engine-1.1`; API and package version `1.1.0`.

### Operator console

- Redesigned interface: top navigation, light-blue background, white cards, Poppins typeface bundled under the SIL Open Font License (`frontend/src/assets/fonts`).
- Live session: vital tiles with prescription limits, two-lane telemetry chart with the irradiance envelope and the temperature limit, decision panel with recommended setpoints and one card per fired rule (observed value, limit, effect).
- Completed and stopped sessions offer a new session from the same page.
- The chart shows recorded samples only, and the sample counter counts every received sample.
- Dashboard, patient, device, prescription and alert views show stored record fields only.

### Tests and evaluation

- 24 requirement scenarios, including `fault_with_exhausted_dose`.
- Engine tests: 22 (323 parameterised cases). New tests cover interlock precedence over completion, completion without escalation and the informational quantization note.
- New lifecycle test: delivery of the target dose closes the session as completed without an alert.
- Frontend: decision card test for `COMPLETE`.
