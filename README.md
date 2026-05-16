# FileScanr

A full-stack file and log scanner for support teams. Point it at network shares, log directories, Windows Event Logs, or database tables, define search strings and date filters, and get paginated, exportable results — live, via WebSocket, as the scan runs.

Built with **FastAPI** + **React 18**. Uses **ripgrep** as the scan engine when available, with a pure-Python parallel fallback. All job history and results persist in SQLite.

---

## Table of Contents

- [Deploying a Pre-Built Executable](#deploying-a-pre-built-executable)
  - [Windows](#windows)
  - [Linux](#linux)
  - [macOS](#macos)
- [Running as a Background Service](#running-as-a-background-service)
  - [Windows Service (NSSM)](#windows-service-nssm)
  - [Linux systemd](#linux-systemd)
  - [macOS launchd](#macos-launchd)
- [Configuration](#configuration)
- [Optional: Install ripgrep for Faster Scans](#optional-install-ripgrep-for-faster-scans)
- [Building from Source](#building-from-source)
- [Upgrading](#upgrading)

---

## Deploying a Pre-Built Executable

No Python installation required. Download a single file, run it, open a browser.

### 1. Download the executable

Go to the [**Releases page**](https://github.com/Ur-Average-Programmer/filescanr/releases) and download the file for your platform:

| Platform | File |
|---|---|
| Windows 10 / 11 | `filescanr-windows.exe` |
| Linux (x86-64) | `filescanr-linux` |
| macOS (Intel / Apple Silicon) | `filescanr-macos` |

---

### Windows

**Step 1 — Place the executable**

Create a folder for FileScanr and move the downloaded file into it:

```
C:\FileScanr\
    filescanr-windows.exe
```

**Step 2 — Run it**

Double-click `filescanr-windows.exe`, or from a terminal:

```cmd
cd C:\FileScanr
filescanr-windows.exe
```

You will see output like:

```
INFO:     Started server process [1234]
INFO:     Uvicorn running on http://0.0.0.0:8443
```

**Step 3 — Open the UI**

Open **http://localhost:8443** in Chrome or Edge.

**Step 4 — Allow through Windows Firewall (optional)**

If other machines on your network need to reach the tool, allow it through the firewall when prompted, or run:

```cmd
netsh advfirewall firewall add rule name="FileScanr" dir=in action=allow protocol=TCP localport=8443
```

> **Note:** On first run, Windows Defender SmartScreen may show a warning because the executable is not code-signed. Click **More info → Run anyway**.

---

### Linux

**Step 1 — Place the executable**

```bash
sudo mkdir -p /opt/filescanr
sudo mv filescanr-linux /opt/filescanr/filescanr
sudo chmod +x /opt/filescanr/filescanr
```

**Step 2 — Run it**

```bash
/opt/filescanr/filescanr
```

**Step 3 — Open the UI**

Open **http://localhost:8443** in a browser.

To run on a different port:

```bash
PORT=9000 /opt/filescanr/filescanr
```

To allow connections from other machines, open the port in your firewall:

```bash
# ufw (Ubuntu/Debian)
sudo ufw allow 8443/tcp

# firewalld (RHEL/CentOS)
sudo firewall-cmd --permanent --add-port=8443/tcp && sudo firewall-cmd --reload
```

---

### macOS

**Step 1 — Place the executable**

```bash
mkdir -p ~/FileScanr
mv filescanr-macos ~/FileScanr/filescanr
chmod +x ~/FileScanr/filescanr
```

**Step 2 — Remove the quarantine flag**

macOS blocks unsigned executables downloaded from the internet. Remove the quarantine attribute before running:

```bash
xattr -d com.apple.quarantine ~/FileScanr/filescanr
```

**Step 3 — Run it**

```bash
~/FileScanr/filescanr
```

**Step 4 — Open the UI**

Open **http://localhost:8443** in Safari, Chrome, or Firefox.

---

## Running as a Background Service

Run FileScanr automatically at startup so it is always available without keeping a terminal open.

---

### Windows Service (NSSM)

[NSSM](https://nssm.cc) (Non-Sucking Service Manager) wraps any executable as a Windows service.

**1. Download NSSM** from [nssm.cc/download](https://nssm.cc/download) and place `nssm.exe` somewhere on your PATH (e.g. `C:\Windows\System32\`).

**2. Install the service** (run Command Prompt as Administrator):

```cmd
nssm install FileScanr "C:\FileScanr\filescanr-windows.exe"
nssm set FileScanr AppDirectory "C:\FileScanr"
nssm set FileScanr DisplayName "FileScanr"
nssm set FileScanr Description "File and log scanner for support teams"
nssm set FileScanr Start SERVICE_AUTO_START
nssm start FileScanr
```

**3. Manage the service:**

```cmd
nssm stop FileScanr
nssm restart FileScanr
nssm remove FileScanr confirm
```

FileScanr will now start automatically with Windows and restart itself if it crashes.

---

### Linux systemd

**1. Create a systemd unit file:**

```bash
sudo nano /etc/systemd/system/filescanr.service
```

Paste the following (adjust the path if you installed elsewhere):

```ini
[Unit]
Description=FileScanr file and log scanner
After=network.target

[Service]
Type=simple
ExecStart=/opt/filescanr/filescanr
WorkingDirectory=/opt/filescanr
Restart=on-failure
RestartSec=5
Environment=PORT=8443

[Install]
WantedBy=multi-user.target
```

**2. Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable filescanr
sudo systemctl start filescanr
```

**3. Check status / logs:**

```bash
sudo systemctl status filescanr
sudo journalctl -u filescanr -f
```

---

### macOS launchd

**1. Create a plist file:**

```bash
nano ~/Library/LaunchAgents/com.filescanr.plist
```

Paste the following (adjust the path to match where you placed the executable):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.filescanr</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOUR_USERNAME/FileScanr/filescanr</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/YOUR_USERNAME/FileScanr</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/Users/YOUR_USERNAME/FileScanr/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/YOUR_USERNAME/FileScanr/stderr.log</string>
</dict>
</plist>
```

Replace `YOUR_USERNAME` with your macOS username.

**2. Load and start:**

```bash
launchctl load ~/Library/LaunchAgents/com.filescanr.plist
launchctl start com.filescanr
```

**3. Stop / unload:**

```bash
launchctl stop com.filescanr
launchctl unload ~/Library/LaunchAgents/com.filescanr.plist
```

---

## Configuration

On first run FileScanr creates two items next to the executable:

| Item | Purpose |
|---|---|
| `filescanr.db` | SQLite database — all scan jobs and results |
| `logs/` | Per-job structured JSON log files |

These persist across restarts and upgrades. **Do not delete them** unless you want to wipe history.

**Changing the port:**

Set the `PORT` environment variable before launching:

```cmd
:: Windows
set PORT=9000 && filescanr-windows.exe

# Linux / macOS
PORT=9000 ./filescanr
```

**Scanning network shares (Windows UNC paths):**

Enter the path directly in the UI's File Share field, e.g.:

```
\\fileserver\logs
\\192.168.1.50\c$\inetpub\logs
```

The account running FileScanr must have read access to the share.

---

## Optional: Install ripgrep for Faster Scans

FileScanr auto-detects `rg` on your PATH and uses it as the scan engine when available. On large directories ripgrep is significantly faster than the Python fallback.

| Platform | Install command |
|---|---|
| Windows (winget) | `winget install BurntSushi.ripgrep.MSVC` |
| Windows (Scoop) | `scoop install ripgrep` |
| Ubuntu / Debian | `sudo apt install ripgrep` |
| RHEL / CentOS | `sudo dnf install ripgrep` |
| macOS (Homebrew) | `brew install ripgrep` |

After installing, restart FileScanr. The Configure tab will log which engine is active at scan start.

---

## Building from Source

If you want to build the executable yourself rather than downloading a release:

```bash
git clone https://github.com/Ur-Average-Programmer/filescanr.git
cd filescanr

python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
pip install pyinstaller

# Windows
pyinstaller --onefile --name filescanr-windows \
  --add-data "frontend;frontend" --add-data "config.yaml;." \
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --collect-all starlette --collect-all fastapi \
  main.py

# Linux / macOS (use : instead of ; in --add-data)
pyinstaller --onefile --name filescanr-linux \
  --add-data "frontend:frontend" --add-data "config.yaml:." \
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --collect-all starlette --collect-all fastapi \
  main.py
```

Output is placed in the `dist/` folder.

The GitHub Actions workflow at `.github/workflows/build.yml` automates this for all three platforms simultaneously — push a `v*` tag to trigger a full release build.

---

## Upgrading

1. Stop the running FileScanr process or service.
2. Replace the executable with the new version from the [Releases page](https://github.com/Ur-Average-Programmer/filescanr/releases).
3. Restart. The existing `filescanr.db` and `logs/` folder are untouched.
