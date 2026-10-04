# Contributing to Pulse

Thank you for your interest in contributing to **Pulse**! Pulse is a high-performance, commercial-grade floating desktop widget and quota monitor for **[AgentRouter](https://agentrouter.org/)**.

---

## 🛠️ Development Setup

### 1. Prerequisites
- **Python 3.10+** (64-bit recommended)
- **Git**
- Microsoft Edge WebView2 runtime (pre-installed on Windows 10/11)

### 2. Clone & Environment Setup
```powershell
git clone https://github.com/MrTG1B/Pulse.git
cd Pulse

# Create virtual environment (optional but recommended)
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install pyinstaller pillow
```

### 3. Run Locally in Development
```powershell
# Launch Desktop Floating Widget
python app.py

# Or launch in Web Browser Mode
python app.py --browser
```

---

## 🧪 Running Tests

Pulse enforces strict test coverage across all subsystems. Always verify that all tests pass before proposing changes:

```powershell
python -m unittest discover -s tests
```

### Test Structure
- `tests/test_config_manager.py`: Key encryption, atomic writes, threading resilience.
- `tests/test_router_client.py`: Gateway health probes, HTTP 200/402/503/401 classifications.
- `tests/test_time_service.py`: UTC 02:00/11:00 release slots, local time conversions (IST).
- `tests/test_server_endpoints.py`: HTTP routes, static asset delivery, REST APIs.

---

## 🏗️ Building the Standalone Executable

To compile a single-file executable (`dist/Pulse.exe`) with no terminal window:

```powershell
python build_exe.py
# or run
.\build.bat
```

The resulting executable in `dist/Pulse.exe` embeds:
- `static/` (HTML, CSS, JS, icons)
- `config.example.json` (Template configuration)
- Multi-resolution icon metadata (`icon.ico`)

---

## 🎨 Design System & Code Style Guidelines

- **Theme Palette**:
  - Background: `#0A0A0A`
  - Surface: `#111111`
  - Elevated: `#171717`
  - Border: `#242424`
  - Primary Text: `#F5F5F5`
  - Secondary Text: `#8A8A8A`
  - Accent: `#B8FF3D` (Lime)
  - Accent Subtle: `#1D2910`
- **Semantic Status**:
  - Lime (`#B8FF3D`): Active / Available (HTTP 200)
  - Amber (`#FFB84D`): Scheduled / Waiting (Pool Release)
  - Red (`#FF4D4D`): Exhausted / Error (HTTP 402/503/401)
  - Gray (`#666666`): Offline / Unknown
- **Python**: PEP 8 compliance, clean docstrings, robust exception handling.
- **Safety**: Never log or print unmasked API tokens. Always use `config_manager.mask_key()`.

---

## 📬 Pull Request Workflow

1. Fork the repository and create a new feature branch (`git checkout -b feature/amazing-feature`).
2. Make your edits and commit with conventional messages (`feat: ...`, `fix: ...`, `docs: ...`).
3. Ensure all tests pass (`python -m unittest discover -s tests`).
4. Push to your branch and open a Pull Request against `main`.
