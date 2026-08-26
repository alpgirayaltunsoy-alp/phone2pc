"""
Clipboard sync between the phone and the PC.

Uses pyperclip rather than Qt's QClipboard because the FastAPI server runs
on a background thread, and QClipboard is only safe to touch from the Qt
GUI (main) thread. pyperclip talks to the OS clipboard directly (via
win32clipboard on Windows) and has no such restriction.
"""
from __future__ import annotations

from core.logging_setup import remote_logger

MAX_CLIPBOARD_CHARS = 20_000  # guard against pasting something absurd from the phone


def get_clipboard_text() -> str:
    import pyperclip
    try:
        return pyperclip.paste() or ""
    except Exception as exc:
        remote_logger.error(f"Failed to read clipboard: {exc}")
        return ""


def set_clipboard_text(text: str) -> None:
    import pyperclip
    text = text[:MAX_CLIPBOARD_CHARS]
    pyperclip.copy(text)
