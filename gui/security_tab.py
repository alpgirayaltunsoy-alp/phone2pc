from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel
)

from server import pairing


class SecurityTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Paired devices:"))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        revoke_btn = QPushButton("Revoke Selected Device")
        revoke_btn.clicked.connect(self._revoke_selected)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(revoke_btn)
        btn_row.addWidget(refresh_btn)
        layout.addLayout(btn_row)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)
        self._refresh()

    def _refresh(self) -> None:
        self.list_widget.clear()
        for device in pairing.list_devices():
            label = f'{device["name"]}  (paired {device.get("paired_at", "?")})'
            item = QListWidgetItem(label)
            item.setData(1000, device["token"])
            self.list_widget.addItem(item)

    def _revoke_selected(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        token = item.data(1000)
        pairing.revoke_device(token)
        self._refresh()
