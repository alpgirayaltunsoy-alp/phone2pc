"""
QR code generation for phone pairing. Returns raw PNG bytes so the GUI
can load them into a QPixmap without touching the filesystem.
"""
from __future__ import annotations

import io


def make_qr_png_bytes(data: str) -> bytes:
    import qrcode

    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
