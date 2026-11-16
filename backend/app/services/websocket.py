from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class SessionConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(session_id)
            if connections is None:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            recipients = tuple(self._connections.get(session_id, set()))
        stale: list[WebSocket] = []
        for websocket in recipients:
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            await self.disconnect(session_id, websocket)

