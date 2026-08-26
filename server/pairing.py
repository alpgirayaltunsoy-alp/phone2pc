"""
Phone pairing.

Flow:
  1. On the PC (from the tray menu or GUI), the user clicks "Pair New Phone".
     This generates a short-lived, random 6-digit pairing code and shows it
     (plus a QR code encoding the URL+code) in the GUI.
  2. The phone opens the web dashboard on the LAN and enters the code (or
     scans the QR code, which submits it automatically).
  3. POST /api/pair/confirm exchanges a valid, unexpired code for a
     permanent device token, which the phone stores and sends as
     Authorization: Bearer <token> on subsequent requests.

Codes expire after PAIRING_CODE_TTL seconds and are single-use.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from core.config import config
from core.logging_setup import auth_logger, now_iso

PAIRING_CODE_TTL = 5 * 60  # 5 minutes


@dataclass
class PendingCode:
    code: str
    expires_at: float


_pending: PendingCode | None = None


def generate_pairing_code() -> str:
    global _pending
    code = f"{secrets.randbelow(1_000_000):06d}"
    _pending = PendingCode(code=code, expires_at=time.time() + PAIRING_CODE_TTL)
    auth_logger.info("Generated new pairing code (expires in %ds)" % PAIRING_CODE_TTL)
    return code


def get_active_code() -> str | None:
    if _pending and _pending.expires_at > time.time():
        return _pending.code
    return None


def confirm_pairing(code: str, device_name: str) -> str | None:
    """Validate a pairing code and, if valid, mint + persist a device token."""
    global _pending
    if not _pending or _pending.expires_at < time.time() or _pending.code != code:
        auth_logger.warning("Rejected pairing attempt for device %r (bad/expired code)" % device_name)
        return None

    token = secrets.token_urlsafe(24)
    devices = config.get("paired_devices", {})
    devices[token] = {"name": device_name or "Unnamed phone", "paired_at": now_iso()}
    config.set("paired_devices", devices)
    _pending = None  # single-use
    auth_logger.info("Paired new device: %r" % device_name)
    return token


def is_valid_token(token: str | None) -> bool:
    if not token:
        return False
    return token in config.get("paired_devices", {})


def revoke_device(token: str) -> bool:
    devices = config.get("paired_devices", {})
    if token in devices:
        name = devices[token].get("name", token)
        del devices[token]
        config.set("paired_devices", devices)
        auth_logger.info("Revoked device: %r" % name)
        return True
    return False


def list_devices() -> list[dict]:
    devices = config.get("paired_devices", {})
    return [{"token": tok, **info} for tok, info in devices.items()]
