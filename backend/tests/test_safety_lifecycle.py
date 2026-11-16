from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models import TherapySession
from app.services.process_lock import SingleWorkerLock
from tests.conftest import create_resource_graph
from tests.test_api import nominal_telemetry


def issue_codes(response: object) -> set[str]:
    payload = response.json()  # type: ignore[attr-defined]
    detail = payload["detail"]
    return {item["code"] for item in detail["issues"]}


def test_seed_contains_no_running_session(client: TestClient) -> None:
    overview = client.get("/api/v1/overview").json()
    assert overview["counts"]["running_sessions"] == 0
    assert overview["active_sessions"] == []
    assert all(item["status"] == "completed" for item in client.get("/api/v1/sessions").json())


def test_start_fails_closed_for_missing_calibration_and_offline_device(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]
    device_id = graph["device"]["id"]

    client.patch(f"/api/v1/devices/{device_id}", headers=headers, json={"calibration_due_at": None})
    missing = client.post(f"/api/v1/sessions/{session_id}/start", headers=headers)
    assert missing.status_code == 409
    assert "CALIBRATION_MISSING" in issue_codes(missing)

    client.patch(
        f"/api/v1/devices/{device_id}",
        headers=headers,
        json={"calibration_due_at": "2099-01-01T00:00:00Z", "connectivity": "offline"},
    )
    offline = client.post(f"/api/v1/sessions/{session_id}/start", headers=headers)
    assert offline.status_code == 409
    assert "DEVICE_NOT_CONNECTED" in issue_codes(offline)
    assert client.get(f"/api/v1/devices/{device_id}").json()["connectivity"] == "offline"
    assert client.get(f"/api/v1/sessions/{session_id}").json()["session"]["status"] == "planned"


def test_prescription_validity_rechecked_on_create_start_and_ingest(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    prescription_id = graph["prescription"]["id"]
    session_id = graph["session"]["id"]

    invalid_interval = client.patch(
        f"/api/v1/prescriptions/{prescription_id}",
        headers=headers,
        json={
            "valid_from": "2026-07-13T10:00:00Z",
            "valid_until": "2026-07-13T09:00:00Z",
        },
    )
    assert invalid_interval.status_code == 422

    expired = client.patch(
        f"/api/v1/prescriptions/{prescription_id}",
        headers=headers,
        json={
            "valid_from": "2026-07-12T00:00:00Z",
            "valid_until": "2026-07-13T10:00:00Z",
        },
    )
    assert expired.status_code == 200
    start = client.post(f"/api/v1/sessions/{session_id}/start", headers=headers)
    assert start.status_code == 409
    assert "PRESCRIPTION_EXPIRED" in issue_codes(start)
    recreate = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "patient_id": graph["patient"]["id"],
            "device_id": graph["device"]["id"],
            "prescription_id": prescription_id,
        },
    )
    assert recreate.status_code == 409
    assert "PRESCRIPTION_EXPIRED" in issue_codes(recreate)


def test_ingest_invalidated_prescription_causes_auditable_hold(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]
    prescription_id = graph["prescription"]["id"]
    assert client.post(f"/api/v1/sessions/{session_id}/start", headers=headers).status_code == 200
    assert client.patch(
        f"/api/v1/prescriptions/{prescription_id}", headers=headers, json={"status": "paused"}
    ).status_code == 200

    response = client.post(
        f"/api/v1/sessions/{session_id}/telemetry",
        headers=headers,
        json=nominal_telemetry(),
    )
    assert response.status_code == 201
    assert response.json()["decision"]["action"] == "HOLD"
    assert "PRESCRIPTION_NOT_ACTIVE" in response.json()["decision"]["reason_codes"]
    assert client.get(f"/api/v1/sessions/{session_id}").json()["session"]["status"] == "safety_hold"


def test_telemetry_sequence_time_dose_and_future_bounds(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]
    client.post(f"/api/v1/sessions/{session_id}/start", headers=headers)
    first_payload = nominal_telemetry(0)
    first = client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=first_payload
    )
    assert first.status_code == 201
    first_time = datetime.fromisoformat(first.json()["telemetry"]["captured_at"].replace("Z", "+00:00"))

    skipped = nominal_telemetry(2)
    assert client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=skipped
    ).status_code == 409

    duplicate_time = nominal_telemetry(1)
    duplicate_time["captured_at"] = first_time.isoformat()
    assert client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=duplicate_time
    ).status_code == 409

    lower_dose = nominal_telemetry(1)
    lower_dose["captured_at"] = (first_time + timedelta(seconds=1)).isoformat()
    lower_dose["cumulative_dose_j_cm2"] = 0.1
    assert client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=lower_dose
    ).status_code == 409

    future = nominal_telemetry(1)
    future["captured_at"] = (datetime.now(timezone.utc) + timedelta(seconds=20)).isoformat()
    assert client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=future
    ).status_code == 409

    valid = nominal_telemetry(1)
    valid["captured_at"] = (first_time + timedelta(seconds=1)).isoformat()
    valid["cumulative_dose_j_cm2"] = 0.3
    assert client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=valid
    ).status_code == 201


def test_planned_duration_completes_session(client: TestClient, headers: dict[str, str]) -> None:
    graph = create_resource_graph(client, headers, planned_duration_seconds=1)
    session_id = graph["session"]["id"]
    started = client.post(f"/api/v1/sessions/{session_id}/start", headers=headers).json()
    captured = datetime.fromisoformat(started["started_at"].replace("Z", "+00:00")) + timedelta(seconds=1.1)
    payload = nominal_telemetry(0)
    payload["captured_at"] = captured.isoformat()
    response = client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=payload
    )
    assert response.status_code == 201, response.text
    detail = client.get(f"/api/v1/sessions/{session_id}").json()["session"]
    assert detail["status"] == "completed"
    assert detail["stop_reason"] == "planned_duration_elapsed"


