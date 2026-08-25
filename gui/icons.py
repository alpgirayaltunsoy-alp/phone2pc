from __future__ import annotations

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont


_STATUS_COLORS = {
    "running": QColor("#22c55e"),   # green
    "starting": QColor("#eab308"),  # yellow
    "stopping": QColor("#eab308"),  # yellow
    "stopped": QColor("#ef4444"),   # red
}


def make_tray_icon(state: str = "stopped") -> QIcon:
    """A small monitor glyph with a status-colored dot in the corner."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Monitor body
    painter.setBrush(QColor("#2b2f38"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRect(6, 8, 52, 36), 6, 6)
    painter.setBrush(QColor("#0f1115"))
    painter.drawRoundedRect(QRect(11, 13, 42, 26), 3, 3)
    # Stand
    painter.setBrush(QColor("#2b2f38"))
    painter.drawRect(QRect(26, 44, 12, 8))
    painter.drawRoundedRect(QRect(16, 52, 32, 6), 3, 3)

    # Status dot
    color = _STATUS_COLORS.get(state, QColor("#ef4444"))
    painter.setBrush(color)
    painter.drawEllipse(QRect(42, 34, 18, 18))

    painter.end()
    return QIcon(pixmap)
