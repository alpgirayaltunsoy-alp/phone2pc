"""
Runs the FastAPI app via uvicorn in a background thread so the PySide6 GUI
event loop and the async server can coexist in one process, and so
start/stop/restart from the tray menu or GUI is just a thread lifecycle.
"""
from __future__ import annotations

import asyncio
import enum
import threading

import uvicorn

from core.config import config
from core.logging_setup import server_logger


class ServerState(str, enum.Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class ServerRunner:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._server: uvicorn.Server | None = None
        self._state = ServerState.STOPPED
        self._lock = threading.Lock()
        self._listeners: list = []

    @property
    def state(self) -> ServerState:
        return self._state

    def on_state_change(self, callback) -> None:
        self._listeners.append(callback)

    def _set_state(self, state: ServerState) -> None:
        self._state = state
        for cb in self._listeners:
            try:
                cb(state)
            except Exception:
                pass

    def start(self) -> None:
        with self._lock:
            if self._state in (ServerState.RUNNING, ServerState.STARTING):
                return
            self._set_state(ServerState.STARTING)

            from server.api import app  # imported here to avoid circular import at module load

            port = config.server_port
            uv_config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning", loop="asyncio")
            self._server = uvicorn.Server(uv_config)

            def _run():
                asyncio.run(self._server.serve())
                self._set_state(ServerState.STOPPED)

            self._thread = threading.Thread(target=_run, name="uvicorn-server", daemon=True)
            self._thread.start()
            server_logger.info(f"Server starting on port {port}")
            self._set_state(ServerState.RUNNING)

    def stop(self) -> None:
        with self._lock:
            if self._state != ServerState.RUNNING or not self._server:
                return
            self._set_state(ServerState.STOPPING)
            self._server.should_exit = True
            server_logger.info("Server stopping")

    def restart(self) -> None:
        self.stop()
        if self._thread:
            self._thread.join(timeout=5)
        self.start()


runner = ServerRunner()
