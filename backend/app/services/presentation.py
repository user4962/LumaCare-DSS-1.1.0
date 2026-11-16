from __future__ import annotations

from typing import Any

from ..database import utcnow
from ..schemas import DecisionRead, TelemetryRead
from .telemetry import IngestionResult


def websocket_telemetry_event(result: IngestionResult) -> dict[str, Any]:
    telemetry = TelemetryRead.model_validate(result.telemetry).model_dump(mode="json")
    decision = DecisionRead.model_validate(result.decision).model_dump(mode="json")
    return {
        "type": "telemetry",
        "timestamp": utcnow().isoformat().replace("+00:00", "Z"),
        "session_id": result.telemetry.session_id,
        "telemetry": telemetry,
        "decision": decision,
        "alerts_created": [alert.id for alert in result.alerts],
        "research_use_only": True,
    }

