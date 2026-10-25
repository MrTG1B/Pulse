"""Cached, background synchronization of AgentRouter's models and announcements."""

import copy
import hashlib
import json
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

import config_manager


REFRESH_INTERVAL_SECONDS = 300
DEFAULT_ANNOUNCEMENTS = [{
    "id": 19,
    "published_at": "2026-10-24T19:20:39.237Z",
    "content": (
        "📢 重要通知\nclaude-opus-5.5 暂时下线，恢复时间另行通知。\n"
        "gpt-6-astra 取消限量，现已全天候供应，欢迎随时使用。\n"
        "gpt-6.1sol 不限量低倍率供应，建议优先使用。\n\n"
        "📢 Important Notice\nclaude-opus-5.5 is temporarily unavailable. Further updates will follow.\n"
        "gpt-6-astra is now unlimited and available all day.\n"
        "gpt-6.1sol is available without limits at a low multiplier. We recommend using it first."
    ),
}]
DEFAULT_MODELS = [
    {"id": "gpt-6.1-sol", "name": "GPT-6.1 Sol", "provider": "OpenAI", "api_type": "openai_responses"},
    {"id": "gpt-6-astra", "name": "GPT-6 Astra", "provider": "OpenAI", "api_type": "openai_responses"},
    {"id": "claude-opus-5-5", "name": "Claude Opus 5.5", "provider": "Anthropic", "api_type": "anthropic"},
]

_MODEL_TOKEN = re.compile(r"(?<![a-z0-9])(?:claude|gpt|deepseek|glm|qwen|kimi|moonshot)[a-z0-9._-]*", re.I)
_TIME_LIST = r"(?:\d{1,2}:\d{2})(?:\s*(?:[/,&]|and|和|与)\s*\d{1,2}:\d{2})*"
_LOCK = threading.RLock()
_REFRESH_LOCK = threading.Lock()
_WAKE = threading.Event()
_STOP = threading.Event()
_THREAD = None
_SCOPE = ""


def model_key(model_id):
    """Match announcement aliases while keeping the API's actual model ID."""
    return re.sub(r"[^a-z0-9]", "", str(model_id).lower())


def _published_timestamp(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp()
    except (ValueError, TypeError, OverflowError):
        return 0


def normalize_announcements(items):
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("content"), str):
            continue
        content = item["content"].strip()
        if not content:
            continue
        published = item.get("publishDate", item.get("published_at"))
        result.append({
            "id": item.get("id") if isinstance(item.get("id"), (str, int)) else None,
            "content": content[:16000],
            "published_at": published if _published_timestamp(published) else None,
        })
    result.sort(key=lambda n: (_published_timestamp(n["published_at"]),
                               n["id"] if isinstance(n["id"], int) else 0), reverse=True)
    return result[:20]


def parse_release_minutes(text):
    """Read explicit UTC or Beijing times; never invent a quota schedule."""
    text = re.sub(r"<[^>]*>|\*|_", "", text)
    for label, offset in ((r"UTC(?!\s*[+-]\s*0*[1-9])", 0),
                          (r"(?:北京时间|Beijing\s*(?:Time)?|CST)", 480)):
        patterns = [rf"({_TIME_LIST})\s*{label}", rf"{label}\s*(?:时间|time)?\s*({_TIME_LIST})"]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                slots = []
                for hour, minute in re.findall(r"(\d{1,2}):(\d{2})", match.group(1)):
                    if int(hour) > 23 or int(minute) > 59:
                        return []
                    slots.append((int(hour) * 60 + int(minute) - offset) % 1440)
                return sorted(set(slots))
    return []


def _make_model(model_id, pricing=None):
    known = next((m for m in DEFAULT_MODELS if model_key(m["id"]) == model_key(model_id)), {})
    lower = model_id.lower()
    provider = "Anthropic" if "claude" in lower else "OpenAI" if lower.startswith("gpt") else "Unknown"
    api_type = "anthropic" if "claude" in lower else "openai_responses" if any(x in lower for x in ("astra", "sol", "responses")) else "openai"
    model = {
        "id": model_id, "name": known.get("name", model_id),
        "provider": known.get("provider", provider), "api_type": known.get("api_type", api_type),
        "provider_status": "unknown", "quota_limited": None, "release_minutes_utc": [],
        "recommended": False, "low_multiplier": False, "available_in_account": None,
    }
    if pricing:
        ratio = pricing.get("model_ratio")
        if isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and math.isfinite(ratio) and ratio >= 0:
            model["multiplier"] = ratio
        endpoints = pricing.get("supported_endpoint_types")
        if isinstance(endpoints, list) and "anthropic" in endpoints:
            model["api_type"] = "anthropic"
    return model


