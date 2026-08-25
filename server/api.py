"""
FastAPI application exposed on the LAN so a paired phone can view stats and
(within the explicit allow-lists configured in Settings) browse allowed
directories or launch allowed applications.

Everything except /, /api/status and pairing endpoints requires a valid
paired-device bearer token.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from core.config import config
from core.logging_setup import remote_logger, server_logger
from core.system_stats import get_local_ip, get_stats, get_uptime_seconds
from server import pairing
from server.websocket_manager import manager

app = FastAPI(title="My Computer Dashboard")

_background_task: asyncio.Task | None = None


@app.on_event("startup")
async def _start_broadcast_loop():
    global _background_task
    _background_task = asyncio.create_task(manager.broadcast_loop())
    server_logger.info("API server started")


@app.on_event("shutdown")
async def _stop_broadcast_loop():
    if _background_task:
        _background_task.cancel()
    server_logger.info("API server stopped")


def _require_device(authorization: str | None) -> None:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not pairing.is_valid_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized - pair this device first")


# ---------------------------------------------------------------------------
# Status / stats (public on the LAN, no sensitive data)
# ---------------------------------------------------------------------------

@app.get("/api/status")
def api_status():
    return {
        "status": "running",
        "local_ip": get_local_ip(),
        "port": config.server_port,
        "connected_devices": manager.count(),
        "paired_devices": len(config.get("paired_devices", {})),
        "uptime_seconds": round(get_uptime_seconds()),
    }


@app.get("/api/stats")
def api_stats():
    return get_stats()


@app.websocket("/ws/monitor")
async def ws_monitor(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We only need to detect disconnects; broadcast_loop pushes data.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Pairing
# ---------------------------------------------------------------------------

@app.post("/api/pair/confirm")
def api_pair_confirm(payload: dict):
    code = str(payload.get("code", ""))
    device_name = str(payload.get("device_name", "")).strip()
    token = pairing.confirm_pairing(code, device_name)
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired pairing code")
    return {"token": token}


@app.get("/api/devices")
def api_devices(authorization: str | None = Header(default=None)):
    _require_device(authorization)
    return pairing.list_devices()


@app.post("/api/devices/revoke")
def api_devices_revoke(payload: dict, authorization: str | None = Header(default=None)):
    _require_device(authorization)
    token = str(payload.get("token", ""))
    ok = pairing.revoke_device(token)
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown device token")
    return {"revoked": True}


# ---------------------------------------------------------------------------
# Remote control (restricted to configured allow-lists)
# ---------------------------------------------------------------------------

@app.get("/api/files")
def api_files(dir: str, authorization: str | None = Header(default=None)):
    _require_device(authorization)
    allowed = [str(Path(p).resolve()) for p in config.allowed_directories]
    target = str(Path(dir).resolve())
    if not any(target == a or target.startswith(a + os.sep) for a in allowed):
        remote_logger.warning("Blocked directory listing outside allow-list: %r" % dir)
        raise HTTPException(status_code=403, detail="Directory not in allowed list")
    p = Path(target)
    if not p.is_dir():
        raise HTTPException(status_code=404, detail="Not a directory")
    entries = []
    for child in sorted(p.iterdir()):
        entries.append({"name": child.name, "is_dir": child.is_dir()})
    remote_logger.info("Listed directory: %r" % target)
    return {"path": target, "entries": entries}


@app.get("/api/applications")
def api_applications(authorization: str | None = Header(default=None)):
    _require_device(authorization)
    return {"applications": config.allowed_applications}


@app.post("/api/applications/launch")
def api_launch_application(payload: dict, authorization: str | None = Header(default=None)):
    _require_device(authorization)
    name = str(payload.get("name", ""))
    allowed = config.allowed_applications
    match = next((a for a in allowed if Path(a).name == name or a == name), None)
    if not match:
        remote_logger.warning("Blocked launch of non-allow-listed app: %r" % name)
        raise HTTPException(status_code=403, detail="Application not in allowed list")
    try:
        subprocess.Popen([match], shell=False)
        remote_logger.info("Launched application: %r" % match)
        return {"launched": match}
    except OSError as exc:
        remote_logger.error("Failed to launch %r: %s" % (match, exc))
        raise HTTPException(status_code=500, detail=f"Failed to launch: {exc}")


# ---------------------------------------------------------------------------
# Minimal phone-facing web dashboard
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>My Computer Dashboard</title>
  <style>
    body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 16px;
           background: #0f1115; color: #e6e6e6; }
    h1 { font-size: 20px; }
    .card { background: #171a21; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
    .row { display: flex; justify-content: space-between; margin: 6px 0; }
    .label { color: #9aa0ac; }
    input, button { font-size: 16px; padding: 10px; border-radius: 8px; border: 1px solid #333;
                    background: #10131a; color: #e6e6e6; width: 100%; box-sizing: border-box; margin-top: 6px; }
    button { background: #3b82f6; border: none; cursor: pointer; margin-top: 10px; }
    #pairSection { display: none; }
  </style>
</head>
<body>
  <h1>🖥️ My Computer Dashboard</h1>

  <div class="card" id="pairSection">
    <div class="label">Enter the pairing code shown on the PC</div>
    <input id="code" placeholder="6-digit code" inputmode="numeric" />
    <input id="deviceName" placeholder="This phone's name (e.g. Alex's iPhone)" />
    <button onclick="pair()">Pair this device</button>
    <div id="pairMsg" class="label"></div>
  </div>

  <div class="card" id="statsSection" style="display:none">
    <div class="row"><span class="label">CPU</span><span id="cpu">-</span></div>
    <div class="row"><span class="label">RAM</span><span id="ram">-</span></div>
    <div class="row"><span class="label">GPU</span><span id="gpu">-</span></div>
    <div class="row"><span class="label">Uptime</span><span id="uptime">-</span></div>
  </div>

  <script>
    const tokenKey = "mcd_token";
    function getToken() { return localStorage.getItem(tokenKey); }

    async function pair() {
      const code = document.getElementById('code').value.trim();
      const deviceName = document.getElementById('deviceName').value.trim();
      const res = await fetch('/api/pair/confirm', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({code, device_name: deviceName})
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem(tokenKey, data.token);
        init();
      } else {
        document.getElementById('pairMsg').innerText = 'Invalid or expired code.';
      }
    }

    function connectSocket() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${location.host}/ws/monitor`);
      ws.onmessage = (evt) => {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'stats') {
          const d = msg.data;
          document.getElementById('cpu').innerText = d.cpu_percent + '%';
          document.getElementById('ram').innerText = d.ram_used_gb + ' / ' + d.ram_total_gb + ' GB';
          document.getElementById('gpu').innerText = d.gpu ? (d.gpu.name + ' - ' + d.gpu.utilization_percent + '%') : 'N/A';
          const h = Math.floor(d.uptime_seconds / 3600), m = Math.floor((d.uptime_seconds % 3600) / 60);
          document.getElementById('uptime').innerText = `${h}h ${m}m`;
        }
      };
      ws.onclose = () => setTimeout(connectSocket, 2000);
    }

    function init() {
      if (getToken()) {
        document.getElementById('pairSection').style.display = 'none';
        document.getElementById('statsSection').style.display = 'block';
        connectSocket();
      } else {
        document.getElementById('pairSection').style.display = 'block';
      }
    }
    init();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def dashboard_home():
    return _DASHBOARD_HTML
