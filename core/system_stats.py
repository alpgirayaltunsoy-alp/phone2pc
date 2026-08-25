"""
Local machine metrics used by the dashboard and the /api/stats endpoint.

GPU stats are best-effort: we try nvidia-smi (works for most discrete NVIDIA
cards without extra Python deps) and silently omit GPU info if it's not
available (integrated graphics, no drivers, non-Windows dev box, etc.).
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

import psutil

_start_time = time.time()


def get_uptime_seconds() -> float:
    return time.time() - _start_time


def get_local_ip() -> str:
    """Best-effort LAN IP (the address a phone on the same Wi-Fi would use)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        s.close()


def _gpu_stats() -> Optional[dict]:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            timeout=2,
            text=True,
        )
        line = out.strip().splitlines()[0]
        name, util, mem_used, mem_total, temp = [p.strip() for p in line.split(",")]
        return {
            "name": name,
            "utilization_percent": float(util),
            "memory_used_mb": float(mem_used),
            "memory_total_mb": float(mem_total),
            "temperature_c": float(temp),
        }
    except Exception:
        return None


def get_stats() -> dict:
    vm = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "cpu_count": psutil.cpu_count(logical=True),
        "ram_percent": vm.percent,
        "ram_used_gb": round(vm.used / (1024 ** 3), 2),
        "ram_total_gb": round(vm.total / (1024 ** 3), 2),
        "gpu": _gpu_stats(),
        "uptime_seconds": round(get_uptime_seconds()),
        "boot_time": psutil.boot_time(),
    }
