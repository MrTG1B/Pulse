# Security Policy — Pulse

Pulse is built with security, privacy, and zero-telemetry principles for developers monitoring **[AgentRouter](https://agentrouter.org/)**.

---

## 🔒 Security Architecture & Guarantees

1. **Local-Only Loopback Binding**
   - The embedded HTTP server binds strictly to IPv4 loopback (`127.0.0.1`) on a dynamic non-conflicting TCP port.
   - It is never exposed to local networks (LAN) or public interfaces.

2. **Zero Third-Party Telemetry**
   - Pulse does not collect user data, tracking analytics, usage metrics, or logs.
   - Network communication is restricted strictly to:
     - Target gateway: `https://agentrouter.org` (or configured backup `https://ps.air-outer.com`).
     - Local loopback: `http://127.0.0.1:[port]`.

3. **Windows DPAPI Local Key Encryption**
   - **Windows DPAPI**: Pulse encrypts AgentRouter API keys at rest using the Windows Data Protection API (`CryptProtectData` via Windows `crypt32.dll`). The encrypted value is bound to the Windows user context and is not stored as plaintext.
   - In `config.json` (or `%APPDATA%/Pulse/config.json`), keys are stored strictly as an opaque encrypted ciphertext blob prefixed with `enc:dpapi:`. Plaintext keys are **never written to disk**.
   - **User Context Isolation**: Because encryption is bound to the logged-in user's Windows credentials, copying or exfiltrating `config.json` to another machine or accessing it from another user account on the same machine cannot decrypt the secret.
   - **Automatic Legacy Migration**: If a legacy plaintext `config.json` is detected on startup, Pulse automatically encrypts it with DPAPI and immediately overwrites and purges the plaintext key from disk.
   - **Local API Security**: The local backend API never exposes raw keys over HTTP (only `has_api_key` and masked strings `sk-••••••••1234`).
   - **Non-Windows Environments**: Non-Windows test environments (e.g. cross-platform CI runners) use reversible encoding (`dev:b64:`) exclusively for testing and should not be considered secure credential storage. Production Windows builds exclusively utilize Windows DPAPI.
   - `config.json` is explicitly gitignored to prevent accidental commits to source control repositories.

4. **Compatible AgentRouter Client Headers**
   - Pulse utilizes authentic, compatible client identification headers matching supported coding client profiles (`claude-cli/1.0.108` for Claude Code and Codex) to ensure seamless API interoperability without encountering unauthorized client rejections.

5. **No Remote Code Execution**
   - The desktop wrapper uses Microsoft Edge WebView2 with a restricted JS API bridge strictly exposing window management controls (`resize_window`, `toggle_always_on_top`, `minimize_window`, `close_window`, `open_external_url`).

---

## 🛡️ Supported Versions

Only the latest release branch of Pulse receives active security updates and vulnerability patches:

| Version | Supported |
|---|---|
| 1.0.x | :white_check_mark: Yes |
| < 1.0.0 | :x: No |

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability within Pulse, please report it responsibly:

1. **Do NOT open a public GitHub issue.**
2. Send an email to the project maintainers via GitHub private security advisories:
   - [Submit Security Advisory](https://github.com/MrTG1B/Pulse/security/advisories/new)
3. Please include:
   - Detailed description of the vulnerability.
   - Step-by-step reproduction instructions or proof-of-concept.
   - Impact assessment on credentials or system environment.

### Response Timeline
- **Initial Acknowledgment:** Within 24 hours.
- **Triage & Assessment:** Within 48 hours.
- **Patch Release:** Within 7 calendar days depending on severity.
