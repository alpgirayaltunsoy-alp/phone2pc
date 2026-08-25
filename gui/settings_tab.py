from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QSpinBox, QPushButton,
    QListWidget, QGroupBox, QLabel, QFileDialog, QMessageBox
)

from app_context import ctx
from core import startup


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        startup_box = QGroupBox("Startup")
        startup_layout = QVBoxLayout(startup_box)
        self.start_with_windows_cb = QCheckBox("Start My Computer Dashboard with Windows")
        self.start_with_windows_cb.setChecked(ctx.config.start_with_windows)
        self.start_with_windows_cb.toggled.connect(self._on_start_with_windows_toggled)
        self.start_minimized_cb = QCheckBox("Start minimized to system tray")
        self.start_minimized_cb.setChecked(ctx.config.start_minimized)
        self.start_minimized_cb.toggled.connect(
            lambda checked: ctx.config.set("start_minimized", checked)
        )
        startup_layout.addWidget(self.start_with_windows_cb)
        startup_layout.addWidget(self.start_minimized_cb)
        layout.addWidget(startup_box)

        port_box = QGroupBox("Server")
        port_layout = QHBoxLayout(port_box)
        port_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(ctx.config.server_port)
        self.port_spin.valueChanged.connect(self._on_port_changed)
        port_layout.addWidget(self.port_spin)
        port_layout.addStretch(1)
        layout.addWidget(port_box)

        dirs_box = QGroupBox("Allowed Directories")
        dirs_layout = QVBoxLayout(dirs_box)
        self.dirs_list = QListWidget()
        self.dirs_list.addItems(ctx.config.allowed_directories)
        dirs_btn_row = QHBoxLayout()
        add_dir_btn = QPushButton("Add Directory...")
        add_dir_btn.clicked.connect(self._add_directory)
        remove_dir_btn = QPushButton("Remove Selected")
        remove_dir_btn.clicked.connect(lambda: self._remove_selected(self.dirs_list, "allowed_directories"))
        dirs_btn_row.addWidget(add_dir_btn)
        dirs_btn_row.addWidget(remove_dir_btn)
        dirs_layout.addWidget(self.dirs_list)
        dirs_layout.addLayout(dirs_btn_row)
        layout.addWidget(dirs_box)

        apps_box = QGroupBox("Allowed Applications")
        apps_layout = QVBoxLayout(apps_box)
        self.apps_list = QListWidget()
        self.apps_list.addItems(ctx.config.allowed_applications)
        apps_btn_row = QHBoxLayout()
        add_app_btn = QPushButton("Add Application...")
        add_app_btn.clicked.connect(self._add_application)
        remove_app_btn = QPushButton("Remove Selected")
        remove_app_btn.clicked.connect(lambda: self._remove_selected(self.apps_list, "allowed_applications"))
        apps_btn_row.addWidget(add_app_btn)
        apps_btn_row.addWidget(remove_app_btn)
        apps_layout.addWidget(self.apps_list)
        apps_layout.addLayout(apps_btn_row)
        layout.addWidget(apps_box)

        layout.addStretch(1)

    def _on_start_with_windows_toggled(self, checked: bool) -> None:
        try:
            startup.set_enabled(checked)
            ctx.config.set("start_with_windows", checked)
        except Exception as exc:
            QMessageBox.warning(self, "Startup setting failed", str(exc))
            self.start_with_windows_cb.setChecked(not checked)

    def _on_port_changed(self, value: int) -> None:
        ctx.config.server_port = value
        QMessageBox.information(
            self, "Restart required",
            "The new port will take effect the next time the server is restarted."
        )

    def _add_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Allowed Directory")
        if path:
            self.dirs_list.addItem(path)
            self._save_list(self.dirs_list, "allowed_directories")

    def _add_application(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Allowed Application", filter="Executables (*.exe);;All files (*)")
        if path:
            self.apps_list.addItem(path)
            self._save_list(self.apps_list, "allowed_applications")

    def _remove_selected(self, list_widget: QListWidget, config_key: str) -> None:
        for item in list_widget.selectedItems():
            list_widget.takeItem(list_widget.row(item))
        self._save_list(list_widget, config_key)

    def _save_list(self, list_widget: QListWidget, config_key: str) -> None:
        values = [list_widget.item(i).text() for i in range(list_widget.count())]
        ctx.config.set(config_key, values)
