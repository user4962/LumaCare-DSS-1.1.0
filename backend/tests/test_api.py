from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import create_resource_graph


def nominal_telemetry(sequence: int | None = None) -> dict:
    payload = {
        "wavelength_nm": 660,
        "irradiance_mw_cm2": 20,
        "cumulative_dose_j_cm2": 0.2,
        "skin_temperature_c": 36.8,
        "spo2_percent": 98,
        "contact_detected": True,
        "battery_percent": 92,
        "signal_quality": 0.99,
    }
    if sequence is not None:
        payload["sequence"] = sequence
    return payload


def test_health_metadata_dashboard_and_seed(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["database"] == "ok"
    assert health.json()["timestamp"].endswith("Z")

    metadata = client.get("/api/v1/meta").json()
    assert metadata["research_use_only"] is True
    assert "does not implement production authentication" in metadata["authentication"]

    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["counts"] == {
        "patients": 2,
        "devices": 2,
        "prescriptions": 2,
        "sessions": 2,
        "running_sessions": 0,
        "open_alerts": 1,
    }
    assert client.get("/api/v1/overview").json()["counts"] == dashboard.json()["counts"]


def test_crud_session_lifecycle_and_audit(client: TestClient, headers: dict[str, str]) -> None:
    graph = create_resource_graph(client, headers)
    patient_id = graph["patient"]["id"]
    device_id = graph["device"]["id"]
    prescription_id = graph["prescription"]["id"]
    session_id = graph["session"]["id"]

    assert client.get(f"/api/v1/patients/{patient_id}").status_code == 200
    assert client.patch(
        f"/api/v1/patients/{patient_id}", headers=headers, json={"notes": "Updated test note"}
    ).json()["notes"] == "Updated test note"
    assert client.get(f"/api/v1/devices/{device_id}").status_code == 200
    assert client.get(f"/api/v1/protocols/{prescription_id}").status_code == 200
    assert any(item["id"] == prescription_id for item in client.get("/api/v1/protocols").json())

    started = client.post(f"/api/v1/sessions/{session_id}/start", headers=headers)
    assert started.status_code == 200
    assert started.json()["status"] == "running"
    assert started.json()["started_at"].endswith("Z")

    stopped = client.post(
        f"/api/v1/sessions/{session_id}/stop",
        headers=headers,
        json={"reason": "test_completed"},
    )
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"

    audit = client.get(
        "/api/v1/audit", params={"entity_id": session_id, "actor_id": "test-researcher"}
    ).json()
    assert {item["event_type"] for item in audit} >= {
        "session.created",
        "session.started",
        "session.stopped",
    }
    assert all(item["actor_role"] == "investigator" for item in audit)


def test_telemetry_decision_hold_alert_and_acknowledgement(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]
    assert client.post(f"/api/v1/sessions/{session_id}/start", headers=headers).status_code == 200

    nominal = client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=nominal_telemetry()
    )
    assert nominal.status_code == 201, nominal.text
    assert nominal.json()["decision"]["action"] == "ALLOW"
    assert nominal.json()["decision"]["research_use_only"] is True

    hold_payload = nominal_telemetry()
    hold_payload.update(
        {
            "cumulative_dose_j_cm2": 0.3,
            "contact_detected": False,
        }
    )
    held = client.post(
        "/api/v1/decision/evaluate",
        headers=headers,
        json={"session_id": session_id, "telemetry": hold_payload},
    )
    assert held.status_code == 200, held.text
    decision = held.json()["decision"]
    assert decision["action"] == "HOLD"
    assert "APPLICATOR_CONTACT_LOST" in decision["reason_codes"]
    rule = next(item for item in decision["fired_rules"] if item["rule_id"] == "APPLICATOR_CONTACT_LOST")
    assert set(rule) == {"rule_id", "severity", "strength", "message", "observed", "threshold"}
    alert_id = held.json()["alerts_created"][0]

    detail = client.get(f"/api/v1/sessions/{session_id}").json()
    assert detail["session"]["status"] == "safety_hold"
    assert detail["latest_decision"]["id"] == decision["id"]
    assert len(detail["telemetry"]) == 2

    acknowledged = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["acknowledged_by"] == "test-researcher"


def test_duplicate_identifiers_and_invalid_session_relations(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    duplicate = client.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "medical_record_number": "TEST-PT-100",
            "given_name": "Duplicate",
            "family_name": "Record",
            "date_of_birth": "1990-01-01",
        },
    )
    assert duplicate.status_code == 409

    seeded_patient_id = client.get("/api/v1/patients").json()[0]["id"]
    invalid = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "patient_id": seeded_patient_id,
            "device_id": graph["device"]["id"],
            "prescription_id": graph["prescription"]["id"],
        },
    )
    assert invalid.status_code == 409


def test_websocket_stream_contains_telemetry_and_decision(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]
    client.post(f"/api/v1/sessions/{session_id}/start", headers=headers)

    with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "connected"
        response = client.post(
            f"/api/v1/sessions/{session_id}/telemetry",
            headers=headers,
            json=nominal_telemetry(),
        )
        assert response.status_code == 201
        event = websocket.receive_json()
        assert event["type"] == "telemetry"
        assert event["session_id"] == session_id
        assert event["telemetry"]["skin_temperature_c"] == 36.8
        assert event["decision"]["action"] == "ALLOW"
        assert event["timestamp"].endswith("Z")
