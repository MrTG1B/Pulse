# Pulse

**Pulse** is a high-performance, always-on-top commercial desktop floating monitor and diagnostics widget designed for **[AgentRouter](https://agentrouter.org/)**.

Pulse provides real-time gateway health monitoring, automated HTTP 402/401/503 error diagnostics, secure API key management, model discovery, and precision countdown tickers for scheduled daily quota replenishments in your local timezone.

---

## 🎨 Commercial Design System & Palette

Pulse follows a modern, high-contrast dark theme:

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

### 1. Zero-Hang Diagnostics & WAF Bypass
- Uses verified allowlisted client wire images to prevent `401 unauthorized client detected` WAF rejections.
- Implements asynchronous `AbortController` timeouts and thread isolation to ensure the desktop window never freezes or triggers Windows "Not Responding" dialogs.

### 2. Intelligent HTTP 402 & 503 Handlers
- **HTTP 402 (Budget Pool Exhausted)**: Prominently displays time remaining until the next replenishment batch with 1-click fallback to active models.
- **HTTP 503 (No Channel in Group)**: Translates channel group constraints and offers 1-click switching to verified active models (`deepseek-v4-flash`).

### 3. Precision Quota Countdown & Local Time Translation
Tracks official AgentRouter release batches (10:00 & 19:00 Beijing Time / 02:00 & 11:00 UTC):
- **User Local Time (IST / UTC+05:30)**:
  - **Batch 1 (Morning)**: `07:30 AM IST`
  - **Batch 2 (Afternoon/Evening)**: `04:30 PM IST`
- Live real-time ticker (`HH:MM:SS`) with circular progress tracker and customizable sound chimes.

### 4. Dynamic Model Discovery & Live Status
- Auto-discovers models available to your token (`/v1/models`).
- Real-time latency tracking (ms) and status prefix badges in the model selector.
- 1-click **Test All** batch diagnostic probe.

### 5. Always-on-Top Floating Widget
- Native Edge WebView2 floating window with frameless draggable header bar.
- Pin toggle to stay atop IDEs (VS Code, Cursor) and terminal sessions.
- **Compact Mini-Dock**: Collapses into a sleek `390×100px` status bar showing current status, countdown, and latency.

### 6. Secure Key Management
- Local encrypted/masked storage in `config.json`.
- In-place Edit drawer with password eye toggle (`👁️`), save, and wipe options.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Dependencies: `pip install -r requirements.txt`

### Quick Launch (Windows)
Double-click `run_widget.bat` or run:
```powershell
python app.py
```

### Browser Mode
To run in your default web browser instead of a desktop window:
```powershell
python app.py --browser
```

---

## 🧪 Testing Suite

Pulse includes a complete test suite covering timezone conversions, API classification, mock gateway responses, and configuration persistence:
```powershell
python -m unittest discover tests
```

---

## 📁 Project Architecture
```
Pulse/
├── app.py                  # Desktop window launcher (pywebview)
├── server.py               # Local REST API & static file server
├── router_client.py        # AgentRouter API diagnostic engine & model catalog
├── time_service.py         # Quota release schedule & timezone calculations
├── config_manager.py       # API key persistence & config storage
├── config.json             # Local configuration file
├── requirements.txt        # Python package dependencies
├── run_widget.bat          # 1-click launcher batch script
├── static/
│   ├── index.html          # Widget UI structure
│   ├── style.css           # Commercial Dark FinTech design system
│   └── widget.js           # Frontend reactive controller
└── tests/
    ├── test_app.py
    ├── test_config_manager.py
    ├── test_router_client.py
    ├── test_server_endpoints.py
    └── test_time_service.py
```

---

## 📄 License
MIT License.
