from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QGroupBox, QVBoxLayout

from app_context import ctx
from core.system_stats import get_local_ip, get_stats
from server.websocket_manager import manager


class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        status_box = QGroupBox("Server")
        grid = QGridLayout(status_box)
        self.state_label = QLabel("-")
        self.ip_label = QLabel("-")
        self.port_label = QLabel("-")
        self.devices_label = QLabel("-")
        self.uptime_label = QLabel("-")
        for row, (name, widget) in enumerate([
            ("Status", self.state_label),
            ("Local IP", self.ip_label),
            ("Port", self.port_label),
            ("Connected devices", self.devices_label),
            ("Uptime", self.uptime_label),
        ]):
            grid.addWidget(QLabel(name + ":"), row, 0)
            grid.addWidget(widget, row, 1)
        layout.addWidget(status_box)

        hw_box = QGroupBox("Hardware")
        hw_grid = QGridLayout(hw_box)
        self.cpu_label = QLabel("-")
        self.ram_label = QLabel("-")
        self.gpu_label = QLabel("-")
        for row, (name, widget) in enumerate([
            ("CPU", self.cpu_label),
            ("RAM", self.ram_label),
            ("GPU", self.gpu_label),
        ]):
            hw_grid.addWidget(QLabel(name + ":"), row, 0)
            hw_grid.addWidget(widget, row, 1)
        layout.addWidget(hw_box)
        layout.addStretch(1)

        ctx.server_state_changed.connect(self._on_state_changed)
        self._on_state_changed(ctx.server_state.value)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1500)
        self._refresh()

    def _on_state_changed(self, state: str) -> None:
        icon = {"running": "🟢", "starting": "🟡", "stopping": "🟡", "stopped": "🔴"}.get(state, "🔴")
        self.state_label.setText(f"{icon} {state.capitalize()}")

    def _refresh(self) -> None:
        self.ip_label.setText(get_local_ip())
        self.port_label.setText(str(ctx.config.server_port))
        self.devices_label.setText(str(manager.count()))

        stats = get_stats()
        h = int(stats["uptime_seconds"] // 3600)
        m = int((stats["uptime_seconds"] % 3600) // 60)
        self.uptime_label.setText(f"{h}h {m}m")
        self.cpu_label.setText(f'{stats["cpu_percent"]:.0f}% ({stats["cpu_count"]} cores)')
        self.ram_label.setText(f'{stats["ram_used_gb"]:.1f} / {stats["ram_total_gb"]:.1f} GB ({stats["ram_percent"]:.0f}%)')
        gpu = stats.get("gpu")
        if gpu:
            self.gpu_label.setText(f'{gpu["name"]} - {gpu["utilization_percent"]:.0f}%')
        else:
            self.gpu_label.setText("Not detected")
