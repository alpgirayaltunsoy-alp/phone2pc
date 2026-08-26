"""
Running-process list and kill, for the phone's "Processes" view.

Killing a process from a phone is powerful enough to break the PC (kill
explorer.exe, a display driver helper, or this app's own process) so a
hard-coded protected list is enforced regardless of what the caller asks
for - there is no setting that overrides this.
"""
from __future__ import annotations

import os

import psutil

from core.logging_setup import remote_logger

# Case-insensitive names that can never be killed remotely, even by an
# authenticated, paired device. This is not user-configurable on purpose.
PROTECTED_PROCESS_NAMES = {
    "system", "system idle process", "registry",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "svchost.exe", "dwm.exe", "explorer.exe", "fontdrvhost.exe",
    "sihost.exe", "taskhostw.exe", "userinit.exe", "logonui.exe",
    "mycomputerdashboard.exe",  # never let a phone kill this app itself
}


def list_processes() -> list[dict]:
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "?",
                "cpu_percent": round(p.cpu_percent(interval=None), 1),
                "memory_mb": round((info["memory_info"].rss if info["memory_info"] else 0) / (1024 ** 2), 1),
                "protected": (info["name"] or "").lower() in PROTECTED_PROCESS_NAMES,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x["memory_mb"], reverse=True)
    return procs


def kill_process(pid: int) -> None:
    if pid == os.getpid():
        raise ValueError("Refusing to kill this application's own process")
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        raise ValueError(f"No process with pid {pid}")

    name = (p.name() or "").lower()
    if name in PROTECTED_PROCESS_NAMES:
        remote_logger.warning(f"Blocked attempt to kill protected process: {name} (pid {pid})")
        raise ValueError(f"{p.name()} is a protected system process and cannot be killed remotely")

    p.terminate()
    remote_logger.info(f"Killed process: {name} (pid {pid})")
