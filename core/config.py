"""
Persistent application configuration.

Settings are stored as JSON under the user's per-app data directory
(%APPDATA%\\MyComputerDashboard on Windows, ~/.my_computer_dashboard elsewhere
so the code can also be exercised/tested on non-Windows platforms).
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


APP_NAME = "MyComputerDashboard"


def get_app_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        path = Path(base) / APP_NAME
    else:
        path = Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_dir() -> Path:
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_PATH = get_app_data_dir() / "config.json"

DEFAULTS: dict[str, Any] = {
    "server_port": 8000,
    "start_with_windows": False,
    "start_minimized": True,
    "allowed_directories": [],
    "allowed_applications": [],
    "paired_devices": {},   # token -> {"name": str, "paired_at": iso str}
    "admin_secret": None,   # set on first run; used to sign/validate pairing codes
    # Screen viewing + remote keyboard/mouse are powerful, so they default to
    # OFF and must be explicitly turned on in Settings, on top of requiring a
    # paired device token for every request.
    "remote_control_enabled": False,
}


class ConfigManager:
    """Thread-safe JSON-backed settings store."""

    def __init__(self, path: Path = CONFIG_PATH):
        self._path = path
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self._path.exists():
                try:
                    with open(self._path, "r", encoding="utf-8") as f:
                        self._data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    self._data = {}
            merged = dict(DEFAULTS)
            merged.update(self._data)
            self._data = merged
            if not self._data.get("admin_secret"):
                self._data["admin_secret"] = secrets.token_hex(16)
            self._save()

    def _save(self) -> None:
        tmp_path = self._path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        tmp_path.replace(self._path)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            self._data.update(kwargs)
            self._save()

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    # --- convenience accessors -------------------------------------------------

    @property
    def server_port(self) -> int:
        return int(self.get("server_port", 8000))

    @server_port.setter
    def server_port(self, value: int) -> None:
        self.set("server_port", int(value))

    @property
    def start_with_windows(self) -> bool:
        return bool(self.get("start_with_windows", False))

    @property
    def start_minimized(self) -> bool:
        return bool(self.get("start_minimized", True))

    @property
    def allowed_directories(self) -> list[str]:
        return list(self.get("allowed_directories", []))

    @property
    def allowed_applications(self) -> list[str]:
        return list(self.get("allowed_applications", []))

    @property
    def paired_devices(self) -> dict[str, Any]:
        return dict(self.get("paired_devices", {}))

    @property
    def remote_control_enabled(self) -> bool:
        return bool(self.get("remote_control_enabled", False))


# Singleton used throughout the app.
config = ConfigManager()
