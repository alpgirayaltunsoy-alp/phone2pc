"""
Remote screen viewing and keyboard/mouse control.

This module is only ever reached from server/api.py, and every function
here is called behind two gates already enforced there:
  1. A valid paired-device bearer token (server/pairing.py)
  2. config.remote_control_enabled must be explicitly turned on in Settings
     (defaults to OFF)

Deliberately NOT included: microphone or camera access. See README for why.
"""
from __future__ import annotations

import io

from core.logging_setup import remote_logger


def capture_screenshot_jpeg(quality: int = 60) -> bytes:
    """Grab the current screen (primary monitor) as JPEG bytes."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitor = sct.monitors[1]  # index 0 is "all monitors combined"
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()


def move_mouse(x: int, y: int) -> None:
    import pyautogui
    pyautogui.moveTo(x, y)


def click_mouse(x: int, y: int, button: str = "left") -> None:
    import pyautogui
    pyautogui.click(x=x, y=y, button=button if button in ("left", "right", "middle") else "left")


def scroll_mouse(x: int, y: int, delta: int) -> None:
    import pyautogui
    pyautogui.moveTo(x, y)
    pyautogui.scroll(delta)


def type_text(text: str) -> None:
    import pyautogui
    pyautogui.typewrite(text, interval=0.01)


_KEY_ALIASES = {
    "enter": "enter", "backspace": "backspace", "tab": "tab", "escape": "esc",
    "esc": "esc", "space": "space", "up": "up", "down": "down", "left": "left",
    "right": "right", "delete": "delete", "home": "home", "end": "end",
    "pageup": "pageup", "pagedown": "pagedown",
}


def press_key(key: str) -> None:
    import pyautogui
    mapped = _KEY_ALIASES.get(key.lower())
    if not mapped:
        remote_logger.warning(f"Rejected unrecognized key press request: {key!r}")
        raise ValueError(f"Unsupported key: {key}")
    pyautogui.press(mapped)