def apply_announcements(models, announcements):
    """Apply older policies first so newer model-specific announcements win."""
    result = copy.deepcopy(models)
    by_key = {model_key(m["id"]): m for m in result}
    for notice in reversed(normalize_announcements(announcements)):
        text = re.sub(r"<[^>]*>|\*|_", "", notice["content"])
        mentions = list(_MODEL_TOKEN.finditer(text))
        for i, mention in enumerate(mentions):
            key = model_key(mention.group().rstrip("."))
            model = by_key.get(key)
            if model is None:
                continue
            end = mentions[i + 1].start() if i + 1 < len(mentions) else len(text)
            clause = text[mention.end():end]
            unavailable = re.search(r"temporarily\s+(?:unavailable|offline|down)|taken offline|暂时下线|暂时不可用|暂停供应|暂停服务", clause, re.I)
            unlimited = re.search(r"\bunlimited\b|without (?:any )?(?:quota )?limits|no (?:quota )?limits|available all day|全天候|全天不限量|不限量|取消限量|无限量", clause, re.I)
            limited = re.search(r"\blimited\b|限量供应|限量|限额", clause, re.I)
            restored = re.search(r"\brestored\b|back online|available again|恢复供应|恢复上线|重新上线", clause, re.I)
            if unavailable:
                model.update(provider_status="unavailable", quota_limited=None, release_minutes_utc=[], recommended=False)
            elif unlimited:
                model.update(provider_status="unlimited", quota_limited=False, release_minutes_utc=[])
            elif limited:
                model.update(provider_status="limited", quota_limited=True, release_minutes_utc=parse_release_minutes(clause), recommended=False)
            elif restored:
                model.update(provider_status="available", quota_limited=None, release_minutes_utc=[], recommended=False)
            if unavailable or unlimited or limited or restored:
                model["policy_notice_id"] = notice["id"]
                model["policy_published_at"] = notice["published_at"]
            if re.search(r"recommend|建议优先|优先使用", clause, re.I) and model["provider_status"] != "unavailable":
                model["recommended"] = True
            if re.search(r"low multiplier|低倍率", clause, re.I):
                model["low_multiplier"] = True
    for model in result:
        status = model["provider_status"]
        model["category"] = "uninterrupted" if status == "unlimited" else "quota" if status == "limited" else status
        model["tag"] = {"unlimited": "Unlimited · all day", "limited": "Limited supply",
                        "unavailable": "Temporarily unavailable", "available": "Supply restored"}.get(status, "Supply policy unknown")
    return result


def _initial_state(base_url="https://agentrouter.org"):
    is_router = urlparse(base_url).hostname in ("agentrouter.org", "ps.air-outer.com")
    notices = copy.deepcopy(DEFAULT_ANNOUNCEMENTS) if is_router else []
    models = apply_announcements([_make_model(m["id"]) for m in DEFAULT_MODELS], notices) if is_router else []
    return {
        "base_url": base_url, "announcements": notices, "models": models,
        "notice_source": "bundled", "model_source": "bundled", "refreshing": False,
        "last_attempt_at": None, "notices_updated_at": None, "models_updated_at": None,
        "notices_stale": True, "models_stale": True, "error": "",
        "pricing_stale": True,
        "recommended_model": "gpt-6.1-sol" if is_router else None,
        "refresh_interval_sec": REFRESH_INTERVAL_SECONDS,
    }


_STATE = _initial_state()
# Keep this list object stable for existing router_client callers.
CATALOG_MODELS = copy.deepcopy(_STATE["models"])


def get_snapshot():
    with _LOCK:
        return copy.deepcopy(_STATE)


def get_scope():
    with _LOCK:
        return _SCOPE


def get_model(model_id):
    with _LOCK:
        return next((copy.deepcopy(m) for m in CATALOG_MODELS if model_key(m["id"]) == model_key(model_id)), None)


def _cache_path():
    return os.path.join(os.path.dirname(os.path.abspath(config_manager.CONFIG_FILE)), "provider_cache.json")


