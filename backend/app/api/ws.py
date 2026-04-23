from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionPool:
    """In-process WebSocket fan-out for live detections.

    For a real multi-worker deployment this would use Redis pub/sub;
    for the hackathon single-process setup it's just a list of sockets."""

    def __init__(self) -> None:
        self._sockets: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._sockets.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        text = json.dumps(payload)
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._sockets:
                try:
                    await ws.send_text(text)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._sockets.discard(ws)


pool = ConnectionPool()


@router.websocket("/ws/live")
async def live_feed(ws: WebSocket) -> None:
    await pool.connect(ws)
    try:
        while True:
            # Consume any client pings; we don't actually need their messages.
            _ = await ws.receive_text()
    except WebSocketDisconnect:
        await pool.disconnect(ws)
    except Exception:
        await pool.disconnect(ws)
