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

from fastapi import FastAPI, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from core.config import config
from core.logging_setup import message_logger, remote_logger, server_logger
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


def _require_remote_control(authorization: str | None) -> None:
    """Screen viewing and keyboard/mouse control need BOTH a valid device
    token AND the explicit 'remote_control_enabled' Settings toggle."""
    _require_device(authorization)
    if not config.remote_control_enabled:
        raise HTTPException(
            status_code=403,
            detail="Remote screen/input control is disabled - enable it in Settings on the PC first",
        )


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
    target = _resolve_allowed_path(dir)
    p = Path(target)
    if not p.is_dir():
        raise HTTPException(status_code=404, detail="Not a directory")
    entries = []
    for child in sorted(p.iterdir()):
        entries.append({"name": child.name, "is_dir": child.is_dir()})
    remote_logger.info("Listed directory: %r" % target)
    return {"path": target, "entries": entries}


@app.get("/api/directories/allowed")
def api_allowed_directories(authorization: str | None = Header(default=None)):
    _require_device(authorization)
    return {"directories": config.allowed_directories}


@app.post("/api/files/mkdir")
def api_files_mkdir(payload: dict, authorization: str | None = Header(default=None)):
    _require_device(authorization)
    parent_dir = str(payload.get("dir", ""))
    folder_name = str(payload.get("name", "")).strip()

    if not folder_name or "/" in folder_name or "\\" in folder_name or folder_name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid folder name")

    parent = _resolve_allowed_path(parent_dir)
    new_path = Path(parent) / folder_name

    # Re-check the final path itself stays inside the allow-list (defends
    # against a folder name that resolves oddly on some filesystems).
    _resolve_allowed_path(str(new_path), must_exist=False)

    if new_path.exists():
        raise HTTPException(status_code=409, detail="A file or folder with that name already exists")
    try:
        new_path.mkdir(parents=False, exist_ok=False)
        remote_logger.info("Created folder: %r" % str(new_path))
        return {"created": str(new_path)}
    except OSError as exc:
        remote_logger.error("Failed to create folder %r: %s" % (str(new_path), exc))
        raise HTTPException(status_code=500, detail=f"Failed to create folder: {exc}")


def _resolve_allowed_path(raw_path: str, must_exist: bool = True) -> str:
    """Resolve raw_path and ensure it falls inside an allowed directory."""
    allowed = [str(Path(p).resolve()) for p in config.allowed_directories]
    target = str(Path(raw_path).resolve())
    if not any(target == a or target.startswith(a + os.sep) for a in allowed):
        remote_logger.warning("Blocked path access outside allow-list: %r" % raw_path)
        raise HTTPException(status_code=403, detail="Path not in allowed list")
    return target


MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB per file


@app.get("/api/files/download")
def api_files_download(path: str, t: str = "", authorization: str | None = Header(default=None)):
    # A direct browser navigation (window.open) can't send a custom
    # Authorization header, so accept the token as a query param too -
    # same pattern as /ws/screen.
    token = t
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not pairing.is_valid_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized - pair this device first")

    target = _resolve_allowed_path(path)
    p = Path(target)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Not a file")
    remote_logger.info("Downloaded file: %r" % target)
    return FileResponse(target, filename=p.name)


