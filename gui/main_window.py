from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget, QSystemTrayIcon

from gui.dashboard_tab import DashboardTab
from gui.network_tab import NetworkTab
from gui.security_tab import SecurityTab
from gui.settings_tab import SettingsTab
from gui.logs_tab import LogsTab


class MainWindow(QMainWindow):
    """
    The native configuration/status window.

    Closing this window (the [X] button) does NOT exit the application - it
    just hides the window back to the tray, since the server must keep
    running in the background. Only "Exit" on the tray menu truly quits.
    """

    def __init__(self, tray_icon: QSystemTrayIcon | None = None):
        super().__init__()
        self._tray_icon = tray_icon
        self.setWindowTitle("My Computer Dashboard")
        self.resize(640, 520)

        tabs = QTabWidget()
        tabs.addTab(DashboardTab(), "Dashboard")
        tabs.addTab(NetworkTab(), "Network")
        tabs.addTab(SecurityTab(), "Security")
        tabs.addTab(SettingsTab(), "Settings")
        tabs.addTab(LogsTab(), "Logs")
        self.setCentralWidget(tabs)

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
        if self._tray_icon is not None:
            self._tray_icon.showMessage(
                "My Computer Dashboard",
                "Still running in the background. Use the tray icon to reopen or exit.",
                QSystemTrayIcon.Information,
                3000,
            )
