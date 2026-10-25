# Changelog — Pulse

All notable changes to **Pulse** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-10-25

### Added
- Automatic background synchronization of account models, pricing multipliers, and dated AgentRouter announcements every five minutes, plus **Sync Now**.
- Cached provider data with visible stale status, account isolation, and automatic model additions/removals.
- API-key credit usage and key caps from AgentRouter billing endpoints, plus recent input/output token counts when model logs are returned. Unreported account balances and model pool quotas remain explicitly unknown.
- Desktop window recovery, single-instance restore, and optional Codex/Claude Code focus controls with Gemini gating.

### Changed
- Claude Opus 5.5 is temporarily unavailable; GPT-6 Astra is unlimited; GPT-6.1 Sol is unlimited, recommended, and shows its live low multiplier.
- Dated announcements override older policies; notice aliases match the actual API model IDs.
- The model picker, current notice, help panels, compact display, and quota schedules update from the synchronized provider data.
- Quota countdowns and auto-focus jobs use only the selected model's current published schedule. Unlimited and suspended models have no refill timer or release trigger.
- Responses API diagnostics support Sol and Astra, and suspended models are not probed.

## [1.0.0] - 2026-10-04

### Added
- **Standalone Windows Single-File Executable (`Pulse.exe`)**:
  - Fully bundled with PyInstaller (`--noconsole --onefile --icon icon.ico`).
  - No terminal / console window popup on startup.
  - Automatic asset extraction and resolution via `sys._MEIPASS`.
  - Portable persistent configuration fallback (`config.json` next to executable or in `%APPDATA%/Pulse`).
  - Multi-resolution Windows app icon (16x16 to 256x256).
- **High-Contrast Dark Theme**:
  - High-contrast industrial palette (`#0A0A0A` background, `#111111` surface, `#171717` elevated, `#242424` border, `#B8FF3D` lime accent).
  - Semantic status colors: Lime (Active / 200), Amber (Scheduled / Pool), Red (Exhausted / 402 / 503), Gray (Offline).
  - Compact mini-dock mode (`390×100px`) for zero-distraction floating status bar.
  - Pin toggle for always-on-top window placement above IDEs and terminals.
- **Precision Quota Drop Countdown & Timezone Translation**:
  - Live real-time countdown to daily AgentRouter release cycles (10:00 & 19:00 Beijing Time / 02:00 & 11:00 UTC).
  - Exact translation to local timezones including India Standard Time (`07:30 AM & 04:30 PM IST`).
  - Non-blocking Web Audio notification chime upon quota replenishment.
- **Intelligent Diagnostics & Model Routing**:
  - Automatic detection and actionable recovery advice for `HTTP 402 Budget Pool Quota Exhausted`.
  - Automatic detection and fallback advice for `HTTP 503 No Channel`.
  - 1-click fallback buttons to switch to uninterrupted models (`deepseek-v4-flash`).
  - Dynamic model discovery from AgentRouter API (`/v1/models`).
  - Batch diagnostic probe ("Test All").
  - Model category filter chips (All, Active, Uninterrupted, Quota Pool).
- **Comprehensive User Help & Documentation Modal**:
  - In-app interactive guide with 5 tabbed sections (Quick Start, Quota Drops, Models & Pools, Troubleshooting, Shortcuts).
  - Direct helper links to AgentRouter Console and status endpoints.
- **Comprehensive Developer Documentation**:
  - `LICENSE` (MIT License)
  - `SECURITY.md` (Security Policy & Vulnerability Reporting)
  - `CONTRIBUTING.md` (Contributor & Developer Guide)
  - `USER_GUIDE.md` (Comprehensive User Manual)
  - `README.md` (Project overview)

### Fixed
- Fixed potential `AttributeError` with `NoneType` stdio handles when launching PyInstaller with `--noconsole` on Windows.
- Fixed audio context autoplay restriction in WebViews by implementing gesture-unlocked audio manager.
- Fixed window control drag-event leakage by intercepting titlebar drag events on control buttons.