@app.post("/api/files/upload")
async def api_files_upload(
    dir: str,
    file: UploadFile,
    authorization: str | None = Header(default=None),
):
    _require_device(authorization)
    target_dir = _resolve_allowed_path(dir)

    safe_name = Path(file.filename or "upload.bin").name  # strip any path components
    if safe_name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    dest = Path(target_dir) / safe_name
    _resolve_allowed_path(str(dest), must_exist=False)

    written = 0
    try:
        with open(dest, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File too large (200 MB limit)")
                out.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        remote_logger.error("Upload failed for %r: %s" % (safe_name, exc))
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")

    remote_logger.info("Uploaded file: %r (%d bytes)" % (str(dest), written))
    return {"saved_as": str(dest), "bytes": written}


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
# Power control - shutdown / restart / sleep / lock the PC
# ---------------------------------------------------------------------------

_POWER_COMMANDS = {
    "shutdown": (["shutdown", "/s", "/t", "5"], "Shutdown"),
    "restart": (["shutdown", "/r", "/t", "5"], "Restart"),
    "sleep": (["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "Sleep"),
    "lock": (["rundll32.exe", "user32.dll,LockWorkStation"], "Lock"),
    "cancel_shutdown": (["shutdown", "/a"], "Cancel pending shutdown/restart"),
}


@app.get("/api/power/actions")
def api_power_actions(authorization: str | None = Header(default=None)):
    _require_device(authorization)
    return {"actions": list(_POWER_COMMANDS.keys())}


@app.post("/api/power/{action}")
def api_power_action(action: str, authorization: str | None = Header(default=None)):
    _require_device(authorization)
    if action not in _POWER_COMMANDS:
        raise HTTPException(status_code=400, detail="Unknown power action")
    if os.name != "nt":
        # Lets the app run for local dev/testing on non-Windows machines
        # without crashing; the real commands only make sense on Windows.
        remote_logger.warning(f"Power action {action!r} requested but not on Windows - ignored")
        raise HTTPException(status_code=501, detail="Power actions are only supported on Windows")

    cmd, label = _POWER_COMMANDS[action]
    try:
        subprocess.Popen(cmd, shell=False)
        remote_logger.info(f"Power action triggered: {label} ({action})")
        return {"action": action, "label": label, "triggered": True}
    except OSError as exc:
        remote_logger.error(f"Power action {action!r} failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to run power action: {exc}")


# ---------------------------------------------------------------------------
# Clipboard sync
# ---------------------------------------------------------------------------

@app.get("/api/clipboard")
def api_clipboard_get(authorization: str | None = Header(default=None)):
    _require_device(authorization)
    from core.clipboard import get_clipboard_text
    return {"text": get_clipboard_text()}


@app.post("/api/clipboard")
def api_clipboard_set(payload: dict, authorization: str | None = Header(default=None)):
    _require_device(authorization)
    from core.clipboard import set_clipboard_text
    text = str(payload.get("text", ""))
    set_clipboard_text(text)
    remote_logger.info("Clipboard set from phone (%d chars)" % len(text))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Running processes
# ---------------------------------------------------------------------------

@app.get("/api/processes")
def api_processes_list(authorization: str | None = Header(default=None)):
    _require_device(authorization)
    from core.processes import list_processes
    return {"processes": list_processes()}


@app.post("/api/processes/kill")
def api_processes_kill(payload: dict, authorization: str | None = Header(default=None)):
    _require_device(authorization)
    from core.processes import kill_process
    pid = int(payload.get("pid", 0))
    try:
        kill_process(pid)
        return {"killed": pid}
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


# ---------------------------------------------------------------------------
# Phone -> PC messaging (shows as a tray notification on the PC)
# ---------------------------------------------------------------------------

MAX_MESSAGE_CHARS = 500


@app.post("/api/message")
def api_send_message(payload: dict, authorization: str | None = Header(default=None)):
    _require_device(authorization)
    text = str(payload.get("text", "")).strip()[:MAX_MESSAGE_CHARS]
    if not text:
        raise HTTPException(status_code=400, detail="Message text is empty")

    token = authorization.split(" ", 1)[1].strip()
    device_name = config.get("paired_devices", {}).get(token, {}).get("name", "Unknown phone")

    message_logger.info(f"{device_name}: {text}")

    from app_context import ctx
    ctx.receive_phone_message(device_name, text)

    return {"sent": True}


# ---------------------------------------------------------------------------
# Remote screen viewing + keyboard/mouse control
#
# Gated behind _require_remote_control: a valid device token is NOT enough
# on its own - the PC owner must also explicitly flip "Enable remote screen
# & input control" on in Settings (default: off). Deliberately excluded:
# microphone and camera access - see README.
# ---------------------------------------------------------------------------

@app.get("/api/screen/snapshot")
def api_screen_snapshot(authorization: str | None = Header(default=None)):
    _require_remote_control(authorization)
    from server.remote_control import capture_screenshot_jpeg
    from fastapi.responses import Response
    try:
        jpeg_bytes = capture_screenshot_jpeg()
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    except Exception as exc:
        remote_logger.error(f"Screenshot capture failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Screenshot failed: {exc}")


@app.websocket("/ws/screen")
async def ws_screen(websocket: WebSocket, token: str = ""):
    # WebSocket connections can't send an Authorization header from a
    # browser, so the token is passed as a query param instead: ?token=...
    if not pairing.is_valid_token(token) or not config.remote_control_enabled:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    from server.remote_control import capture_screenshot_jpeg
    remote_logger.info("Screen-viewing session started")
    try:
        while True:
            if not config.remote_control_enabled:
                break
            jpeg_bytes = capture_screenshot_jpeg(quality=50)
            await websocket.send_bytes(jpeg_bytes)
            await asyncio.sleep(0.5)  # ~2 fps - plenty for remote viewing over Wi-Fi
    except WebSocketDisconnect:
        pass
    finally:
        remote_logger.info("Screen-viewing session ended")


@app.post("/api/input/mouse")
def api_input_mouse(payload: dict, authorization: str | None = Header(default=None)):
    _require_remote_control(authorization)
    from server.remote_control import move_mouse, click_mouse, scroll_mouse

    action = str(payload.get("action", ""))
    x, y = int(payload.get("x", 0)), int(payload.get("y", 0))
    try:
        if action == "move":
            move_mouse(x, y)
        elif action == "click":
            click_mouse(x, y, str(payload.get("button", "left")))
        elif action == "scroll":
            scroll_mouse(x, y, int(payload.get("delta", 0)))
        else:
            raise HTTPException(status_code=400, detail="Unknown mouse action")
        remote_logger.info(f"Remote mouse action: {action} at ({x},{y})")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as exc:
        remote_logger.error(f"Remote mouse action failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/input/keyboard")
def api_input_keyboard(payload: dict, authorization: str | None = Header(default=None)):
    _require_remote_control(authorization)
    from server.remote_control import type_text, press_key

    action = str(payload.get("action", ""))
    try:
        if action == "type":
            type_text(str(payload.get("text", "")))
        elif action == "key":
            press_key(str(payload.get("key", "")))
        else:
            raise HTTPException(status_code=400, detail="Unknown keyboard action")
        remote_logger.info(f"Remote keyboard action: {action}")
        return {"ok": True}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        remote_logger.error(f"Remote keyboard action failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


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
    h2 { font-size: 15px; color: #9aa0ac; margin: 0 0 8px 0; }
    .card { background: #171a21; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
    .row { display: flex; justify-content: space-between; margin: 6px 0; align-items: center; }
    .label { color: #9aa0ac; }
    input, button { font-size: 16px; padding: 10px; border-radius: 8px; border: 1px solid #333;
                    background: #10131a; color: #e6e6e6; width: 100%; box-sizing: border-box; margin-top: 6px; }
    button { background: #3b82f6; border: none; cursor: pointer; margin-top: 10px; }
    button.danger { background: #ef4444; }
    button.secondary { background: #2b2f38; }
    .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .file-row { display: flex; justify-content: space-between; padding: 8px 4px; border-bottom: 1px solid #262b35; }
    .file-row .name { cursor: pointer; }
    .crumb { color: #60a5fa; cursor: pointer; }
    #pairSection { display: none; }
    #mainSections { display: none; }
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

  <div id="mainSections">
    <div class="card" id="statsSection">
      <h2>Status</h2>
      <div class="row"><span class="label">CPU</span><span id="cpu">-</span></div>
      <div class="row"><span class="label">RAM</span><span id="ram">-</span></div>
      <div class="row"><span class="label">GPU</span><span id="gpu">-</span></div>
      <div class="row"><span class="label">Uptime</span><span id="uptime">-</span></div>
    </div>

    <div class="card">
      <h2>Files</h2>
      <div id="breadcrumb" class="label" style="margin-bottom:8px;"></div>
      <div id="fileList"></div>
      <div class="btn-grid">
        <button class="secondary" onclick="promptNewFolder()">+ New Folder</button>
        <button class="secondary" onclick="document.getElementById('uploadInput').click()">Upload File</button>
      </div>
      <input type="file" id="uploadInput" style="display:none" onchange="uploadFile(this.files[0])" />
    </div>

    <div class="card">
      <h2>Clipboard</h2>
      <textarea id="clipboardText" rows="3" style="width:100%; box-sizing:border-box; font-size:15px;
        border-radius:8px; border:1px solid #333; background:#10131a; color:#e6e6e6; padding:10px;"></textarea>
      <div class="btn-grid">
        <button class="secondary" onclick="loadClipboard()">Get from PC</button>
        <button onclick="setClipboard()">Send to PC</button>
      </div>
    </div>

    <div class="card">
      <h2>Send a Message</h2>
      <input id="messageText" placeholder="Message to show on the PC" maxlength="500" />
      <button onclick="sendMessage()">Send</button>
      <div id="messageStatus" class="label"></div>
    </div>

    <div class="card">
      <h2>Processes</h2>
      <div id="processList" style="max-height:260px; overflow-y:auto;"></div>
      <button class="secondary" onclick="loadProcesses()">Refresh</button>
    </div>

    <div class="card">
      <h2>Power</h2>
      <div class="btn-grid">
        <button class="secondary" onclick="powerAction('lock')">Lock</button>
        <button class="secondary" onclick="powerAction('sleep')">Sleep</button>
        <button class="danger" onclick="confirmPower('restart')">Restart</button>
        <button class="danger" onclick="confirmPower('shutdown')">Shut Down</button>
      </div>
    </div>

    <div class="card">
      <h2>Remote Control</h2>
      <div id="remoteDisabledMsg" class="label" style="display:none;">
        Disabled on the PC. Turn on "Enable remote screen &amp; input control" in Settings first.
      </div>
      <div id="remoteControlBody" style="display:none;">
        <img id="screenImg" style="width:100%; border-radius:8px; touch-action:none; cursor:pointer;" />
        <div class="btn-grid" style="margin-top:8px;">
          <button class="secondary" onclick="sendKey('enter')">Enter</button>
          <button class="secondary" onclick="sendKey('backspace')">Backspace</button>
          <button class="secondary" onclick="sendKey('tab')">Tab</button>
          <button class="secondary" onclick="sendKey('esc')">Esc</button>
        </div>
        <input id="typeInput" placeholder="Type text, then press Send" />
        <button onclick="sendTyped()">Send Text</button>
      </div>
      <button class="secondary" id="remoteToggleBtn" onclick="toggleRemoteControl()">Start Remote Control</button>
    </div>
  </div>

  <script>
    const tokenKey = "mcd_token";
    function getToken() { return localStorage.getItem(tokenKey); }
    function authHeaders() { return {'Authorization': 'Bearer ' + getToken(), 'Content-Type': 'application/json'}; }

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

    // ---- Files ----
    let allowedRoots = [];
    let currentDir = null;

    async function loadAllowedRoots() {
      const res = await fetch('/api/directories/allowed', { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      allowedRoots = data.directories || [];
      if (allowedRoots.length && !currentDir) {
        currentDir = allowedRoots[0];
        loadDir(currentDir);
      } else if (!allowedRoots.length) {
        document.getElementById('fileList').innerHTML =
          '<div class="label">No allowed directories configured yet (set these in the PC app\\'s Settings tab).</div>';
      }
    }

    async function loadDir(path) {
      const res = await fetch('/api/files?dir=' + encodeURIComponent(path), { headers: authHeaders() });
      if (!res.ok) { alert('Could not open that folder.'); return; }
      const data = await res.json();
      currentDir = data.path;
      renderBreadcrumb(data.path);
      const list = document.getElementById('fileList');
      list.innerHTML = '';
      data.entries.forEach(e => {
        const row = document.createElement('div');
        row.className = 'file-row';
        row.innerHTML = `<span class="name">${e.is_dir ? '📁' : '📄'} ${e.name}</span>`;
        if (e.is_dir) {
          row.querySelector('.name').onclick = () => loadDir(data.path + '/' + e.name);
        } else {
          row.querySelector('.name').onclick = () => downloadFile(data.path + '/' + e.name);
        }
        list.appendChild(row);
      });
    }

    function downloadFile(path) {
      const url = '/api/files/download?path=' + encodeURIComponent(path) + '&t=' + encodeURIComponent(getToken());
      window.open(url, '_blank');
    }

    async function uploadFile(file) {
      if (!file || !currentDir) return;
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/files/upload?dir=' + encodeURIComponent(currentDir), {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + getToken() },
        body: form
      });
      if (res.ok) {
        loadDir(currentDir);
      } else {
        const err = await res.json().catch(() => ({}));
        alert('Upload failed: ' + (err.detail || res.status));
      }
    }

    function renderBreadcrumb(path) {
      const root = allowedRoots.find(r => path === r || path.startsWith(r));
      const bc = document.getElementById('breadcrumb');
      bc.innerHTML = '';
      if (allowedRoots.length > 1) {
        allowedRoots.forEach(r => {
          const span = document.createElement('span');
          span.className = 'crumb';
          span.innerText = '[' + r.split(/[\\\\/]/).pop() + '] ';
          span.onclick = () => loadDir(r);
          bc.appendChild(span);
        });
      }
      const rel = document.createElement('span');
      rel.innerText = path;
      bc.appendChild(rel);
    }

    async function promptNewFolder() {
      if (!currentDir) return;
      const name = prompt('New folder name:');
      if (!name) return;
      const res = await fetch('/api/files/mkdir', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ dir: currentDir, name })
      });
      if (res.ok) {
        loadDir(currentDir);
      } else {
        const err = await res.json().catch(() => ({}));
        alert('Could not create folder: ' + (err.detail || res.status));
      }
    }

    // ---- Power ----
    function confirmPower(action) {
      const label = action === 'shutdown' ? 'shut down' : 'restart';
      if (confirm(`Are you sure you want to ${label} the PC?`)) {
        powerAction(action);
      }
    }

    async function powerAction(action) {
      const res = await fetch('/api/power/' + action, { method: 'POST', headers: authHeaders() });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert('Action failed: ' + (err.detail || res.status));
      }
    }

    // ---- Clipboard ----
    async function loadClipboard() {
      const res = await fetch('/api/clipboard', { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        document.getElementById('clipboardText').value = data.text;
      }
    }

    async function setClipboard() {
      const text = document.getElementById('clipboardText').value;
      const res = await fetch('/api/clipboard', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ text })
      });
      if (!res.ok) alert('Could not update clipboard.');
    }

    // ---- Message to PC ----
    async function sendMessage() {
      const input = document.getElementById('messageText');
      const text = input.value.trim();
      if (!text) return;
      const res = await fetch('/api/message', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ text })
      });
      const status = document.getElementById('messageStatus');
      if (res.ok) {
        status.innerText = 'Sent.';
        input.value = '';
      } else {
        status.innerText = 'Failed to send.';
      }
    }

    // ---- Processes ----
    async function loadProcesses() {
      const res = await fetch('/api/processes', { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      const list = document.getElementById('processList');
      list.innerHTML = '';
      data.processes.slice(0, 60).forEach(p => {
        const row = document.createElement('div');
        row.className = 'file-row';
        const killBtn = p.protected ? '' :
          `<button class="danger" style="width:auto;padding:4px 10px;margin:0;font-size:13px;" onclick="killProcess(${p.pid})">Kill</button>`;
        row.innerHTML = `<span>${p.name} (${p.memory_mb} MB)</span>${killBtn}`;
        list.appendChild(row);
      });
    }

    async function killProcess(pid) {
      if (!confirm('Kill this process?')) return;
      const res = await fetch('/api/processes/kill', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ pid })
      });
      if (res.ok) {
        loadProcesses();
      } else {
        const err = await res.json().catch(() => ({}));
        alert('Could not kill process: ' + (err.detail || res.status));
      }
    }

    // ---- Remote screen + input control ----
    let screenSocket = null;
    let remoteActive = false;

    function toggleRemoteControl() {
      if (remoteActive) { stopRemoteControl(); } else { startRemoteControl(); }
    }

    function startRemoteControl() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      screenSocket = new WebSocket(`${proto}://${location.host}/ws/screen?token=${encodeURIComponent(getToken())}`);
      screenSocket.binaryType = 'blob';
      screenSocket.onopen = () => {
        remoteActive = true;
        document.getElementById('remoteDisabledMsg').style.display = 'none';
        document.getElementById('remoteControlBody').style.display = 'block';
        document.getElementById('remoteToggleBtn').innerText = 'Stop Remote Control';
      };
      screenSocket.onmessage = (evt) => {
        const url = URL.createObjectURL(evt.data);
        const img = document.getElementById('screenImg');
        const old = img.src;
        img.src = url;
        if (old) URL.revokeObjectURL(old);
      };
      screenSocket.onclose = (evt) => {
        remoteActive = false;
        document.getElementById('remoteControlBody').style.display = 'none';
        document.getElementById('remoteToggleBtn').innerText = 'Start Remote Control';
        if (evt.code === 4401) {
          document.getElementById('remoteDisabledMsg').style.display = 'block';
        }
      };
    }

    function stopRemoteControl() {
      if (screenSocket) screenSocket.close();
    }

    async function sendMouseAction(action, clientX, clientY, extra) {
      const img = document.getElementById('screenImg');
      const rect = img.getBoundingClientRect();
      if (!img.naturalWidth) return;
      const x = Math.round((clientX - rect.left) * (img.naturalWidth / rect.width));
      const y = Math.round((clientY - rect.top) * (img.naturalHeight / rect.height));
      await fetch('/api/input/mouse', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ action, x, y, ...extra })
      });
    }

    document.addEventListener('DOMContentLoaded', () => {
      const img = document.getElementById('screenImg');
      img.addEventListener('click', (e) => sendMouseAction('click', e.clientX, e.clientY, { button: 'left' }));
    });

    async function sendKey(key) {
      await fetch('/api/input/keyboard', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ action: 'key', key })
      });
    }

    async function sendTyped() {
      const input = document.getElementById('typeInput');
      if (!input.value) return;
      await fetch('/api/input/keyboard', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ action: 'type', text: input.value })
      });
      input.value = '';
    }

    function init() {
      if (getToken()) {
        document.getElementById('pairSection').style.display = 'none';
        document.getElementById('mainSections').style.display = 'block';
        connectSocket();
        loadAllowedRoots();
        loadClipboard();
        loadProcesses();
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
