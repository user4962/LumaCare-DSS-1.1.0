from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.seed import SEED_PATIENT_ID, SEED_SESSION_ID
from .conftest import create_resource_graph


def test_deterministic_simulator_step_and_safety_scenario(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]

    first = client.post(f"/api/v1/sessions/{session_id}/simulator/step")
    assert first.status_code == 200, first.text
    assert first.json()["telemetry"]["sequence"] == 0
    assert first.json()["decision"]["action"] in {"ALLOW", "ADJUST"}

    injected = client.post(
        f"/api/v1/sessions/{session_id}/inject-scenario",
        headers=headers,
        json={"scenario": "contact_loss"},
    )
    assert injected.status_code == 200
    second = client.post(f"/api/v1/sessions/{session_id}/simulator/step")
    assert second.status_code == 200
    third = client.post(f"/api/v1/sessions/{session_id}/simulator/step")
    assert third.status_code == 200
    assert third.json()["telemetry"]["contact_detected"] is False
    assert third.json()["decision"]["action"] == "HOLD"


def test_background_simulator_has_observable_status(client: TestClient, headers: dict[str, str]) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]
    started = client.post(
        f"/api/v1/sessions/{session_id}/simulator/start",
        headers=headers,
        json={"scenario": "nominal", "interval_seconds": 0.05, "max_samples": 2},
    )
    assert started.status_code == 200, started.text
    for _ in range(30):
        status = client.get(f"/api/v1/sessions/{session_id}/simulator").json()
        if not status["running"]:
            break
        time.sleep(0.02)
    assert status["running"] is False
    assert status["samples_generated"] == 2
    telemetry = client.get(f"/api/v1/sessions/{session_id}/telemetry").json()
    assert len(telemetry) == 2


def test_fhir_r4_aligned_patient_and_session_bundles(client: TestClient) -> None:
    patient_bundle = client.get(f"/api/v1/patients/{SEED_PATIENT_ID}/fhir")
    assert patient_bundle.status_code == 200
    assert patient_bundle.headers["content-type"].startswith("application/fhir+json")
    patient_json = patient_bundle.json()
    assert patient_json["resourceType"] == "Bundle"
    assert patient_json["type"] == "collection"
    assert any(entry["resource"]["resourceType"] == "Patient" for entry in patient_json["entry"])
    service_request = next(
        entry["resource"]
        for entry in patient_json["entry"]
        if entry["resource"]["resourceType"] == "ServiceRequest"
    )
    assert "orderDetail" in service_request
    assert "deviceCode" not in service_request

    session_bundle = client.get(f"/api/v1/sessions/{SEED_SESSION_ID}/fhir").json()
    resource_types = {entry["resource"]["resourceType"] for entry in session_bundle["entry"]}
    assert {"Patient", "Device", "ServiceRequest", "Procedure", "Observation", "DetectedIssue"} <= resource_types
    observation = next(
        entry["resource"]
        for entry in session_bundle["entry"]
        if entry["resource"]["resourceType"] == "Observation"
    )
    assert observation["focus"] == [{"reference": f"Procedure/{SEED_SESSION_ID}"}]

    all_export = client.get("/api/v1/interop/fhir/export")
    assert all_export.status_code == 200
    all_export_json = all_export.json()
    assert all_export_json["total"] >= 8
    all_resource_types = {
        entry["resource"]["resourceType"] for entry in all_export_json["entry"]
    }
    assert {
        "Patient",
        "Device",
        "ServiceRequest",
        "Procedure",
        "Observation",
        "DetectedIssue",
    } <= all_resource_types


def test_openapi_exposes_research_disclaimer_and_core_routes(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "not validated for diagnosis" in schema["info"]["description"]
    for path in (
        "/api/v1/patients",
        "/api/v1/devices",
        "/api/v1/prescriptions",
        "/api/v1/sessions/{session_id}/telemetry",
        "/api/v1/interop/fhir/export",
    ):
        assert path in schema["paths"]
