from __future__ import annotations

import webbrowser

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtGui import QAction

from app_context import ctx
from core.system_stats import get_local_ip, get_stats
from gui.icons import make_tray_icon
from gui.main_window import MainWindow
from server import pairing


class TrayApplication:
    def __init__(self, app: QApplication):
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)

        self.tray_icon = QSystemTrayIcon(make_tray_icon("stopped"))
        self.tray_icon.setToolTip("My Computer Dashboard")

        self.main_window = MainWindow(tray_icon=self.tray_icon)

        self._build_menu()
        self.tray_icon.activated.connect(self._on_activated)

        ctx.server_state_changed.connect(self._on_server_state_changed)
        self._on_server_state_changed(ctx.server_state.value)
<<<<<<< HEAD
        ctx.phone_message_received.connect(self._on_phone_message)
=======
>>>>>>> de07db71b4e20767c70c1c464cbf3f5c8b29fb9a

        self.tray_icon.show()

    # -- menu -------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = QMenu()

        open_dashboard = QAction("Open Dashboard", menu)
        open_dashboard.triggered.connect(self.show_dashboard)
        menu.addAction(open_dashboard)

        open_web = QAction("Open Web Interface", menu)
        open_web.triggered.connect(self._open_web_interface)
        menu.addAction(open_web)

        computer_status = QAction("Computer Status", menu)
        computer_status.triggered.connect(self._show_status_popup)
        menu.addAction(computer_status)

        menu.addSeparator()

        start_action = QAction("Start Server", menu)
        start_action.triggered.connect(ctx.start_server)
        menu.addAction(start_action)

        stop_action = QAction("Stop Server", menu)
        stop_action.triggered.connect(ctx.stop_server)
        menu.addAction(stop_action)

        restart_action = QAction("Restart Server", menu)
        restart_action.triggered.connect(ctx.restart_server)
        menu.addAction(restart_action)

        menu.addSeparator()

        settings_action = QAction("Settings", menu)
        settings_action.triggered.connect(lambda: self.show_dashboard(tab_index=3))
        menu.addAction(settings_action)

        logs_action = QAction("View Logs", menu)
        logs_action.triggered.connect(lambda: self.show_dashboard(tab_index=4))
        menu.addAction(logs_action)

        pair_action = QAction("Pair New Phone", menu)
        pair_action.triggered.connect(lambda: self.show_dashboard(tab_index=1))
        menu.addAction(pair_action)

        menu.addSeparator()

        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(exit_action)

        self.tray_icon.setContextMenu(menu)

    # -- actions ------------------------------------------------------------

    def show_dashboard(self, tab_index: int | None = None) -> None:
        if tab_index is not None:
            self.main_window.centralWidget().setCurrentIndex(tab_index)
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _open_web_interface(self) -> None:
        url = f"http://{get_local_ip()}:{ctx.config.server_port}"
        webbrowser.open(url)

    def _show_status_popup(self) -> None:
        stats = get_stats()
        gpu = stats.get("gpu")
        gpu_text = f'{gpu["name"]} - {gpu["utilization_percent"]:.0f}%' if gpu else "Not detected"
        QMessageBox.information(
            None,
            "Computer Status",
            (
                f'Server: {ctx.server_state.value}\n'
                f'Local IP: {get_local_ip()}:{ctx.config.server_port}\n'
                f'CPU: {stats["cpu_percent"]:.0f}%\n'
                f'RAM: {stats["ram_used_gb"]:.1f} / {stats["ram_total_gb"]:.1f} GB\n'
                f'GPU: {gpu_text}\n'
                f'Uptime: {int(stats["uptime_seconds"] // 3600)}h '
                f'{int((stats["uptime_seconds"] % 3600) // 60)}m'
            ),
        )

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_dashboard()

    def _on_server_state_changed(self, state: str) -> None:
        self.tray_icon.setIcon(make_tray_icon(state))
        self.tray_icon.setToolTip(f"My Computer Dashboard - {state.capitalize()}")

<<<<<<< HEAD
    def _on_phone_message(self, device_name: str, text: str) -> None:
        self.tray_icon.showMessage(
            f"Message from {device_name}",
            text,
            QSystemTrayIcon.Information,
            6000,
        )

=======
>>>>>>> de07db71b4e20767c70c1c464cbf3f5c8b29fb9a
    def exit_app(self) -> None:
        ctx.stop_server()
        self.tray_icon.hide()
        self.app.quit()
