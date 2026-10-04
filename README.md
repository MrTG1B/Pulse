# Pulse

[![Latest Release](https://img.shields.io/github/v/release/MrTG1B/Pulse?style=flat-square&color=B8FF3D&label=Latest%20Release)](https://github.com/MrTG1B/Pulse/releases/latest)
[![Download Pulse.exe](https://img.shields.io/badge/Download-Pulse.exe%20(v1.0.0)-B8FF3D?style=flat-square&logo=windows&logoColor=0A0A0A&labelColor=111111)](https://github.com/MrTG1B/Pulse/releases/download/v1.0.0/Pulse.exe)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(64--bit)-0078D6?style=flat-square&logo=windows)](https://github.com/MrTG1B/Pulse/releases/latest)
[![Target Service](https://img.shields.io/badge/target%20service-agentrouter.org-B8FF3D?style=flat-square&labelColor=111111)](https://agentrouter.org)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-43%2F43%20passed-brightgreen?style=flat-square)](tests)

> ### ⚡ Quick Download
> 📦 **[Download Standalone Pulse.exe (v1.0.0)](https://github.com/MrTG1B/Pulse/releases/download/v1.0.0/Pulse.exe)** (31.5 MB) — Zero installation or Python required. Runs out of the box with no terminal window.

**Pulse** is a lightweight, high-performance, commercial-grade floating desktop monitor and telemetry widget designed specifically for **[AgentRouter](https://agentrouter.org/)**.

Pulse delivers real-time gateway health monitoring, automated HTTP 402/401/503 error diagnostics, secure API key management, dynamic model discovery, and precision countdown tickers for scheduled daily quota replenishments in your local timezone.

---

## 🎨 Commercial Dark FinTech Design System

Pulse follows a high-contrast industrial Dark FinTech aesthetic engineered for developer environments:

| Element | Hex Code | Description |
|---|---|---|
| **Background** | `#0A0A0A` | Deep contrast workspace foundation |
| **Surface** | `#111111` | Primary container cards |
| **Elevated** | `#171717` | Hover states, drawers, and active surfaces |
| **Border** | `#242424` | Crisp, subtle structural separation |
| **Primary Text** | `#F5F5F5` | High-readability header and body copy |
| **Secondary Text** | `#8A8A8A` | Subtitles, labels, and timestamps |
| **Accent (Lime)** | `#B8FF3D` | Brand identity and primary CTA |
| **Accent Subtle** | `#1D2910` | Badges and active indicator backgrounds |

### Semantic Status Indicators
- **Lime (`#B8FF3D`)** — **Available / Active**: Connected and quota available (HTTP 200).
- **Amber (`#FFB84D`)** — **Scheduled / Waiting**: Quota refill pending or channel discovery needed.
- **Red (`#FF4D4D`)** — **Exhausted / Error**: Daily budget pool exhausted (HTTP 402), unauthorized (401), or no channel (503).
- **Gray (`#666666`)** — **Offline / Unknown**: Network disconnect or unreachable gateway.

---

## 🌟 Key Capabilities

### 1. Standalone Single-File Windows Executable (No Terminal)
- Packaged as a clean, single-file `.exe` with **no console/terminal popup** on launch (`--noconsole --onefile`).
- Embedded multi-resolution icon metadata (`icon.ico`).
- Fully self-extracting runtime assets (`static/`, `config.example.json`) with zero external dependency requirements.
- Portable persistence: saves settings in `config.json` next to the executable or in `%APPDATA%/Pulse`.

### 2. Zero-Hang Diagnostics & WAF Bypass
- Employs allowlisted client wire profiles (`claude-cli/1.0.108`) to prevent `401 unauthorized client detected` Cloudflare / AgentRouter WAF blocks.
- Asynchronous `AbortController` timeouts and thread isolation guarantee the desktop window never freezes or displays Windows "Not Responding" prompts.

### 3. Intelligent HTTP 402 & 503 Handlers
- **HTTP 402 (Budget Pool Exhausted)**: Displays exact time remaining until the next replenishment batch with a 1-click fallback button to active uninterrupted models.
- **HTTP 503 (No Channel in Group)**: Translates channel group constraints and provides 1-click switching to verified active models (`deepseek-v4-flash`).

### 4. Precision Quota Countdown & Local Time Translation
Tracks official AgentRouter release batches (10:00 & 19:00 Beijing Time / 02:00 & 11:00 UTC):
- **User Local Time (IST / UTC+05:30)**:
  - **Batch 1 (Morning)**: `07:30 AM IST`
  - **Batch 2 (Afternoon/Evening)**: `04:30 PM IST`
- Live real-time ticker (`HH:MM:SS`) with progress bar and Web Audio release chime.

### 5. Dynamic Model Discovery & Live Status
- Auto-discovers models available to your token (`/v1/models`).
- Real-time latency tracking (ms) and status prefix badges in the model selector.
- 1-click **Test All** batch diagnostic probe.
- Category filter chips: `All`, `🟢 Active`, `⚡ Uninterrupted`, `⏱️ Quota Pool`.

### 6. Always-on-Top Floating Widget & Mini-Dock
- Native Microsoft Edge WebView2 frameless floating window.
- **Pin Toggle**: Keeps widget floating over code editors (Cursor, VS Code) and terminals.
- **Compact Mini-Dock**: Collapses into a sleek `390×100px` floating status bar.
- Interactive in-app **Help & User Guide** modal with tabs for rapid onboarding and troubleshooting.

### 7. Hardware-Backed Local Key Encryption (Windows DPAPI)
- Local encrypted storage using **Windows Data Protection API (DPAPI)** (`CryptProtectData`).
- Keys are encrypted with keys bound to your Windows user credentials; plaintext keys are **never stored on disk**.
- In-place Edit drawer with password eye toggle (`👁️`), save, and wipe options.
- Automatic migration of legacy unencrypted configurations on startup.

---

## 🚀 Getting Started

### Method 1: Run Standalone Executable (Recommended)
1. Download or build `Pulse.exe`.
2. Double-click `Pulse.exe` to run. No installation or Python required!

### Method 2: Run from Python Source
```powershell
# Clone repository
git clone https://github.com/MrTG1B/Pulse.git
cd Pulse

# Install dependencies
pip install -r requirements.txt

# Launch desktop floating window
python app.py

# Or launch in web browser mode
python app.py --browser
```

---

## 🏗️ Building the Single-File Executable

To compile `Pulse.exe` locally:

```powershell
# Run the Python build automation
python scripts/build_exe.py

# Or execute the batch file
.\scripts\build.bat
```

Output executable will be placed in `dist/Pulse.exe`.

---

## 🧪 Testing Suite

Pulse maintains 100% pass rates across unit and integration tests:

```powershell
python -m unittest discover -s tests
```

### Coverage:
- `test_config_manager.py`: Key persistence, masking, concurrent thread safety.
- `test_router_client.py`: Gateway health checks, HTTP 200/402/503/401 classification.
- `test_time_service.py`: UTC release slot math, IST (UTC+05:30) conversions.
- `test_server_endpoints.py`: REST endpoints, static file serving, color palette verification.

---

## 📁 Project Architecture

```
Pulse/
├── src/                    # Application backend & client source modules
│   ├── app.py              # Main desktop window launcher (pywebview)
│   ├── server.py           # Local REST API & static asset server
│   ├── router_client.py    # Diagnostic engine & model discovery
│   ├── time_service.py     # Quota release schedule & timezone calculations
│   └── config_manager.py   # Thread-safe settings & credential manager
├── static/                 # Frontend UI web application
│   ├── index.html          # Widget UI structure & Help guide
│   ├── style.css           # Commercial Dark FinTech design system
│   ├── widget.js           # Frontend reactive controller & Web Audio
│   ├── icon.png            # Webview branding asset
│   └── icon.ico            # Webview favicon asset
├── assets/                 # Brand assets & master icons
│   ├── icon.png            # High-res master logo (PNG)
│   └── icon.ico            # Multi-resolution Windows application icon (ICO)
├── docs/                   # Commercial documentation & guides
│   ├── USER_GUIDE.md       # Comprehensive user manual & troubleshooting
│   ├── SECURITY.md         # Vulnerability reporting & token encryption policy
│   ├── CONTRIBUTING.md     # Engineering standards & contribution workflow
│   └── CHANGELOG.md        # Version history & release notes
├── scripts/                # Packaging & build automation
│   ├── build_exe.py        # PyInstaller standalone executable builder
│   ├── build.bat           # 1-click executable compile script
│   └── file_version_info.txt # Windows PE VersionInfo resource definition
├── tests/                  # Automated test suite (43/43 passing)
│   ├── test_config_manager.py
│   ├── test_router_client.py
│   ├── test_server_endpoints.py
│   └── test_time_service.py
├── dist/                   # Compiled standalone binaries
│   └── Pulse.exe           # 🚀 Standalone single-file Windows executable (no terminal)
├── app.py                  # Root entry point launcher
├── run_widget.bat          # 1-click Python source launcher
├── config.example.json     # Git-safe configuration template
├── requirements.txt        # Python package dependencies
├── .gitignore              # Git ignore rules
└── LICENSE                 # Commercial-friendly MIT License
```

---

## 📚 Commercial Documentation

- [User Guide & Troubleshooting Manual](docs/USER_GUIDE.md)
- [Security Policy & Disclosures](docs/SECURITY.md)
- [Contributing Guidelines](docs/CONTRIBUTING.md)
- [Release Changelog](docs/CHANGELOG.md)
- [License](LICENSE)

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
Target Service: **[AgentRouter](https://agentrouter.org/)**.
