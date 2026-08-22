"""
checklist 4.1: real-time transaction feed over WebSocket.

Every scored transaction is fanned out to all connected dashboard clients
as it happens, instead of each browser tab polling /api/v1/score on its
own timer — this is what lets multiple analysts watch the same live feed.
Broadcasting is best-effort: a slow or dead socket is dropped rather than
blocking the score request that triggered it (see routers/score.py,
which schedules the broadcast onto the event loop via
run_coroutine_threadsafe since scoring itself runs in a worker thread).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ws"])


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self._connections:
            return
        message = json.dumps(payload)
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)


@router.websocket("/ws/transactions")
async def transactions_feed(ws: WebSocket) -> None:
    manager: ConnectionManager = ws.app.state.ws_manager
    await manager.connect(ws)
    try:
        while True:
            # Clients don't need to send anything; just keep the socket
            # open and clean up once the browser tab closes it.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
