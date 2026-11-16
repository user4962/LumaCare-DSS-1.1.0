# Browser acceptance record

## Scope

This record documents the manual system-level acceptance run completed on 2026-07-13 against the locally hosted release candidate `1.0.0`. The run exercised the React operator console, FastAPI service, SQLite persistence, WebSocket telemetry stream, deterministic simulator, alert workflow, audit trail, and FHIR-aligned export. All displayed patient and treatment data were synthetic.

Release `1.1.0` changes the decision lifecycle (`COMPLETE`), the operator console and the simulator. The checklist in `README.md` must be repeated for `1.1.0`; the table below remains the record of the `1.0.0` run.

## Environment

- web client: `http://127.0.0.1:5173`
- API and OpenAPI document: `http://127.0.0.1:8000`
- desktop and 390 x 844 mobile viewports
- API demo fallback disabled by the connected-service state

## Acceptance results

| Check | Result | Evidence observed |
| --- | --- | --- |
| API-backed overview | Pass | Health state reported API ready; zero active sessions produced an explicit empty state. |
| Core navigation | Pass | Overview, Live Therapy, Patients, Devices, Protocols, Alerts, and Audit & Interoperability loaded from API data. |
| Global search | Pass | A synthetic patient query navigated to the Patients route and opened the corresponding record drawer. |
| Session preflight | Pass | Patient, device, and prescription selections showed wavelength, irradiance, dose, and duration limits before session creation. |
| Live WebSocket stream | Pass | Starting a supervised session produced sequential telemetry and decision updates without a page refresh. |
| Contact-loss interlock | Pass | Injected contact loss produced `HOLD`, zero recommended irradiance, zero recommended duration, zero additional dose, and rule `APPLICATOR_CONTACT_LOST`. |
| Terminal-state presentation | Pass | The interface replaced invalid stop controls with a terminal safety-hold state after the interlock. |
| Alert persistence and acknowledgement | Pass | A critical contact-loss alert appeared, acknowledgement updated its state, and a confirmation notification was displayed. |
| Audit trail | Pass | Session creation and start, simulator scenario injection, telemetry decision, and alert acknowledgement events were present. |
| FHIR-aligned export | Pass | The UI completed the export action; direct API verification confirmed a collection Bundle with Patient, Device, ServiceRequest, Procedure, Observation, and DetectedIssue resources. |
| Responsive layout | Pass | The 390 x 844 layout showed no horizontal overflow and provided an operable mobile navigation drawer. |
| Browser diagnostics | Pass | No uncaught application errors or warnings were present after the tested workflow. |

## Interpretation and limitations

The acceptance run verifies integration behavior for the documented synthetic workflow. It does not establish clinical validity, medical-device conformity, treatment effectiveness, cybersecurity certification, or suitability for autonomous control. Reproduction in another environment requires the automated release gate and the manual checks described in the project README.
