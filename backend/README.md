# Light Therapy Research Decision Support API

FastAPI and SQLite backend for the reproducible research demonstrator. It manages synthetic patients, IoT device state, research protocol prescriptions, therapy sessions, telemetry, explainable decisions, alerts, audit events, deterministic safety scenarios, WebSocket streaming, and FHIR R4-aligned exports.

All thresholds, recommendations, seed records, and simulator signals are research/demo artifacts. The software has not been validated for diagnosis, treatment, or autonomous medical-device control. `X-Actor` and `X-Role` provide audit labels and do not implement authentication or authorization.

## Run

From `system/backend`:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

OpenAPI is available at `http://127.0.0.1:8000/docs`. The default SQLite database is created at `system/backend/light_therapy.db` and receives an idempotent deterministic seed on first startup.

Runtime settings use the `LUMACARE_` prefix. The application loads `system/.env` first and `system/backend/.env` as an optional local override. Supported keys include `LUMACARE_DATABASE_URL`, `LUMACARE_SEED_DEMO_DATA`, `LUMACARE_SIMULATOR_INTERVAL_SECONDS`, and `LUMACARE_ALLOWED_ORIGINS`.

The deterministic simulator is deliberately single-worker. Startup acquires an exclusive lock associated with the SQLite database, and a second API worker for the same database fails explicitly. This prevents duplicate process-local simulator loops; run Uvicorn with one worker. SQLite partial unique indexes independently enforce at most one `running` session for each device and patient.

## Verify

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pip check
.venv/bin/python -m pip_audit --local --progress-spinner off
```

The primary REST prefix is `/api/v1`; session telemetry is streamed from `/ws/sessions/{session_id}`. Use `/api/v1/meta` for machine-readable scope and research-use limitations.
