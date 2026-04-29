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
        """v3.0/D5.7 — concurrent fan-out with per-socket timeout.
        Previous version awaited send_text serially under the lock, so
        one slow client backed up every other subscriber. asyncio.gather
        with a 1-second timeout per socket bounds worst-case latency."""
        text = json.dumps(payload)
        # Snapshot under the lock; release before awaiting sends so a
        # slow client can't block other broadcasts.
        async with self._lock:
            sockets = list(self._sockets)

        if not sockets:
            return

        async def send_one(ws: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(ws.send_text(text), timeout=1.0)
                return None
            except Exception:
                return ws

        results = await asyncio.gather(*(send_one(s) for s in sockets), return_exceptions=False)
        dead = [s for s in results if s is not None]
        if dead:
            async with self._lock:
                for ws in dead:
                    self._sockets.discard(ws)


pool = ConnectionPool()
# v3.0/D3.3 — separate fan-out pool for the Counter-Drone Sentinel
# command-and-control channel. Kept distinct from /ws/live so a
# subscriber to detections isn't pummelled by 5 Hz scenario ticks.
c2_pool = ConnectionPool()


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


@router.websocket("/ws/c2")
async def c2_feed(ws: WebSocket) -> None:
    """Counter-Drone Sentinel state stream. 5 Hz `sentinel_tick` events
    and on-demand `sentinel_ack` events. See app.services.sentinel."""
    await c2_pool.connect(ws)
    try:
        while True:
            _ = await ws.receive_text()
    except WebSocketDisconnect:
        await c2_pool.disconnect(ws)
    except Exception:
        await c2_pool.disconnect(ws)
