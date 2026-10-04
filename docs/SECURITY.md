# Security Policy — Pulse

Pulse is built with security, privacy, and zero-telemetry principles for developers and enterprise teams monitoring **[AgentRouter](https://agentrouter.org/)**.

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

3. **Hardware-Backed Local API Key Encryption (Windows DPAPI)**
   - API tokens are encrypted at rest using the **Windows Data Protection API (DPAPI)** (`CryptProtectData` via Windows `crypt32.dll`).
   - Encryption keys are derived by the Windows Local Security Authority Subsystem Service (LSASS) from the logged-in user's Windows security credentials and hardware TPM (if present).
   - In `config.json` (or `%APPDATA%/Pulse/config.json`), keys are stored strictly as an opaque encrypted ciphertext blob prefixed with `enc:dpapi:`. Plaintext keys are **never written to disk**.
   - **Cross-Account & Cross-Device Protection**: No other Windows user account on the same machine, and no unauthorized process on another computer, can decrypt the stored ciphertext—even if `config.json` is copied, inspected, or exfiltrated.
   - **Automatic Legacy Migration**: If a legacy plaintext `config.json` is detected on startup, Pulse automatically encrypts it with DPAPI and immediately overwrites and purges the plaintext key from disk.
   - Tokens are masked in API payloads and UI views by default (`sk-••••••••1234`).
   - `config.json` is explicitly gitignored to prevent accidental commits to source control repositories.

4. **WAF & Header Validation**
   - Pulse utilizes authenticated, allowlisted client headers matching official client profiles (`claude-cli/1.0.108`) to ensure legitimate communications without triggering Cloudflare / AgentRouter WAF blocks.

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
