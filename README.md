# LumaCare DSS

LumaCare DSS is a full-stack research prototype for explainable monitoring of IoT-enabled light-therapy sessions. It combines deterministic device telemetry, persistent session records, a rule and fuzzy-logic decision engine, real-time WebSocket updates, safety alerts, an application audit trail, and FHIR R4-aligned research exports.

> Research software only. The bundled patients, devices, prescriptions, telemetry, and outcomes are synthetic. The system has not been validated for diagnosis, treatment selection, autonomous control, or clinical deployment.

## Release identification

The research artifact release is `1.1.0`; `CHANGELOG.md` lists the changes against `1.0.0`. The API reports this identifier from `/api/v1/health` and `/api/v1/meta`, and the release archive includes it in the filename.

## Included components

- FastAPI service with OpenAPI documentation and SQLite persistence
- patient, device, prescription, session, telemetry, decision, alert, and audit records
- explainable `ALLOW`, `ADJUST`, `COMPLETE`, and `HOLD` recommendations with stored rule evidence; `COMPLETE` closes a session at the prescribed dose without a safety alert
- deterministic telemetry simulator with nominal and fault-injection scenarios
- WebSocket stream for live telemetry and decision updates
- React and TypeScript operator console with responsive data views (screenshots in `docs/screenshots`)
- FHIR R4-aligned JSON bundles for research interoperability tests
- backend unit and API integration tests, frontend component and mapping tests, lint, production build, deterministic scenario evaluation, and dependency audits

## Prerequisites

The managed scripts support macOS and Linux environments with:

- Bash
- Python `3.11` or later, with `venv` and `pip`
- Node.js `22.12.0` or later and npm
- `curl`, `nohup`, and `ps`
- network access to the Python and npm registries during dependency installation and vulnerability audits

Release packaging additionally requires `zip` and either `shasum` or `sha256sum`. If `python3` is not the intended interpreter, provide an executable path or command name through `PYTHON_BIN`:

```bash
PYTHON_BIN=/path/to/python3 ./scripts/bootstrap.sh
```

An existing `backend/.venv` is reused. Remove that environment before selecting a different base interpreter.

## Start locally

From this directory:

```bash
./scripts/bootstrap.sh
./scripts/dev.sh
```

The API uses `http://127.0.0.1:8000`. The web client uses `http://127.0.0.1:5173` when that port is available and falls back to `http://127.0.0.1:4173` when required. The selected port is printed by `dev.sh` and written to `.runtime/frontend.port`. Startup fails when port `8000` or both frontend ports are occupied.

OpenAPI documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Runtime logs are written to `.runtime/backend.log` and `.runtime/frontend.log`.

Stop the managed processes with:

```bash
./scripts/stop.sh
```

The managed scripts validate stored process identifiers before termination. `LumaCare-DSS.code-workspace` provides editor settings and development tasks; `scripts/dev.sh` remains the authoritative launch path when automatic port fallback is required.

## Demonstration workflow

1. Review the synthetic cohort, device states, and research prescriptions.
2. Open **Live session**, select an eligible patient, online device, and active prescription, then start a session.
3. Observe telemetry, cumulative dose, decision state, recommended setpoints, and fired rules.
4. Inject a temperature rise, SpO2 decrease, contact loss, or irradiance spike.
5. Confirm that the state changes and the associated alert and audit record are persisted.
6. Let a nominal session run until the delivered dose reaches the prescription target and confirm that it closes as completed without an alert.
7. Open **Audit & FHIR** and export a research bundle.

The simulator stops after a `HOLD` or `COMPLETE` decision. A new session is required for another scenario, preserving the original session trace.

## Automated verification

Run the complete local release gate:

```bash
./scripts/test-all.sh
```

The gate performs Python dependency consistency and vulnerability checks, backend tests, the deterministic requirements matrix with 50,000 latency iterations, npm audit, frontend tests, lint, TypeScript checks, and the production build. Vulnerability audits require registry access. The evaluation iteration count can be changed for local diagnostics while retaining a minimum of 100:

```bash
LUMACARE_EVAL_ITERATIONS=1000 ./scripts/test-all.sh
```

Run the requirements matrix independently with:

```bash
./backend/.venv/bin/python evaluation/run_evaluation.py --iterations 50000
```

The scenario labels encode software requirements. They do not constitute clinical ground truth, and the resulting metrics must not be presented as clinical performance.

## Manual browser acceptance

Browser acceptance remains a separate system-level check. After `dev.sh` reports readiness:

1. open the reported web-client URL and confirm that the overview loads from the connected API;
2. visit each navigation route at desktop and mobile viewport widths;
3. start a supervised synthetic session and confirm live WebSocket telemetry;
4. inject contact loss and confirm a `HOLD` decision plus a persisted alert;
5. run a nominal session to the target dose and confirm a `COMPLETE` decision, the session status `completed`, and no new alert;
6. acknowledge the alert and confirm the corresponding audit event;
7. export the FHIR R4-aligned research bundle;
8. confirm that the browser console contains no uncaught application errors.

These checks assess software integration and presentation. They do not validate clinical safety or treatment effectiveness.

## Configuration

Copy the root example when overriding local defaults:

```bash
cp .env.example .env
```

Backend settings use the `LUMACARE_` prefix. Frontend build settings use the `VITE_` prefix and are read from the same root `.env`. The example permits both supported frontend origins, points REST and WebSocket traffic to `127.0.0.1:8000`, enables deterministic seed data, and stores SQLite data in `backend/light_therapy.db` when launched through the managed scripts.

`VITE_DEMO_FALLBACK=true` permits a clearly labelled deterministic frontend fallback when the API cannot be reached. Set it to `false` when an unavailable API must be treated as a hard interface failure.

## Release package

Run the complete verification gate before creating the source artifact. The packaging script copies an explicit allow-list, includes the generated scenario results, verifies the ZIP container, and writes a SHA-256 checksum:

```bash
./scripts/test-all.sh
./scripts/package-release.sh
```

By default, the files are written to `../outputs/LumaCare-DSS-1.1.0.zip` and `../outputs/LumaCare-DSS-1.1.0.zip.sha256`. A different output directory may be supplied as the first argument. Installed virtual environments, `node_modules`, databases, runtime logs, PID files, frontend build output, local `.env`, and compiler caches are excluded. Packaging is refused when the saved evaluation digest does not match the current engine source or when any requirement scenario failed.

Verify the checksum on macOS with:

```bash
(cd ../outputs && shasum -a 256 -c LumaCare-DSS-1.1.0.zip.sha256)
```

On Linux, use `sha256sum -c` with the same checksum file.

## Project structure

```text
backend/      FastAPI API, persistence, simulator, decision engine, and tests
frontend/     React operator console and component tests
evaluation/   deterministic requirements matrix and generated results
docs/         architecture and explicit research safety boundary
scripts/      bootstrap, managed runtime, verification, and packaging commands
```

The architecture and safety boundary are documented in `docs/architecture.md` and `docs/safety-case.md`.

## Rights and license status

No open-source or redistribution license is granted with this artifact. The research-use disclaimer defines the software scope and does not provide copyright permission. Use, redistribution, or adaptation requires permission from the rights holder unless applicable law provides otherwise.
