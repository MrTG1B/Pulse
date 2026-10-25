"""Publish the verified Windows executable as a new GitHub release asset."""

import argparse
import hashlib
import os
import subprocess
import sys

import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE_PATH = os.path.join(ROOT_DIR, "dist", "Pulse.exe")
REPO = "MrTG1B/Pulse"
TAG_NAME = "v1.1.0"
RELEASE_TITLE = "Pulse v1.1.0 — Automatic AgentRouter Updates & Usage"


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
    digest = hashlib.sha256()
    with open(filepath, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_release_notes(sha256: str, size_mb: float) -> str:
    return f"""Pulse now automatically follows AgentRouter's current model catalog and dated supply announcements.

- Claude Opus 5.5 is temporarily unavailable; Astra is unlimited; Sol is unlimited, recommended, and displays its live base multiplier.
- Models, pricing and notices refresh in the background every five minutes. Sync Now refreshes immediately; failed refreshes keep visibly stale cached data.
- The picker, help panels and quota countdowns update with provider policies. Unlimited and unavailable models have no quota refill timer or automatic release trigger.
- API-key credit usage and caps are displayed when reported. Recent per-model input/output tokens are shown when logs are returned. Unreported account balances and shared model pool quotas remain unknown.
- Includes the current desktop window recovery, single-instance restoration, and optional Codex/Claude Code focus controls with Gemini gating.

Download Pulse.exe and run it on Windows 10/11. API keys remain encrypted locally with Windows DPAPI.

Binary size: {size_mb:.2f} MB
SHA256: `{sha256}`
"""


def publish(dry_run=False, target_commit=None):
    if not os.path.isfile(EXE_PATH):
        print(f"Executable not found: {EXE_PATH}")
        return 1
    target_commit = target_commit or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True).strip()
    size = os.path.getsize(EXE_PATH)
    checksum = compute_sha256(EXE_PATH)
    notes = get_release_notes(checksum, size / (1024 * 1024))
    print(f"Release: {TAG_NAME}; target: {target_commit}; size: {size}; SHA256: {checksum}")
    if dry_run:
        print(notes)
        return 0
    token = get_github_token()
    if not token:
        print("GitHub credentials are unavailable.")
        return 1
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Pulse-Release-Publisher"})
    api = f"https://api.github.com/repos/{REPO}/releases"
    tag_commit = session.get(f"https://api.github.com/repos/{REPO}/commits/{TAG_NAME}", timeout=(8, 20))
    if tag_commit.status_code == 200 and tag_commit.json().get("sha") != target_commit:
        print("The release tag points to a different commit; it has been preserved.")
        return 1
    if tag_commit.status_code not in (200, 404):
        print(f"Release tag lookup failed: HTTP {tag_commit.status_code}")
        return 1
    existing = session.get(f"{api}/tags/{TAG_NAME}", timeout=(8, 20))
    if existing.status_code == 200:
        release = existing.json()
        for asset in release.get("assets", []):
            if asset.get("name") == "Pulse.exe":
                if asset.get("digest") == f"sha256:{checksum}" and asset.get("size") == size:
                    print(f"Matching asset already published: {asset['browser_download_url']}")
                    return 0
                print("An existing Pulse.exe asset differs; it has been preserved.")
                return 1
    elif existing.status_code == 404:
        created = session.post(api, json={"tag_name": TAG_NAME, "target_commitish": target_commit,
                                         "name": RELEASE_TITLE, "body": notes, "draft": True, "prerelease": False}, timeout=(8, 20))
        if created.status_code != 201:
            print(f"Release creation failed: HTTP {created.status_code}")
            return 1
        release = created.json()
    else:
        print(f"Release lookup failed: HTTP {existing.status_code}")
        return 1
    upload_url = release["upload_url"].split("{")[0]
    with open(EXE_PATH, "rb") as handle:
        uploaded = session.post(upload_url, params={"name": "Pulse.exe"}, data=handle,
                                headers={"Content-Type": "application/vnd.microsoft.portable-executable"}, timeout=(10, 180))
    if uploaded.status_code != 201:
        print(f"Asset upload failed: HTTP {uploaded.status_code}; draft retained.")
        return 1
    asset = uploaded.json()
    if asset.get("size") != size or (asset.get("digest") and asset["digest"] != f"sha256:{checksum}"):
        print("Uploaded asset verification failed; draft retained.")
        return 1
    published = session.patch(f"{api}/{release['id']}", json={"draft": False}, timeout=(8, 20))
    if published.status_code != 200:
        print(f"Release publication failed: HTTP {published.status_code}; uploaded draft retained.")
        return 1
    print(f"Release URL: {published.json()['html_url']}")
    print(f"Download URL: {asset['browser_download_url']}")
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--target-commit")
    args = parser.parse_args()
    sys.exit(publish(dry_run=args.dry_run, target_commit=args.target_commit))
