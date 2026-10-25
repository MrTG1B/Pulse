# Pulse — User Guide & Manual

**Pulse** is a lightweight, high-performance, always-on-top desktop monitor and diagnostics widget designed specifically for developers using **[AgentRouter](https://agentrouter.org/)**.

---

## 📑 Table of Contents
1. [Overview](#1-overview)
2. [System Requirements](#2-system-requirements)
3. [Installation & Launch](#3-installation--launch)
4. [Desktop Interface & Floating Controls](#4-desktop-interface--floating-controls)
5. [Configuring Your API Key](#5-configuring-your-api-key)
6. [Daily Quota Drops & Timezone Translation](#6-daily-quota-drops--timezone-translation)
7. [Quota Pool vs. Uninterrupted Models](#7-quota-pool-vs-uninterrupted-models)
8. [Diagnostic Status Codes & Troubleshooting](#8-diagnostic-status-codes--troubleshooting)
9. [Keyboard Shortcuts & Power-User Tips](#9-keyboard-shortcuts--power-user-tips)
10. [Configuration File Reference](#10-configuration-file-reference)

---

## 1. Overview

AgentRouter provides high-speed access to leading LLMs (Claude 3.5/3.7, GPT-4o, DeepSeek, GLM). Supply policies change per model. Pulse fetches the latest notices and live account catalog automatically. When a limited pool is exhausted, requests return `HTTP 402 Budget pool quota has been exhausted`.

**Pulse solves this problem by providing:**
- A floating desktop widget that sits atop your IDE (Cursor, VS Code, JetBrains).
- Real-time countdown tickers to exact quota release times in your local timezone.
- Instant connection and latency testing for any model.
- 1-click fallback to an available model, preferring AgentRouter's current recommendation.
- Automatic model, pricing and notice synchronization every five minutes, plus Sync Now.

---

## 2. System Requirements

- **Operating System:** Windows 10 or Windows 11 (64-bit).
- **Webview Engine:** Microsoft Edge WebView2 runtime (pre-installed on modern Windows 10/11).
- **Network:** Outbound HTTPS access to `https://agentrouter.org` (port 443).
- **RAM:** Memory usage varies with WebView2 and optional focus/AI features.

---

## 3. Installation & Launch

### Option A: Portable Standalone Executable (`Pulse.exe`)
1. Download `Pulse.exe` from the project release or build it locally.
2. Double-click `Pulse.exe`.
3. The floating monitor will immediately appear on your screen — **no terminal window or console pops up**.
4. Settings and API keys are saved locally in `config.json` next to the executable, making it completely portable.

### Option B: Running from Source
If running in a Python environment:
```powershell
# Install requirements
pip install -r requirements.txt

# Launch desktop floating window
python app.py

# Or launch in web browser mode
python app.py --browser
```

---

## 4. Desktop Interface & Floating Controls

```text
+-------------------------------------------------------+
|  [Pulse]  [Pin]  [Dock]  [Settings]  [Help]  [_]  [X]  |
+-------------------------------------------------------+
|  API KEY: sk-********1234                  [Edit]      |
|  CONNECTED & ACTIVE                          82 ms    |
|  GPT-6.1 Sol: Unlimited all day, recommended           |
+-------------------------------------------------------+
|  Target Model: [ GPT-6.1 Sol                       v] |
|  [ Test Connection ]   [ Test All ]   [ Sync Now ]    |
|  Models & notices sync automatically every 5 minutes |
+-------------------------------------------------------+
|  API-Key Credits & Model Usage                       |
|  Model Quota Status Overview                         |
|  Latest AgentRouter Notice                           |
+-------------------------------------------------------+
```

### Titlebar Controls:
- **📌 Pin (Always on Top):** Toggles whether Pulse stays above other windows (IDEs, browsers, terminals).
- **⤢ Mini-Dock (Compact Mode):** Collapses the window into an ultra-sleek `390×100px` floating ticker bar showing status, countdown, and latency.
- **⚙️ Settings:** Opens configuration dialog to adjust base URL, polling intervals, sound alerts, and timezone offset.
- **? Help Guide:** Opens the in-app interactive user manual and troubleshooting guide.
- **_ Minimize:** Minimizes Pulse to the Windows taskbar.
- **✕ Close:** Exits Pulse cleanly.

---

## 5. Configuring Your API Key

1. Log into your [AgentRouter Token Console](https://ps.air-outer.com/console/token).
2. Generate or copy an API Token (`sk-...`).
3. In Pulse, click **Enter Key** on the top strip (or open Settings ⚙️).
4. Paste your key and click **Save Key**.
5. Pulse validates the key locally and immediately performs an operational probe.

> **Security & Encryption:** Pulse encrypts AgentRouter API keys at rest using the **Windows Data Protection API (DPAPI)** (`CryptProtectData`). The encrypted value is bound to the Windows user context and is not stored as plaintext. The local API never exposes raw keys over HTTP, and keys are never transmitted to any third-party service.

---

## 6. Daily Quota Drops & Timezone Translation

Pulse derives quota schedules from the latest dated provider announcements. Unlimited models and temporarily unavailable models have no refill countdown. A limited model gets a countdown only when AgentRouter publishes a release time; Pulse converts that time to your configured timezone.

Audio and optional auto-focus triggers follow the selected model's published schedule. A change to unlimited supply or temporary suspension removes obsolete jobs and prevents release triggers.

Models and notices refresh automatically every five minutes, even when connection **Auto-check** is off. **Sync Now** requests an immediate update. Failed refreshes keep cached data and show a stale status. The dated announcement feed takes priority over older undated notice text.

---

## 7. Quota Pool vs. Uninterrupted Models

The latest announcement reports:

- **GPT-6.1 Sol:** unlimited all day, low multiplier, recommended first.
- **GPT-6 Astra:** unlimited all day; its old daily quota windows are removed.
- **Claude Opus 5.5:** temporarily unavailable, with no announced restoration time.

The list follows your API token's models, and base multipliers come from current pricing. Models are added and removed automatically. Temporarily suspended models remain visible and disabled. If the saved model becomes unavailable, Pulse selects the current recommended available model. Unknown supply policies are displayed without inventing a quota window.

### API-Key Credits & Model Usage

Open this panel to see reported credit usage and any API-key cap. AgentRouter's billing API expresses usage in hundredths of a billing credit, so Pulse converts it to whole credits. These credits are separate from input/output token counts.

An **Uncapped key** indicates that the API key has no configured cap; it does not reveal the remaining account balance or the shared provider pool. Unreported remaining balances and model tokens are clearly labeled **not reported**.

If AgentRouter returns recent model logs, Pulse groups their input/output tokens and request counts by model. These are recent returned records, not lifetime totals. If no logs are returned, Pulse leaves the per-model totals unreported. Changing or clearing the API key clears the previous key's cached usage and connection status.

---

## 8. Diagnostic Status Codes & Troubleshooting

| Status Code | Status Badge | Meaning | Recommended Action |
|---|---|---|---|
| **200 OK** | 🟢 **Available / Active** | The model is operational and quota is available. | You can safely make API requests. |
| **402** | 🔴 **Quota Exhausted** | The daily budget pool for Claude/GPT has been depleted. | Check the model's published schedule or use the suggested available fallback. |
| **503** | 🔴 **No Channel** | The requested model is not available in your token's current channel pool (e.g. core). | Click **Sync Now** or select another available account model. |
| **401** | 🔴 **Unauthorized** | Invalid API key or unauthorized client identity. | Check your API key in Settings. Pulse automatically uses compatible headers for Claude Code and Codex. |
| **429** | 🔴 **Rate Limited** | Too many requests within a short timeframe. | Wait 10-30 seconds before retrying. |
| **0** | ⚪ **Offline** | Cannot reach `https://agentrouter.org` or local network failure. | Check your internet connection. |

### Desktop Window Appears Only in the Taskbar

Older executables could place Pulse outside the screen on displays using 125%, 150%, or higher scaling. The launcher now accounts for display scaling and the usable monitor area, including space reserved for the taskbar.

Open the updated `Pulse.exe`. If Pulse is already running, opening it again restores its minimized, hidden, or off-screen window and keeps the current Always on Top setting. Startup diagnostics are saved in `%USERPROFILE%\.pulse\pulse.log`.

---

## 9. Keyboard Shortcuts & Power-User Tips

- <kbd>Esc</kbd> — Instantly dismisses any open modal (Help Guide, Settings, API Key drawer).
- <kbd>R</kbd> — Triggers an immediate connection test on the currently selected model.
- **Model Overview Filter Chips:** In the *Model Quota Status Overview* drawer, click chips (`All`, `🟢 Active`, `⚡ Uninterrupted`, `⏱️ Quota Pool`) to filter the current account catalog.
- **Sync Live Models:** Click **Sync Now** to refresh models and notices immediately. The background sync also updates them every five minutes.

---

## 10. Configuration File Reference

Pulse persists settings in `config.json`:

```json
{
  "api_key": "",
  "api_key_encrypted": "enc:dpapi:<encrypted value>",
  "base_url": "https://agentrouter.org",
  "selected_model": "gpt-6.1-sol",
  "refresh_interval_sec": 30,
  "auto_refresh_enabled": true,
  "always_on_top": true,
  "compact_mode": false,
  "sound_alert_enabled": true,
  "user_timezone_offset": 330
}
```

- `api_key`: Empty on disk; the runtime decrypts `api_key_encrypted` locally with Windows DPAPI.
- `base_url`: Gateway base URL (`https://agentrouter.org` or official mirror `https://ps.air-outer.com`).
- `selected_model`: Currently tracked model.
- `refresh_interval_sec`: Polling rate in seconds (15, 30, 60, 120, 300).
- `auto_refresh_enabled`: Boolean flag for automatic background polling.
- `always_on_top`: Boolean flag for desktop pin behavior.
- `compact_mode`: Boolean flag for mini-dock view.
- `sound_alert_enabled`: Boolean flag for chime on quota release.
- `user_timezone_offset`: Timezone offset in minutes (`330` = UTC+05:30 IST).
