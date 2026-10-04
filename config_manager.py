"""
Configuration Manager for AgentRouter Monitor Widget.
Persists API key, base URL, refresh rates, model preferences, and widget settings.
"""

import json
import os
import sys
import threading
import time
from typing import Dict, Any


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
    if not key:
        return ""
    key = key.strip()
    if len(key) <= 8:
        return "••••••••"
    prefix = key[:4]
    suffix = key[-4:]
    return f"{prefix}••••••••{suffix}"


def load_config() -> Dict[str, Any]:
    """Loads configuration from config.json or returns default configuration in a thread-safe manner."""
    with _CONFIG_LOCK:
        cfg = dict(DEFAULT_CONFIG)
        template = get_template_config()
        if template:
            cfg.update(template)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        cfg.update(saved)
            except Exception as e:
                # Do not crash if read momentarily encounters a lock
                pass
        return cfg


def save_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Saves updated settings to config.json with thread-safety and Windows file-replace resilience."""
    with _CONFIG_LOCK:
        cfg = load_config()
        for k, v in updates.items():
            cfg[k] = v

        parent_dir = os.path.dirname(CONFIG_FILE)
        if parent_dir and not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except Exception:
                pass

        temp_file = CONFIG_FILE + f".tmp.{os.getpid()}_{threading.get_ident()}"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            
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
                # Fallback direct write if replace failed
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
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
