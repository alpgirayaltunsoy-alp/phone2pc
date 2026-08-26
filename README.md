# My Computer Dashboard

![License](https://img.shields.io/badge/license-GPL--3.0-orangered)
![Version](https://img.shields.io/badge/version-1.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![Status](https://img.shields.io/badge/status-active-success)



## Architecture

```
Windows
│
├── MyComputerDashboard.exe
│   │
│   ├── PySide6 GUI          (gui/, app_context.py)
│   ├── System Tray          (tray_app.py, gui/icons.py)
│   ├── FastAPI Server       (server/api.py, server/runner.py)
│   ├── WebSocket Server     (server/websocket_manager.py)
│   └── Monitoring Services  (core/system_stats.py)
│
└── Windows Startup (Registry Run key)
        │
        └── Automatically launches application (core/startup.py)
```

- **main.py** — entry point; single-instance guard, starts the server
  automatically, shows or hides the main window based on the
  `--tray` flag / "start minimized" setting.
- **app_context.py** — shared object wiring config + server runner + Qt
  signals together, used by both the tray and the GUI.
- **tray_app.py** — the `QSystemTrayIcon`, its right-click menu, and the
  green/yellow/red status icon.
- **gui/** — the native PySide6 window (`main_window.py`) and its five tabs:
  Dashboard, Network, Security, Settings, Logs.
- **server/** — the FastAPI app (`api.py`), the WebSocket
  connection/broadcast manager (`websocket_manager.py`), device pairing
  (`pairing.py`), and the uvicorn-in-a-thread lifecycle manager
  (`runner.py`) used for Start/Stop/Restart.
- **core/** — cross-cutting concerns: JSON settings persistence
  (`config.py`), the Windows Registry "start with Windows" toggle
  (`startup.py`), rotating file + in-memory ring-buffer logging
  (`logging_setup.py`), CPU/RAM/GPU stats (`system_stats.py`), and QR code
  generation for pairing (`qr.py`).

## Running from source

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Pass `--tray` to start minimized (this is what the Windows startup entry
uses):

```bat
python main.py --tray
```

## Phone pairing

1. On the PC, open the tray menu → **Pair New Phone** (or the Network tab).
2. Click **Generate Pairing Code**. A 6-digit code and QR code appear
   (valid for 5 minutes, single-use).
3. On the phone, connect to the same Wi-Fi network and open
   `http://<PC's local IP>:8000` in a browser (shown on the Network tab).
4. Enter the code (or scan the QR code, which encodes the same URL+code)
   and give the device a name. The phone stores a permanent pairing token
   and from then on sees live stats without re-pairing.
5. Revoke access any time from the **Security** tab.

## Background behavior

- The server starts automatically on launch — nothing to start manually.
- Closing the main window (the **X** button) only hides it; the server,
  WebSocket broadcaster, and tray icon keep running.
- Only **Exit** in the tray menu fully shuts the app down (server, sockets,
  and tray icon are all stopped cleanly).
- **Settings → Start with Windows** registers the exe in the per-user
  Registry `Run` key (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`),
  so no admin rights are needed. **Start minimized** controls whether the
  main window opens automatically at login.

## Building the standalone .exe

```bat
build_windows.bat
```

This creates `dist\MyComputerDashboard.exe` — a single-file, windowless
executable (no visible console) that end users can run without installing
Python. Point a shortcut or the Registry Run key at that file.

## Security notes

This app is intended for use on a trusted home/local network only:

- The web dashboard and REST API bind to `0.0.0.0` so phones on the same
  Wi-Fi can reach them, but nothing is exposed beyond the LAN unless you
  configure port forwarding yourself (not recommended).
- Every endpoint beyond basic status/stats requires a paired-device
  bearer token; pairing requires physical access to the PC's GUI to read
  the one-time code.
- Remote file browsing, folder creation, and app launching are hard-restricted
  to the directories/applications you explicitly allow-list in Settings —
  nothing outside those lists is reachable from a phone, even with a valid
  token.
- Remote screen viewing and keyboard/mouse control require a **second,
  explicit opt-in** on top of pairing: "Enable remote screen & input
  control" in Settings, which defaults to **off**.
- Power actions (shutdown/restart/sleep/lock) only require a paired
  device token, since they can't be used to access data or files.
- **Microphone and camera access are intentionally not implemented.**
  Combined with this app's background/auto-start design, remote audio/video
  capture is the signature feature set of covert surveillance (stalkerware)
  tools, and that risk isn't worth the convenience. Screen viewing plus
  keyboard/mouse control already cover legitimate remote-desktop use cases
  without exposing anyone near the PC to being recorded without their
  knowledge.