def _ensure_scope(base_url, api_key):
    global _SCOPE, _STATE
    scope = hashlib.sha256((base_url + "\0" + api_key).encode("utf-8")).hexdigest()
    with _LOCK:
        if scope == _SCOPE:
            return scope
        state = _initial_state(base_url)
        try:
            with open(_cache_path(), encoding="utf-8") as handle:
                cache = json.load(handle)
            cached = cache.get("snapshot")
            if cache.get("schema") == 1 and cache.get("scope") == scope and isinstance(cached, dict):
                if isinstance(cached.get("models"), list) and all(isinstance(m, dict) and isinstance(m.get("id"), str) and m.get("provider_status") in ("unknown", "unlimited", "limited", "unavailable", "available") and isinstance(m.get("release_minutes_utc"), list) for m in cached["models"]):
                    state.update(cached)
                    state.update(refreshing=False, notices_stale=True, models_stale=True)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        _SCOPE = scope
        _STATE = state
        CATALOG_MODELS[:] = copy.deepcopy(state["models"])
    return scope


def _save_cache(scope, state):
    path = _cache_path()
    tmp = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"schema": 1, "scope": scope, "snapshot": state}, handle, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


def _fetch_json(url, headers=None):
    response = requests.get(url, headers=headers or {"Accept": "application/json"}, timeout=(5, 7))
    if response.status_code != 200:
        raise ValueError(f"HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict) or data.get("success") is False:
        raise ValueError("Invalid provider response")
    return data


def refresh(api_key=None, base_url=None, cancel_event=None):
    """Synchronize once, coalescing overlapping refreshes into the running request."""
    global _STATE
    if not _REFRESH_LOCK.acquire(blocking=False):
        return get_snapshot()
    try:
        cfg = config_manager.load_config()
        key = api_key if isinstance(api_key, str) and "••••" not in api_key and "..." not in api_key else cfg.get("api_key", "")
        url = (base_url or cfg.get("base_url", "https://agentrouter.org")).rstrip("/")
        scope = _ensure_scope(url, key)
        previous = get_snapshot()
        with _LOCK:
            _STATE.update(refreshing=True, last_attempt_at=time.time())
        headers = {"Accept": "application/json", "User-Agent": "claude-cli/1.0.108 (external, cli)",
                   "anthropic-version": "2023-06-01"}
        if key:
            headers.update(Authorization=f"Bearer {key}", **{"x-api-key": key})
        paths = {"status": "/api/status", "pricing": "/api/pricing"}
        if key:
            paths["account"] = "/v1/models"
        responses, errors = {}, {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {name: pool.submit(_fetch_json, url + path, headers if name == "account" else None) for name, path in paths.items()}
            for name, future in futures.items():
                try:
                    data = future.result()
                    payload = data.get("data")
                    if not isinstance(payload, dict if name == "status" else list):
                        raise ValueError("Invalid provider payload")
                    if name == "status":
                        raw_notices = payload.get("announcements", [])
                        if not isinstance(raw_notices, list) or (raw_notices and not normalize_announcements(raw_notices)):
                            raise ValueError("Invalid announcements")
                    if name == "pricing" and payload and not any(isinstance(item, dict) and isinstance(item.get("model_name"), str) and item["model_name"].strip() for item in payload):
                        raise ValueError("Invalid pricing")
                    responses[name] = data
                except (requests.RequestException, ValueError, TypeError) as exc:
                    # Do not include response bodies or credentials in UI/cache errors.
                    errors[name] = f"{name}: {type(exc).__name__}"
        state = copy.deepcopy(previous)
        now = time.time()
        state.update(last_attempt_at=now, refreshing=False)
        if "status" in responses:
            notices = normalize_announcements(responses["status"]["data"].get("announcements", []))
            source = "status"
            if not notices:
                try:
                    notice = _fetch_json(url + "/api/notice").get("data")
                    if not isinstance(notice, str):
                        raise ValueError("Invalid notice")
                    notices = normalize_announcements([{"id": "notice", "content": notice}])
                    source = "notice"
                except (requests.RequestException, ValueError, TypeError) as exc:
                    errors["status"] = f"notice: {type(exc).__name__}"
            if "status" not in errors:
                state.update(announcements=notices, notice_source=source, notices_updated_at=now, notices_stale=False)
        if "status" in errors:
            state["notices_stale"] = True

        pricing = {}
        for item in responses.get("pricing", {}).get("data", []):
            if isinstance(item, dict) and isinstance(item.get("model_name"), str) and item["model_name"].strip():
                pricing[model_key(item["model_name"])] = item
        account_ids = None
        if "account" in responses:
            items = responses["account"]["data"]
            account_ids = list(dict.fromkeys(item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()))
            if items and not account_ids:
                account_ids = None
                errors["account"] = "account: Invalid model list"
        if account_ids is not None:
            primary_ids = account_ids
            source = "account"
        elif key and previous["model_source"] == "account":
            primary_ids = [m["id"] for m in previous["models"] if m.get("available_in_account")]
            source = "account"
        elif pricing:
            primary_ids = [item["model_name"] for item in pricing.values()]
            source = "pricing"
        else:
            primary_ids = [m["id"] for m in previous["models"]]
            source = previous["model_source"]
        primary_keys = {model_key(mid) for mid in primary_ids}
        candidates = list(primary_ids)
        for m in previous["models"] + DEFAULT_MODELS:
            if model_key(m["id"]) not in {model_key(mid) for mid in candidates}:
                candidates.append(m["id"])
        for notice in state["announcements"]:
            for match in _MODEL_TOKEN.finditer(notice["content"]):
                mid = match.group().rstrip(".")
                if "-" in mid and model_key(mid) not in {model_key(value) for value in candidates}:
                    candidates.append(mid)
        old_by_key = {model_key(m["id"]): m for m in previous["models"]}
        models = []
        for mid in candidates:
            model = _make_model(mid, pricing.get(model_key(mid)))
            old = old_by_key.get(model_key(mid), {})
            if "pricing" not in responses and "multiplier" not in model and "multiplier" in old:
                model["multiplier"] = old["multiplier"]
            if account_ids is not None:
                model["available_in_account"] = model_key(mid) in primary_keys
            elif source == "account":
                model["available_in_account"] = old.get("available_in_account")
            models.append(model)
        models = apply_announcements(models, state["announcements"])
        models = [m for m in models if model_key(m["id"]) in primary_keys or m["provider_status"] == "unavailable"]
        for model in models:
            old = old_by_key.get(model_key(model["id"]), {})
            changed = old.get("provider_status") != model["provider_status"] or old.get("release_minutes_utc") != model["release_minutes_utc"]
            model["policy_updated_at"] = now if changed else old.get("policy_updated_at", 0)
        state.update(models=models, model_source=source,
                     pricing_stale="pricing" in errors,
                     models_stale=bool("account" in errors or (not pricing and account_ids is None)))
        if account_ids is not None or (pricing and source == "pricing"):
            state["models_updated_at"] = now
        eligible = [m for m in models if m["provider_status"] != "unavailable" and m.get("available_in_account") is not False]
        eligible.sort(key=lambda m: (not m["recommended"], m["quota_limited"] is not False, m["id"]))
        state["recommended_model"] = eligible[0]["id"] if eligible else None
        state["error"] = "; ".join(errors.values())
        if cancel_event is not None and cancel_event.is_set():
            with _LOCK:
                _STATE["refreshing"] = False
            return get_snapshot()
        with _LOCK:
            if scope != _SCOPE:
                return get_snapshot()
            _STATE = state
            CATALOG_MODELS[:] = copy.deepcopy(models)
        _save_cache(scope, state)
        return get_snapshot()
    finally:
        with _LOCK:
            _STATE["refreshing"] = False
        _REFRESH_LOCK.release()


def request_refresh():
    cfg = config_manager.load_config()
    _ensure_scope(cfg.get("base_url", "https://agentrouter.org").rstrip("/"), cfg.get("api_key", ""))
    _WAKE.set()


def start(interval_seconds=REFRESH_INTERVAL_SECONDS):
    """Start one daemon worker; HTTP handlers always read its cached snapshot."""
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        cfg = config_manager.load_config()
        _ensure_scope(cfg.get("base_url", "https://agentrouter.org").rstrip("/"), cfg.get("api_key", ""))
        _STOP.clear()
        _WAKE.clear()

        def worker():
            while not _STOP.is_set():
                try:
                    refresh(cancel_event=_STOP)
                except Exception:
                    with _LOCK:
                        _STATE.update(refreshing=False, notices_stale=True, models_stale=True, error="Provider refresh failed; retrying automatically.")
                if _STOP.is_set():
                    break
                _WAKE.wait(interval_seconds)
                _WAKE.clear()

        _THREAD = threading.Thread(target=worker, name="provider-sync", daemon=True)
        _THREAD.start()


def stop():
    _STOP.set()
    _WAKE.set()
    thread = _THREAD
    if thread is not None and thread is not threading.current_thread():
        thread.join(timeout=1)
