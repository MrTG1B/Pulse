"""
Pulse — GitHub Release & Asset Publisher.
Creates a GitHub Release and uploads the standalone Pulse.exe binary asset.
Uses Git Credential Manager or GITHUB_TOKEN environment variable for authentication.
"""

import os
import sys
import hashlib
import subprocess
import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE_PATH = os.path.join(ROOT_DIR, "dist", "Pulse.exe")
REPO = "MrTG1B/Pulse"
TAG_NAME = "v1.0.0"
RELEASE_TITLE = "Pulse v1.0.0 — Standalone Release for Windows"


def get_github_token() -> str:
    """Retrieves GitHub token from GITHUB_TOKEN env var or Git Credential Manager."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token

    try:
        p = subprocess.Popen(
            ["git", "credential", "fill"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, _ = p.communicate("protocol=https\nhost=github.com\n\n")
        for line in out.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception as e:
        print(f"[Warning] Failed to query Git Credential Manager: {e}")

    return ""


def compute_sha256(filepath: str) -> str:
    """Computes SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def get_release_notes(sha256: str, size_mb: float) -> str:
    return f"""## Pulse v1.0.0 — Standalone Desktop Release for Windows

**Pulse** is a lightweight, always-on-top availability monitor and quota tracker for developers using [AgentRouter](https://agentrouter.org) with Claude Code and Codex.

### 🚀 What's New in v1.0.0

- **Standalone Single-File Executable (`Pulse.exe`)**:
  - Zero dependencies or Python runtime required.
  - Runs cleanly without any terminal or console window popup (`--noconsole`).
  - Embedded Windows version metadata, multi-resolution app icon, and static web assets.
  - Portable configuration: settings and API keys are stored safely in `config.json` next to the executable.

- **4 Core Active AgentRouter Models**:
  - `deepseek-v4-flash` — ⚡ Always Active (Uninterrupted 200 OK)
  - `claude-opus-4-8` — ⏱️ Quota Pool (10:00 & 19:00 CST Daily Release)
  - `claude-opus-5` — ⏱️ Quota Pool (10:00 & 19:00 CST Daily Release)
  - `gpt-6-astra` — ⏱️ Quota Pool (10:00 & 19:00 CST Daily Release)

- **Beijing Daily Quota Countdown & Local Timezone Conversion**:
  - Tracks the exact Beijing replenishment cycles (10:00 AM & 07:00 PM CST / 02:00 & 11:00 UTC).
  - Translates drop times into local user timezone (e.g. `07:30 AM & 04:30 PM IST`).
  - Subtle audio chime upon quota replenishment.

- **FinTech Dark Mode & Smooth Scrolling UI**:
  - Premium high-contrast palette (`#0A0A0A` background, `#B8FF3D` neon lime accent).
  - Compact mini-dock mode (`390×100px`) and Always-on-Top pin.
  - Smooth multi-input scrolling (mouse wheel, keyboard navigation, touch drag).

---

### 📦 Binary Asset Details

| File Name | Platform | Size | SHA256 Checksum |
| :--- | :--- | :--- | :--- |
| **`Pulse.exe`** | Windows 10 / 11 (x64) | {size_mb:.2f} MB | `{sha256}` |

### 🛠️ Quick Start
1. Download `Pulse.exe` from the Assets below.
2. Double-click `Pulse.exe` to launch. No installer needed!
3. Enter your AgentRouter API key (`sk-...`) in the top bar to start monitoring.
"""


def publish():
    print("=" * 65)
    print(" Pulse — GitHub Release & Asset Publisher")
    print(f" Target Repository: {REPO}")
    print(f" Release Tag:       {TAG_NAME}")
    print("=" * 65)

    if not os.path.exists(EXE_PATH):
        print(f"[Error] Executable not found at {EXE_PATH}")
        print("Please build Pulse.exe first using `python scripts/build_exe.py`.")
        return 1

    token = get_github_token()
    if not token:
        print("[Error] No GitHub authentication token found.")
        print("Set GITHUB_TOKEN environment variable or authenticate via Git Credential Manager.")
        return 1

    size_bytes = os.path.getsize(EXE_PATH)
    size_mb = size_bytes / (1024 * 1024)
    sha256 = compute_sha256(EXE_PATH)
    print(f"[Binary] Found Pulse.exe: {size_mb:.2f} MB ({size_bytes:,} bytes)")
    print(f"[Binary] SHA256: {sha256}")

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Pulse-Release-Publisher/1.0"
    }

    # 1. Check if release already exists
    print(f"\n[1/3] Checking if release '{TAG_NAME}' exists on GitHub...")
    r = requests.get(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG_NAME}", headers=headers)
    release = None
    if r.status_code == 200:
        release = r.json()
        print(f"[GitHub] Existing release found (ID: {release['id']})")
    elif r.status_code == 404:
        print(f"[GitHub] Release '{TAG_NAME}' does not exist yet. Creating release...")
        payload = {
            "tag_name": TAG_NAME,
            "target_commitish": "main",
            "name": RELEASE_TITLE,
            "body": get_release_notes(sha256, size_mb),
            "draft": False,
            "prerelease": False
        }
        create_res = requests.post(f"https://api.github.com/repos/{REPO}/releases", headers=headers, json=payload)
        if create_res.status_code in (200, 201):
            release = create_res.json()
            print(f"[GitHub] Release created successfully! (ID: {release['id']})")
        else:
            print(f"[Error] Failed to create release: {create_res.status_code} - {create_res.text}")
            return 1
    else:
        print(f"[Error] Failed to query releases: {r.status_code} - {r.text}")
        return 1

    release_id = release["id"]

    # 2. Check existing assets for Pulse.exe
    print(f"\n[2/3] Checking existing release assets...")
    assets_res = requests.get(f"https://api.github.com/repos/{REPO}/releases/{release_id}/assets", headers=headers)
    if assets_res.status_code == 200:
        for asset in assets_res.json():
            if asset["name"] == "Pulse.exe":
                print(f"[GitHub] Existing Pulse.exe asset found (ID: {asset['id']}). Deleting old asset...")
                del_res = requests.delete(f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}", headers=headers)
                if del_res.status_code == 204:
                    print("[GitHub] Old asset deleted.")
                else:
                    print(f"[Warning] Could not delete old asset: {del_res.status_code}")

    # 3. Upload Pulse.exe asset
    print(f"\n[3/3] Uploading Pulse.exe ({size_mb:.2f} MB) to GitHub Release...")
    upload_url = release.get("upload_url", "").split("{")[0]
    upload_url = f"{upload_url}?name=Pulse.exe"

    upload_headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/vnd.microsoft.portable-executable",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Pulse-Release-Publisher/1.0"
    }

    with open(EXE_PATH, "rb") as f:
        upload_res = requests.post(upload_url, headers=upload_headers, data=f)

    if upload_res.status_code in (200, 201):
        asset_data = upload_res.json()
        download_url = asset_data.get("browser_download_url")
        print("=" * 65)
        print(" Successfully Uploaded Release Asset!")
        print(f" Release URL:  {release.get('html_url')}")
        print(f" Download URL: {download_url}")
        print(f" Asset Size:   {size_mb:.2f} MB")
        print(f" SHA256:       {sha256}")
        print("=" * 65)
        return 0
    else:
        print(f"[Error] Failed to upload asset: {upload_res.status_code} - {upload_res.text}")
        return 1


if __name__ == "__main__":
    sys.exit(publish())
