from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditEvent
from ..schemas import ActorContext


def add_audit_event(
    db: Session,
    actor: ActorContext,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor.actor_id,
        actor_role=actor.actor_role,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    )
    db.add(event)
    return event

