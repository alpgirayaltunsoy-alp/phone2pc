"""
My Computer Dashboard - entry point.

Usage:
  python main.py            # launches with the main window visible
  python main.py --tray     # launches minimized to the system tray
                            # (this is the flag used by the Windows startup entry)

Behavior:
  - Starts the FastAPI/WebSocket server automatically.
  - Never opens a large window automatically; --tray (or the "start
    minimized" setting) keeps things tray-only until the user opens
    the dashboard themselves.
  - Closing the main window hides it; only "Exit" in the tray menu
    actually shuts the app (and the server) down.
"""
from __future__ import annotations

import io
import sys


def _patch_stdio_for_windowed_build() -> None:
    """
    A PyInstaller --windowed/--noconsole build has no console, so Windows
    gives the process sys.stdout/sys.stderr = None instead of a stream.
    Anything that assumes a real stream (uvicorn's logging setup calls
    stdout.isatty(), some libraries call .write()/.flush()) then crashes
    with AttributeError: 'NoneType' object has no attribute 'isatty'.

    Swap in a harmless in-memory stream before any such library loads.
    Must run before importing uvicorn/app_context/etc.
    """
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()


_patch_stdio_for_windowed_build()

from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication, QMessageBox

from app_context import ctx
from core.logging_setup import server_logger
from tray_app import TrayApplication

SINGLE_INSTANCE_KEY = "MyComputerDashboard-SingleInstanceGuard"


def _acquire_single_instance_lock() -> QSharedMemory | None:
    shared_mem = QSharedMemory(SINGLE_INSTANCE_KEY)
    # attach+detach clears a stale segment left behind by a crashed process
    if shared_mem.attach():
        shared_mem.detach()
    if not shared_mem.create(1):
        return None
    return shared_mem


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("My Computer Dashboard")

    lock = _acquire_single_instance_lock()
    if lock is None:
        QMessageBox.warning(
            None, "Already running",
            "My Computer Dashboard is already running in the system tray."
        )
        return 0

    if not QApplication.instance() or not hasattr(sys, "_mcd_tray_supported_checked"):
        from PySide6.QtWidgets import QSystemTrayIcon
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "System tray unavailable",
                                  "No system tray was detected on this system.")
            return 1

    tray_app = TrayApplication(app)

    # Always start the server automatically - the user should never have to
    # start it by hand.
    ctx.start_server()
    server_logger.info("Application launched")

    start_minimized = "--tray" in sys.argv or ctx.config.start_minimized
    if not start_minimized:
        tray_app.show_dashboard()

    exit_code = app.exec()
    lock.detach()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
