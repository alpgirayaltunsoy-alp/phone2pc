# My Computer Dashboard — Release Notes

## v1.1.0

### Added
- **Folder creation** — `POST /api/files/mkdir`, plus a "+ New Folder"
  button in the phone web dashboard's Files section. Same allow-list
  enforcement as file browsing.
- **Power control** — Shutdown, Restart, Sleep, and Lock buttons on the
  phone dashboard (`/api/power/{action}`), gated by a paired device token.
  Shutdown/restart confirm before sending; both give a 5-second OS-level
  grace period and can be cancelled from the PC.
- **Remote screen viewing** — live ~2fps JPEG stream over `/ws/screen`,
  shown in a new "Remote Control" card on the phone dashboard.
- **Remote keyboard/mouse control** — tap-to-click on the streamed screen
  image, a text field to type remotely, and quick buttons for
  Enter/Backspace/Tab/Esc (`/api/input/mouse`, `/api/input/keyboard`).
- **New Settings toggle: "Enable remote screen & input control"** —
  defaults to **off**. Screen viewing and input control require this
  *in addition to* a paired device token; everything else (stats, files,
  power) only needs pairing.

### Deliberately not added
- **Microphone and camera access.** Given this app runs silently in the
  background and auto-starts with Windows, remote audio/video capture
  would recreate the core feature set of stalkerware. Screen viewing and
  keyboard/mouse input already cover legitimate remote-desktop needs
  without that risk.

### Known limitations (carried over from v1.0.0)
- GPU stats only populate for NVIDIA cards with `nvidia-smi` on PATH.
- No HTTPS/TLS on the local web server — LAN-only use, not for exposing
  the port beyond it.
- Config file (paired devices, tokens) stored unencrypted under
  `%APPDATA%\MyComputerDashboard`.
- No auto-update mechanism.
- All paired devices share the same access level — no per-device scoping
  (e.g. one phone with power control, another view-only).
- Screen streaming is single-viewer-at-a-time per phone connection and
  capped at ~2fps — fine for occasional remote checks, not a substitute
  for a proper remote-desktop tool for extended sessions.

---

## v1.0.0 — Initial Release

First build of the Windows background dashboard app: a system-tray-resident
FastAPI server with a PySide6 native GUI, built for monitoring and
(limited, allow-listed) remote control from a phone on the same network.

### Added

**Background service behavior**
- FastAPI + WebSocket server auto-starts on launch — no manual start required.
- App launches to the system tray only; no large window opens automatically.
- Closing the native GUI window hides it instead of quitting the app.
- "Exit" in the tray menu is the only action that fully shuts down the
  server, WebSocket broadcaster, and tray icon.
- Single-instance guard prevents launching a second copy.

**System tray**
- Custom-drawn tray icon with live status color: 🟢 running / 🟡
  starting-stopping / 🔴 stopped.
- Right-click menu: Open Dashboard, Open Web Interface, Computer Status,
  Start Server, Stop Server, Restart Server, Settings, View Logs, Pair New
  Phone, Exit.
- "Computer Status" shows a quick popup with CPU/RAM/GPU/uptime without
  opening the full GUI.

**Native GUI (5 tabs)**
- *Dashboard* — live server status, local IP, port, connected device
  count, CPU/RAM/GPU usage, uptime (auto-refreshes).
- *Network* — local IP:port for the web interface, plus a "Generate
  Pairing Code" flow that shows a 6-digit code and QR code together.
- *Security* — list of paired devices with pairing timestamps and a
  Revoke action.
- *Settings* — Start with Windows toggle, Start minimized toggle, server
  port, allowed directories list, allowed applications list.
- *Logs* — four live-updating log views: Server Events, Authentication,
  Errors, Remote-Control Actions.

**Windows startup integration**
- "Start with Windows" writes/removes a per-user Registry Run key entry
  (no admin rights required) pointing at the exe with `--tray`.
- "Start minimized" controls whether the GUI opens automatically at login
  once the app is running.

**Phone access**
- Minimal web dashboard served at `http://<local-ip>:<port>/` — no app
  install needed on the phone, just a browser on the same Wi-Fi.
- Pairing: PC generates a single-use, 5-minute pairing code (shown as text
  + QR); phone submits it once to receive a permanent device token stored
  in its browser.
- Live stats pushed to the phone over WebSocket (`/ws/monitor`).
- REST endpoints for status, stats, device management, directory listing,
  and application launch — all gated behind a valid device token except
  `/`, `/api/status`, and pairing.

**Remote control (allow-list enforced)**
- Directory browsing (`/api/files`) restricted to paths under the
  configured "Allowed Directories".
- Application launching (`/api/applications/launch`) restricted to exact
  entries in "Allowed Applications". Requests outside either list are
  rejected (403) and logged to Remote-Control Actions.

**Packaging**
- `build_windows.bat` produces a single-file, windowless
  `dist\MyComputerDashboard.exe` via PyInstaller — no Python install
  required on the target machine.

### Known limitations
- GPU stats only populate for NVIDIA cards with `nvidia-smi` on PATH; AMD
  and Intel GPUs aren't read yet.
- No HTTPS/TLS on the local web server — acceptable for a trusted home
  LAN, not suitable for exposing the port beyond it (e.g. via port
  forwarding).
- Pairing codes and device tokens are stored in a local JSON config file
  under `%APPDATA%\MyComputerDashboard`, unencrypted at rest.
- No auto-update mechanism yet — new builds must be reinstalled manually.
- Single flat device list — no per-device permission scoping (all paired
  devices get the same access).

### Upgrade notes
This is the first release; no upgrade steps apply. On first launch, a
config file and log directory are created automatically under
`%APPDATA%\MyComputerDashboard`.
