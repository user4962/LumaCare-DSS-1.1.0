from __future__ import annotations

from typing import Annotated

from fastapi import Header

from ..schemas import ActorContext


def get_actor(
    x_actor: Annotated[str | None, Header(alias="X-Actor")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> ActorContext:
    return ActorContext(
        actor_id=(x_actor or "anonymous-research-user")[:100],
        actor_role=(x_role or "researcher")[:80],
    )

