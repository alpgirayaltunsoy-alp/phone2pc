from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QPlainTextEdit

from core.logging_setup import get_recent


class LogsTab(QWidget):
    CATEGORIES = [
        ("Server Events", "server"),
        ("Authentication", "auth"),
        ("Errors", "error"),
        ("Remote-Control Actions", "remote"),
        ("Messages", "message"),
    ]

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self._views: dict[str, QPlainTextEdit] = {}
        for label, category in self.CATEGORIES:
            view = QPlainTextEdit()
            view.setReadOnly(True)
            view.setMaximumBlockCount(5000)
            self._views[category] = view
            self.tabs.addTab(view, label)
        layout.addWidget(self.tabs)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)
        self._refresh()

    def _refresh(self) -> None:
        for _, category in self.CATEGORIES:
            view = self._views[category]
            lines = get_recent(category)
            text = "\n".join(lines)
            if view.toPlainText() != text:
                scrollbar = view.verticalScrollBar()
                at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
                view.setPlainText(text)
                if at_bottom:
                    scrollbar.setValue(scrollbar.maximum())
