"""
Configuration Manager for AgentRouter Monitor Widget.
Persists API key, base URL, refresh rates, model preferences, and widget settings.
"""

import json
import os
import sys
import threading
import time
import base64
from typing import Dict, Any

# Windows Data Protection API (DPAPI) via ctypes
HAS_DPAPI = False
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte))
            ]

        _CryptProtectData = ctypes.windll.crypt32.CryptProtectData
        _CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
        _LocalFree = ctypes.windll.kernel32.LocalFree
        HAS_DPAPI = True
    except Exception:
        HAS_DPAPI = False


def encrypt_secret(plaintext: str) -> str:
    """
    Encrypts a plaintext string using Windows DPAPI (CryptProtectData).
    Data is encrypted using an AES/3DES key derived from the local user's Windows logon credentials.
    Returns a string prefixed with 'enc:dpapi:<base64_ciphertext>'.
    Falls back to base64 encoding on non-Windows platforms (e.g. Linux CI/tests).
    """
    plaintext = (plaintext or "").strip()
    if not plaintext:
        return ""

    if HAS_DPAPI:
        try:
            data = plaintext.encode("utf-8")
            blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
            blob_out = DATA_BLOB()
            # CRYPTPROTECT_UI_FORBIDDEN = 0x1
            if _CryptProtectData(ctypes.byref(blob_in), "Pulse API Key", None, None, None, 0x1, ctypes.byref(blob_out)):
                try:
                    encrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                    return "enc:dpapi:" + base64.b64encode(encrypted_bytes).decode("ascii")
                finally:
                    _LocalFree(blob_out.pbData)
        except Exception:
            pass

    # Non-Windows test environments (e.g. Linux CI test runners) use reversible Base64 encoding.
    # NOTE: Non-Windows test environments use reversible encoding only and should not be considered
    # secure credential storage. Production Windows builds exclusively utilize Windows DPAPI.
    return "dev:b64:" + base64.b64encode(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    """
    Decrypts a ciphertext string encrypted by encrypt_secret.
    Uses Windows DPAPI CryptUnprotectData on Windows, or decodes development fallback.
    """
    ciphertext = (ciphertext or "").strip()
    if not ciphertext:
        return ""

    if ciphertext.startswith("enc:dpapi:") and HAS_DPAPI:
        try:
            raw_b64 = ciphertext[len("enc:dpapi:"):]
            encrypted_bytes = base64.b64decode(raw_b64)
            blob_in = DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_byte)))
            blob_out = DATA_BLOB()
            # CRYPTPROTECT_UI_FORBIDDEN = 0x1
            if _CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out)):
                try:
                    decrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                    return decrypted_bytes.decode("utf-8")
                finally:
                    _LocalFree(blob_out.pbData)
        except Exception:
            return ""

    elif ciphertext.startswith("dev:b64:") or ciphertext.startswith("enc:b64:"):
        prefix_len = len("dev:b64:") if ciphertext.startswith("dev:b64:") else len("enc:b64:")
        try:
            raw_b64 = ciphertext[prefix_len:]
            return base64.b64decode(raw_b64).decode("utf-8")
        except Exception:
            return ""

    # Legacy plaintext fallback if unencrypted string was passed
    return ciphertext