def test_target_dose_delivery_completes_session_without_alert(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]
    assert client.post(f"/api/v1/sessions/{session_id}/start", headers=headers).status_code == 200
    payload = nominal_telemetry(0)
    payload["cumulative_dose_j_cm2"] = graph["prescription"]["target_dose_j_cm2"]
    response = client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=payload
    )
    assert response.status_code == 201, response.text
    decision = response.json()["decision"]
    assert decision["action"] == "COMPLETE"
    assert "TARGET_DOSE_DELIVERED" in decision["reason_codes"]
    assert decision["recommended_irradiance_mw_cm2"] == 0
    assert decision["recommended_duration_seconds"] == 0
    assert decision["estimated_additional_dose_j_cm2"] == 0
    assert decision["risk_score"] == 0
    assert response.json()["alerts_created"] == []

    detail = client.get(f"/api/v1/sessions/{session_id}").json()["session"]
    assert detail["status"] == "completed"
    assert detail["stop_reason"] == "target_dose_delivered"
    assert client.get("/api/v1/alerts", params={"session_id": session_id}).json() == []
    completed = client.get(
        "/api/v1/audit", params={"entity_id": session_id, "event_type": "session.completed"}
    ).json()
    assert len(completed) == 1
    assert completed[0]["details"]["reason"] == "target_dose_delivered"


def test_wavelength_hold_is_causal_and_cannot_be_overwritten(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]
    client.post(f"/api/v1/sessions/{session_id}/start", headers=headers)
    payload = nominal_telemetry(0)
    payload["wavelength_nm"] = 700
    held = client.post(
        f"/api/v1/sessions/{session_id}/telemetry", headers=headers, json=payload
    )
    assert held.status_code == 201
    decision = held.json()["decision"]
    assert decision["action"] == "HOLD"
    assert "OBSERVED_WAVELENGTH_MISMATCH" in decision["reason_codes"]
    rule = next(rule for rule in decision["fired_rules"] if rule["rule_id"] == "OBSERVED_WAVELENGTH_MISMATCH")
    assert rule["severity"] == "HOLD"

    assert client.post(
        f"/api/v1/sessions/{session_id}/stop", headers=headers, json={"reason": "operator"}
    ).status_code == 409
    assert client.post(
        f"/api/v1/sessions/{session_id}/inject-scenario",
        headers=headers,
        json={"scenario": "nominal"},
    ).status_code == 409
    detail = client.get(f"/api/v1/sessions/{session_id}").json()["session"]
    assert detail["status"] == "safety_hold"
    assert detail["stop_reason"] == "research_safety_rule"


def test_running_session_exclusivity_and_safety_hold_release(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    first_id = graph["session"]["id"]
    client.post(f"/api/v1/sessions/{first_id}/start", headers=headers)
    conflict = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "patient_id": graph["patient"]["id"],
            "device_id": graph["device"]["id"],
            "prescription_id": graph["prescription"]["id"],
        },
    )
    assert conflict.status_code == 409
    assert "ACTIVE_SESSION_CONFLICT" in issue_codes(conflict)

    payload = nominal_telemetry(0)
    payload["contact_detected"] = False
    assert client.post(
        f"/api/v1/sessions/{first_id}/telemetry", headers=headers, json=payload
    ).status_code == 201
    replacement = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "patient_id": graph["patient"]["id"],
            "device_id": graph["device"]["id"],
            "prescription_id": graph["prescription"]["id"],
        },
    )
    assert replacement.status_code == 201
    assert client.post(
        f"/api/v1/sessions/{replacement.json()['id']}/start", headers=headers
    ).status_code == 200


def test_sqlite_partial_unique_indexes_close_concurrent_start_race(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    second = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "patient_id": graph["patient"]["id"],
            "device_id": graph["device"]["id"],
            "prescription_id": graph["prescription"]["id"],
        },
    )
    assert second.status_code == 201
    with client.app.state.session_factory() as db:
        first_model = db.get(TherapySession, graph["session"]["id"])
        second_model = db.get(TherapySession, second.json()["id"])
        assert first_model is not None and second_model is not None
        first_model.status = "running"
        db.commit()
        second_model.status = "running"
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_duplicate_simulator_start_has_no_mutation_or_audit(
    client: TestClient, headers: dict[str, str]
) -> None:
    graph = create_resource_graph(client, headers)
    session_id = graph["session"]["id"]
    first = client.post(
        f"/api/v1/sessions/{session_id}/simulator/start",
        headers=headers,
        json={"scenario": "nominal", "interval_seconds": 1, "max_samples": 100},
    )
    assert first.status_code == 200
    before = client.get(f"/api/v1/sessions/{session_id}").json()["session"]
    second = client.post(
        f"/api/v1/sessions/{session_id}/simulator/start",
        headers=headers,
        json={"scenario": "contact_loss", "interval_seconds": 1, "max_samples": 100},
    )
    assert second.status_code == 409
    after = client.get(f"/api/v1/sessions/{session_id}").json()["session"]
    assert after["active_scenario"] == before["active_scenario"] == "nominal"
    audit = client.get(
        "/api/v1/audit", params={"entity_id": session_id, "event_type": "simulator.started"}
    ).json()
    assert len(audit) == 1
    client.post(f"/api/v1/sessions/{session_id}/simulator/stop", headers=headers)


def test_single_worker_lock_is_enforced(tmp_path: Path) -> None:
    database = tmp_path / "worker.db"
    first = SingleWorkerLock(f"sqlite:///{database}")
    second = SingleWorkerLock(f"sqlite:///{database}")
    first.acquire()
    try:
        with pytest.raises(RuntimeError, match="run one worker"):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()
