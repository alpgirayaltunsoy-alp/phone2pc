"""
Tracks connected WebSocket clients (used both for the /ws/monitor stream
and for reporting "connected devices" count on the dashboard).
"""
from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket

from core.logging_setup import server_logger
from core.system_stats import get_stats


class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        server_logger.info("WebSocket client connected (total=%d)" % len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        server_logger.info("WebSocket client disconnected (total=%d)" % len(self._connections))

    def count(self) -> int:
        return len(self._connections)

    async def broadcast_loop(self, interval_seconds: float = 1.0) -> None:
        """Runs for the lifetime of the app; pushes stats to all subscribers."""
        while True:
            if self._connections:
                payload = json.dumps({"type": "stats", "data": get_stats()})
                dead = []
                for ws in list(self._connections):
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        dead.append(ws)
                if dead:
                    async with self._lock:
                        for ws in dead:
                            self._connections.discard(ws)
            await asyncio.sleep(interval_seconds)


manager = ConnectionManager()
