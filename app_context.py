"""
Small shared-state hub so the tray icon, main window, and server runner can
all react to each other without importing each other directly.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from core.config import config
from server.runner import ServerState, runner


class AppContext(QObject):
    server_state_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.config = config
        self.runner = runner
        runner.on_state_change(lambda state: self.server_state_changed.emit(state.value))

    def start_server(self) -> None:
        self.runner.start()

    def stop_server(self) -> None:
        self.runner.stop()

    def restart_server(self) -> None:
        self.runner.restart()

    @property
    def server_state(self) -> ServerState:
        return self.runner.state


# Single shared instance for the process.
ctx = AppContext()