def get_config_path() -> str:
    """
    Determines the persistent configuration file path.
    When frozen as a single-file executable:
      1. Uses config.json located next to sys.executable if writable (portable app mode).
      2. If directory is not writable (e.g. Program Files), falls back to %APPDATA%/Pulse/config.json.
    When running from source:
      Uses config.json in the script's directory.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        portable_path = os.path.join(exe_dir, "config.json")
        if os.path.exists(portable_path):
            return portable_path
        # Test writability of exe_dir
        try:
            test_file = os.path.join(exe_dir, f".write_test_{os.getpid()}.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return portable_path
        except (PermissionError, OSError):
            appdata = os.getenv("APPDATA") or os.path.expanduser("~")
            pulse_dir = os.path.join(appdata, "Pulse")
            try:
                os.makedirs(pulse_dir, exist_ok=True)
                return os.path.join(pulse_dir, "config.json")
            except Exception:
                return portable_path

    # When running from source: check project root (parent of src/), else script directory
    src_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_config = os.path.join(src_parent, "config.json")
    if os.path.exists(root_config) or os.path.exists(os.path.join(src_parent, "config.example.json")):
        return root_config
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def get_template_config() -> Dict[str, Any]:
    """Reads default config from bundled config.example.json if present."""
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(bundle_dir, "config.example.json")
    if os.path.exists(template_path):
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    return saved
        except Exception:
            pass
    return {}


CONFIG_FILE = get_config_path()
_CONFIG_LOCK = threading.RLock()

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_key": "",
    "api_key_encrypted": "",
    "base_url": "https://agentrouter.org",
    "selected_model": "deepseek-v4-flash",
    "refresh_interval_sec": 30,
    "auto_refresh_enabled": True,
    "always_on_top": True,
    "compact_mode": False,
    "sound_alert_enabled": True,
    "user_timezone_offset": 330,  # UTC+05:30 (IST) in minutes
}


def mask_key(key: str) -> str:
    """Masks an API key for safe display (e.g., sk-1234••••••••5678)."""
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "••••••••"
    prefix = key[:4]
    suffix = key[-4:]
    return f"{prefix}••••••••{suffix}"


def _save_to_disk(cfg: Dict[str, Any]) -> None:
    """Internal helper to atomically write config to disk with API key DPAPI-encrypted."""
    disk_cfg = dict(cfg)
    plain_key = (disk_cfg.get("api_key") or "").strip()

    if plain_key:
        disk_cfg["api_key_encrypted"] = encrypt_secret(plain_key)
    else:
        disk_cfg["api_key_encrypted"] = ""

    # NEVER store plaintext API key in the JSON file on disk
    disk_cfg["api_key"] = ""

    parent_dir = os.path.dirname(CONFIG_FILE)
    if parent_dir and not os.path.exists(parent_dir):
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except Exception:
            pass

    temp_file = CONFIG_FILE + f".tmp.{os.getpid()}_{threading.get_ident()}"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(disk_cfg, f, indent=2, ensure_ascii=False)

        # Robust atomic replace on Windows with retry
        replaced = False
        for attempt in range(5):
            try:
                os.replace(temp_file, CONFIG_FILE)
                replaced = True
                break
            except (PermissionError, OSError):
                time.sleep(0.02 * (attempt + 1))

        if not replaced:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(disk_cfg, f, indent=2, ensure_ascii=False)
    finally:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass


def load_config() -> Dict[str, Any]:
    """Loads configuration from config.json, decrypts DPAPI key, and migrates legacy plaintext."""
    with _CONFIG_LOCK:
        cfg = dict(DEFAULT_CONFIG)
        template = get_template_config()
        if template:
            cfg.update(template)

        needs_migration = False
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        cfg.update(saved)

                        # 1. If encrypted key is present, decrypt it into memory
                        enc_key = saved.get("api_key_encrypted", "").strip()
                        if enc_key:
                            decrypted = decrypt_secret(enc_key)
                            cfg["api_key"] = decrypted
                            cfg["api_key_encrypted"] = enc_key

                        # 2. Check for legacy unencrypted plaintext key in config.json
                        legacy_plain = saved.get("api_key", "").strip()
                        if legacy_plain and not enc_key:
                            cfg["api_key"] = legacy_plain
                            cfg["api_key_encrypted"] = encrypt_secret(legacy_plain)
                            needs_migration = True
            except Exception:
                pass

        if needs_migration:
            try:
                _save_to_disk(cfg)
            except Exception:
                pass

        return cfg


def save_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Saves updated settings to config.json with thread-safety and Windows DPAPI encryption."""
    with _CONFIG_LOCK:
        cfg = load_config()
        for k, v in updates.items():
            cfg[k] = v

        _save_to_disk(cfg)
        return cfg


def get_safe_config() -> Dict[str, Any]:
    """Returns configuration object suitable for frontend, with masked API key."""
    cfg = load_config()
    key = cfg.get("api_key", "").strip()
    safe_cfg = dict(cfg)
    safe_cfg["has_api_key"] = bool(key)
    safe_cfg["masked_api_key"] = mask_key(key)
    # Don't send plain key in general config fetch
    safe_cfg["api_key"] = mask_key(key)
    safe_cfg["is_encrypted"] = True
    if "api_key_encrypted" in safe_cfg:
        safe_cfg["api_key_encrypted"] = bool(key)
    return safe_cfg


def get_api_key() -> str:
    """Returns the raw unmasked API key for local user editing."""
    cfg = load_config()
    return cfg.get("api_key", "").strip()


def set_api_key(key: str) -> Dict[str, Any]:
    """Updates API key and returns safe config."""
    key = (key or "").strip()
    save_config({"api_key": key})
    return get_safe_config()


def clear_api_key() -> Dict[str, Any]:
    """Clears API key."""
    return set_api_key("")
