# Pulse — Commercial User Guide & Manual

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

AgentRouter provides high-speed access to leading LLMs (Claude 3.5/3.7, GPT-4o, DeepSeek, GLM). However, Claude and GPT models operate under daily budget pool limits that refresh twice per day. When a pool is exhausted, requests return `HTTP 402 Budget pool quota has been exhausted`.

**Pulse solves this problem by providing:**
- A floating desktop widget that sits atop your IDE (Cursor, VS Code, JetBrains).
- Real-time countdown tickers to exact quota release times in your local timezone.
- Instant connection and latency testing for any model.
- 1-click fallback to **uninterrupted models** (such as DeepSeek V4 Flash) that have zero quota limits.
- Dynamic model discovery from AgentRouter's live API.

---

## 2. System Requirements

- **Operating System:** Windows 10 or Windows 11 (64-bit).
- **Webview Engine:** Microsoft Edge WebView2 runtime (pre-installed on modern Windows 10/11).
- **Network:** Outbound HTTPS access to `https://agentrouter.org` (port 443).
- **RAM:** Less than 45 MB typical memory footprint.

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

```
+-------------------------------------------------------+
|  [Pulse] 🟢  [📌 Pin]  [⤢ Dock]  [⚙️]  [?]  [_]  [✕]   |  <- Draggable Titlebar
+-------------------------------------------------------+
|  🔑 API KEY: sk-••••••••1234      [Edit] [Show]       |  <- Key Quick-Bar
+-------------------------------------------------------+
|  🟢 CONNECTED & ACTIVE                    142 ms       |  <- Status & Latency Card
|  Model 'deepseek-v4-flash' is operational.            |
+-------------------------------------------------------+
|  NEXT QUOTA RELEASE                          [Batch 1] |  <- Quota Countdown Card
|  01 : 45 : 22  (HOURS : MINS : SECS)                  |
|  [=======================>            ] 68%            |  <- Cycle Progress Bar
|  When in My Local Time: Today, 07:30 AM (IST)         |
+-------------------------------------------------------+
|  Target Model: [ ⚡ DeepSeek V4 Flash       ▼ ]       |  <- Model Selector
|  [ ⚡ Test Connection ]   [ Test All ]   [ Discover ]  |
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

> **Security & Encryption:** Your API key is encrypted at rest using the **Windows Data Protection API (DPAPI)** (`CryptProtectData`). The encryption key is tied to your Windows user account; plaintext keys are **never stored on disk**. It is never sent to any remote server other than direct HTTPS diagnostic requests to `https://agentrouter.org`.

---

## 6. Daily Quota Drops & Timezone Translation

AgentRouter replenishes the Claude and GPT shared budget pools twice daily:

| Batch | Beijing Time (CST, UTC+08:00) | Universal Time (UTC) | India Standard Time (IST, UTC+05:30) |
|---|---|---|---|
| **Batch 1 (Morning)** | **10:00 AM CST** | **02:00 UTC** | **07:30 AM IST** |
| **Batch 2 (Evening)** | **07:00 PM CST** | **11:00 UTC** | **04:30 PM IST** |

### Automatic Local Time Conversion:
Pulse automatically converts these drop times into your local time (defaulting to IST, UTC+05:30, or auto-detected from your system clock in Settings).

### Audio Chime Alert:
When the countdown ticker hits `00:00:00`, Pulse plays a subtle audio chime (if 🔔 enabled) and refreshes model status automatically.

---

## 7. Quota Pool vs. Uninterrupted Models

AgentRouter classifies models into two operational categories:

### 1. Quota Pool Models (Limited Daily Supply)
- **Active Models:** `claude-opus-4-8`, `claude-opus-5`, `gpt-6-astra`.
- **Behavior:** These models share a daily quota pool. When the pool runs dry, requests fail with `HTTP 402 Budget pool quota has been exhausted`.
- **Recovery:** Wait for the next scheduled drop batch (07:30 AM or 04:30 PM IST), or switch to an uninterrupted model.

### 2. ⚡ Uninterrupted Models (Zero Pool Lock)
- **Active Model:** `deepseek-v4-flash`.
- **Behavior:** **This model is NOT restricted by the daily pool limit!** It is always active and ready for coding, chat, and reasoning.
- **Pulse Recommendation:** Whenever Claude is exhausted (402), Pulse presents an instant 1-click button to switch to `deepseek-v4-flash`.

---

## 8. Diagnostic Status Codes & Troubleshooting

| Status Code | Status Badge | Meaning | Recommended Action |
|---|---|---|---|
| **200 OK** | 🟢 **Available / Active** | The model is operational and quota is available. | You can safely make API requests. |
| **402** | 🔴 **Quota Exhausted** | The daily budget pool for Claude/GPT has been depleted. | Check the countdown for the next batch, or click **Switch to DeepSeek V4 Flash**. |
| **503** | 🔴 **No Channel** | The requested model is not available in your token's current channel pool (e.g. core). | Click **Discover** or select an active model like `deepseek-v4-flash`. |
| **401** | 🔴 **Unauthorized** | Invalid API key or client identity blocked by WAF. | Check your API key in Settings. Pulse automatically uses allowlisted headers. |
| **429** | 🔴 **Rate Limited** | Too many requests within a short timeframe. | Wait 10-30 seconds before retrying. |
| **0** | ⚪ **Offline** | Cannot reach `https://agentrouter.org` or local network failure. | Check your internet connection. |

---

## 9. Keyboard Shortcuts & Power-User Tips

- <kbd>Esc</kbd> — Instantly dismisses any open modal (Help Guide, Settings, API Key drawer).
- <kbd>R</kbd> — Triggers an immediate connection test on the currently selected model.
- **Model Overview Filter Chips:** In the *Model Quota Status Overview* drawer, click chips (`All`, `🟢 Active`, `⚡ Uninterrupted`, `⏱️ Quota Pool`) to instantly filter through 18+ models.
- **Discover Live Models:** Click the **Discover** button to query `/v1/models` on AgentRouter and discover newly added models available to your specific account token.

---

## 10. Configuration File Reference

Pulse persists settings in `config.json`:

```json
{
  "api_key": "sk-your-agentrouter-token",
  "base_url": "https://agentrouter.org",
  "selected_model": "deepseek-v4-flash",
  "refresh_interval_sec": 30,
  "auto_refresh_enabled": true,
  "always_on_top": true,
  "compact_mode": false,
  "sound_alert_enabled": true,
  "user_timezone_offset": 330
}
```

- `api_key`: Your personal AgentRouter token.
- `base_url`: Gateway base URL (`https://agentrouter.org` or official mirror `https://ps.air-outer.com`).
- `selected_model`: Currently tracked model.
- `refresh_interval_sec`: Polling rate in seconds (15, 30, 60, 120, 300).
- `auto_refresh_enabled`: Boolean flag for automatic background polling.
- `always_on_top`: Boolean flag for desktop pin behavior.
- `compact_mode`: Boolean flag for mini-dock view.
- `sound_alert_enabled`: Boolean flag for chime on quota release.
- `user_timezone_offset`: Timezone offset in minutes (`330` = UTC+05:30 IST).
