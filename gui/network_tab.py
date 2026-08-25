from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox, QGridLayout

from app_context import ctx
from core.qr import make_qr_png_bytes
from core.system_stats import get_local_ip
from server import pairing


class NetworkTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        info_box = QGroupBox("Web Interface")
        grid = QGridLayout(info_box)
        self.url_label = QLabel("-")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(QLabel("URL:"), 0, 0)
        grid.addWidget(self.url_label, 0, 1)
        layout.addWidget(info_box)

        pair_box = QGroupBox("Pair New Phone")
        pair_layout = QVBoxLayout(pair_box)
        self.qr_label = QLabel("Click 'Generate Pairing Code' to begin.")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setMinimumHeight(220)
        self.code_label = QLabel("")
        self.code_label.setAlignment(Qt.AlignCenter)
        self.code_label.setStyleSheet("font-size: 22px; font-weight: bold; letter-spacing: 4px;")
        gen_btn = QPushButton("Generate Pairing Code")
        gen_btn.clicked.connect(self._generate_code)
        pair_layout.addWidget(self.qr_label)
        pair_layout.addWidget(self.code_label)
        pair_layout.addWidget(gen_btn)
        layout.addWidget(pair_box)
        layout.addStretch(1)

        self._refresh_url()

    def _refresh_url(self) -> None:
        self.url_label.setText(f"http://{get_local_ip()}:{ctx.config.server_port}")

    def _generate_code(self) -> None:
        self._refresh_url()
        code = pairing.generate_pairing_code()
        self.code_label.setText(code)
        url = f"http://{get_local_ip()}:{ctx.config.server_port}/?code={code}"
        png_bytes = make_qr_png_bytes(url)
        pixmap = QPixmap()
        pixmap.loadFromData(png_bytes, "PNG")
        self.qr_label.setPixmap(pixmap.scaledToHeight(220, Qt.SmoothTransformation))
