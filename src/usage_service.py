"""Read API-key credit statistics and recent model usage without generation calls."""

import copy
import hashlib
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

import config_manager


_LOCK = threading.RLock()
_REFRESH_LOCK = threading.Lock()
_WAKE = threading.Event()
_STOP = threading.Event()
_THREAD = None
_SCOPE = ""


def _empty(has_key=False):
    return {
        "status": "not_checked" if has_key else "no_key", "stale": True,
        "updated_at": None, "refreshing": False, "scope": "api_key",
        "credit_unit": "billing credits", "used_credit": None,
        "total_credit_cap": None, "remaining_key_credit": None,
        "unlimited_key_cap": None, "account_balance": None,
        "shared_pool_remaining": None, "per_model": {}, "recent_log_count": None,
        "usage_coverage": "recent logs returned by AgentRouter",
        "message": "Waiting for usage data." if has_key else "Enter an API key to load credit usage.",
    }


_STATE = _empty()


def get_snapshot():
    with _LOCK:
        return copy.deepcopy(_STATE)


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def _ensure_scope(cfg):
    global _STATE, _SCOPE
    key = cfg.get("api_key", "")
    url = cfg.get("base_url", "https://agentrouter.org").rstrip("/")
    identity = hashlib.sha256((url + "\0" + key).encode("utf-8")).hexdigest()
    with _LOCK:
        if identity != _SCOPE:
            _STATE = _empty(bool(key))
            _SCOPE = identity
    return url, key


def _fetch(url, headers):
    response = requests.get(url, headers=headers, timeout=(5, 7))
    if response.status_code != 200:
        raise ValueError(f"HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict) or data.get("success") is False or "error" in data:
        raise ValueError("Usage not exposed by provider")
    return data


def summarize_logs(items):
    """These are recent returned records, never lifetime model totals."""
    models = {}
    if not isinstance(items, list):
        return models
    for item in items:
        if not isinstance(item, dict) or item.get("type", 2) not in (2, "2"):
            continue
        mid = item.get("model_name", item.get("model"))
        prompt = _number(item.get("prompt_tokens"))
        completion = _number(item.get("completion_tokens"))
        if not isinstance(mid, str) or not mid or prompt is None or completion is None:
            continue
        model = models.setdefault(mid, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0})
        model["prompt_tokens"] += prompt
        model["completion_tokens"] += completion
        model["total_tokens"] += prompt + completion
        model["requests"] += 1
    return models


def refresh(cancel_event=None):
    global _STATE
    if not _REFRESH_LOCK.acquire(blocking=False):
        return get_snapshot()
    try:
        url, key = _ensure_scope(config_manager.load_config())
        if not key:
            return get_snapshot()
        with _LOCK:
            identity = _SCOPE
            previous = copy.deepcopy(_STATE)
            _STATE["refreshing"] = True
        headers = {"User-Agent": "claude-cli/1.0.108 (external, cli)", "Accept": "application/json",
                   "Authorization": f"Bearer {key}", "x-api-key": key, "anthropic-version": "2023-06-01"}
        paths = {"cap": "/v1/dashboard/billing/subscription", "used": "/v1/dashboard/billing/usage",
                 "logs": "/api/log/token?p=0&page_size=100"}
        responses, errors = {}, []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {name: pool.submit(_fetch, url + path, headers) for name, path in paths.items()}
            for name, future in futures.items():
                try:
                    data = future.result()
                    if name == "logs" and not isinstance(data.get("data"), list):
                        raise ValueError("Invalid usage logs")
                    responses[name] = data
                except (requests.RequestException, ValueError, TypeError):
                    errors.append(name)
        state = copy.deepcopy(previous)
        state["refreshing"] = False
        total = _number(responses.get("cap", {}).get("hard_limit_usd"))
        used = _number(responses.get("used", {}).get("total_usage"))
        # AgentRouter's OpenAI-compatible billing usage is expressed in hundredths
        # of a billing credit. The subscription endpoint returns whole credits.
        if used is not None:
            state["used_credit"] = used / 100
        if total is not None:
            # New API uses this exact sentinel for an API key with UnlimitedQuota.
            # This does not report the user's remaining account credit balance.
            state["unlimited_key_cap"] = total == 100000000
            state["total_credit_cap"] = None if state["unlimited_key_cap"] else total
        if "cap" in responses and total is None:
            errors.append("cap")
        if "used" in responses and used is None:
            errors.append("used")
        if total is not None and used is not None:
            state["remaining_key_credit"] = None if state["unlimited_key_cap"] else max(0, total - used / 100)
        if "logs" in responses:
            state["per_model"] = summarize_logs(responses["logs"]["data"])
            state["recent_log_count"] = len(responses["logs"]["data"])
        state["stale"] = bool(errors)
        if used is not None or total is not None or "logs" in responses:
            state["updated_at"] = time.time()
            state["status"] = "partial" if errors else "available"
            state["message"] = "Recent model logs are a partial history, not lifetime totals." if state["per_model"] else "Per-model token totals and shared pool balances are not reported by this API key."
        else:
            state["status"] = "unavailable"
            state["message"] = "Usage is unavailable through this API key; keeping any previously reported figures."
        if cancel_event is not None and cancel_event.is_set():
            return get_snapshot()
        with _LOCK:
            if identity == _SCOPE:
                _STATE = state
        return get_snapshot()
    finally:
        with _LOCK:
            _STATE["refreshing"] = False
        _REFRESH_LOCK.release()


def request_refresh():
    _ensure_scope(config_manager.load_config())
    _WAKE.set()


def start(interval_seconds=300):
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        _ensure_scope(config_manager.load_config())
        _STOP.clear()
        _WAKE.clear()

        def worker():
            while not _STOP.is_set():
                try:
                    refresh(cancel_event=_STOP)
                except Exception:
                    with _LOCK:
                        _STATE.update(refreshing=False, stale=True, status="unavailable", message="Usage refresh failed; retrying automatically.")
                if _STOP.is_set():
                    break
                _WAKE.wait(interval_seconds)
                _WAKE.clear()

        _THREAD = threading.Thread(target=worker, name="usage-sync", daemon=True)
        _THREAD.start()


def stop():
    _STOP.set()
    _WAKE.set()
    if _THREAD is not None and _THREAD is not threading.current_thread():
        _THREAD.join(timeout=1)
