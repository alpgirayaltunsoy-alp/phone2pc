"""
"Start with Windows" support.

Uses the per-user Registry Run key (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)
so no admin privileges are required. This is the standard, low-friction way
for a normal desktop app to launch at login.
"""
from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "MyComputerDashboard"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _get_launch_command() -> str:
    """
    Build the command line used to relaunch the app at login.

    When frozen by PyInstaller, sys.executable IS the app exe, so we call it
    directly. When running from source (python main.py), we relaunch through
    the same interpreter for development convenience.
    """
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return f'"{exe}" --tray'
    else:
        exe = Path(sys.executable)
        script = Path(__file__).resolve().parent.parent / "main.py"
        return f'"{exe}" "{script}" --tray'


def is_enabled() -> bool:
    if not _is_windows():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool) -> None:
    if not _is_windows():
        # Allow the rest of the app (settings UI, config toggle) to work
        # on non-Windows dev machines without crashing.
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _get_launch_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
