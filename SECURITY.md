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

3. **Secure Local API Key Storage**
   - API tokens are stored strictly on your local machine in `config.json` (or `%APPDATA%/Pulse/config.json`).
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
