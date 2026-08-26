"""
Central logging configuration.

Logs go to a rotating file under the app-data logs directory AND to an
in-memory ring buffer that the GUI's Logs tab reads from directly, split
into categories (server / auth / error / remote-control) via logger names.
"""
from __future__ import annotations

import collections
import logging
import logging.handlers
from datetime import datetime, timezone

from core.config import get_log_dir

MAX_RING_ENTRIES = 2000

# category -> deque of formatted strings, newest last
_ring: dict[str, collections.deque] = {
    "server": collections.deque(maxlen=MAX_RING_ENTRIES),
    "auth": collections.deque(maxlen=MAX_RING_ENTRIES),
    "error": collections.deque(maxlen=MAX_RING_ENTRIES),
    "remote": collections.deque(maxlen=MAX_RING_ENTRIES),
<<<<<<< HEAD
    "message": collections.deque(maxlen=MAX_RING_ENTRIES),
=======
>>>>>>> de07db71b4e20767c70c1c464cbf3f5c8b29fb9a
}


class RingBufferHandler(logging.Handler):
    def __init__(self, category: str):
        super().__init__()
        self.category = category

    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        _ring[self.category].append(line)
        if record.levelno >= logging.ERROR and self.category != "error":
            _ring["error"].append(line)


def get_recent(category: str, limit: int = 300) -> list[str]:
    buf = _ring.get(category)
    if buf is None:
        return []
    return list(buf)[-limit:]


def _make_logger(name: str, category: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = logging.handlers.RotatingFileHandler(
        get_log_dir() / f"{category}.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    ring_handler = RingBufferHandler(category)
    ring_handler.setFormatter(fmt)
    logger.addHandler(ring_handler)

    logger.propagate = False
    return logger


server_logger = _make_logger("mcd.server", "server")
auth_logger = _make_logger("mcd.auth", "auth")
error_logger = _make_logger("mcd.error", "error")
remote_logger = _make_logger("mcd.remote", "remote")
<<<<<<< HEAD
message_logger = _make_logger("mcd.message", "message")
=======
>>>>>>> de07db71b4e20767c70c1c464cbf3f5c8b29fb9a


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
