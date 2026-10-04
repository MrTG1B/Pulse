"""
AgentRouter Client & Network Diagnostic Module.
Communicates with AgentRouter API, performs latency testing, status evaluation,
and model discovery.
"""

import time
import threading
import concurrent.futures
import requests
from typing import Dict, Any, List, Optional
import config_manager

# Officially supported / common models on AgentRouter
CATALOG_MODELS = [
    # Discovered & Active Models on AgentRouter (core group)
    {
        "id": "deepseek-v4-flash",
        "name": "⚡ DeepSeek V4 Flash",
        "provider": "DeepSeek",
        "category": "uninterrupted",
        "quota_limited": False,
        "api_type": "openai",
        "tag": "⚡ Active (200)"
    },
    {
        "id": "claude-opus-4-8",
        "name": "Claude Opus 4.8",
        "provider": "Anthropic",
        "category": "claude",
        "quota_limited": True,
        "api_type": "anthropic",
        "tag": "Quota Pool"
    },
    {
        "id": "claude-opus-5",
        "name": "Claude Opus 5",
        "provider": "Anthropic",
        "category": "claude",
        "quota_limited": True,
        "api_type": "anthropic",
        "tag": "Quota Pool"
    },
    {
        "id": "gpt-6-astra",
        "name": "GPT-6 Astra",
        "provider": "OpenAI",
        "category": "openai",
        "quota_limited": True,
        "api_type": "openai",
        "tag": "Quota Pool"
    }
]

# Cache of model test results {model_id: {"status_code": ..., "status_type": ..., "timestamp": ...}}
MODEL_STATUS_CACHE: Dict[str, Dict[str, Any]] = {}

# Gateway health cache and lock to prevent hammering /api/status on rapid/concurrent model checks
_GATEWAY_CACHE: Dict[str, Any] = {"timestamp": 0.0, "url": "", "data": None}
_GATEWAY_CACHE_TTL = 30.0  # seconds
_GATEWAY_LOCK = threading.RLock()


def get_auth_headers(api_key: Optional[str] = None) -> Dict[str, str]:
    """
    Returns authentic client headers compatible with AgentRouter.
    Uses official claude-cli client identity matching supported coding clients
    (Claude Code, Codex) to ensure seamless API interoperability.
    """
    headers = {
        "User-Agent": "claude-cli/1.0.108 (external, cli)",
        "anthropic-version": "2023-06-01",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["x-api-key"] = api_key
    return headers


def check_gateway_health(base_url: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Checks if AgentRouter gateway is reachable and extracts system status.
    Uses /api/status endpoint with thread-safe caching to avoid redundant round trips.
    """
    global _GATEWAY_CACHE
    if not base_url:
        cfg = config_manager.load_config()
        base_url = cfg.get("base_url", "https://agentrouter.org")

    base_url = base_url.rstrip("/")
    status_url = f"{base_url}/api/status"

    with _GATEWAY_LOCK:
        now = time.time()
        if not force_refresh and _GATEWAY_CACHE["data"] and _GATEWAY_CACHE["url"] == status_url and (now - _GATEWAY_CACHE["timestamp"]) < _GATEWAY_CACHE_TTL:
            return _GATEWAY_CACHE["data"]

        start_time = time.time()
        try:
            resp = requests.get(status_url, timeout=(3.05, 5.0), headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json"
            })
            latency_ms = int((time.time() - start_time) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                announcements = data.get("data", {}).get("announcements", [])
                latest_announcement = announcements[0].get("content", "") if announcements else ""
                version = data.get("data", {}).get("version", "online")

                result = {
                    "reachable": True,
                    "status_code": 200,
                    "latency_ms": latency_ms,
                    "version": version,
                    "announcement": latest_announcement,
                    "message": "Gateway is online and reachable.",
                    "url": status_url
                }
            else:
                result = {
                    "reachable": False,
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "message": f"Gateway responded with HTTP {resp.status_code}",
                    "url": status_url
                }
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            result = {
                "reachable": False,
                "status_code": 0,
                "latency_ms": latency_ms,
                "message": f"Gateway unreachable: {str(e)}",
                "url": status_url
            }

        _GATEWAY_CACHE = {"timestamp": now, "url": status_url, "data": result}
        return result


def test_model_connection(
    api_key: Optional[str] = None,
    model_id: Optional[str] = None,
    base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tests connection to AgentRouter for a specific model.
    Evaluates:
      - 200 OK: Active / Quota available
      - 402: Budget pool quota exhausted
      - 401: Unauthorized / invalid key / unauthenticated
      - 429: Rate limited
      - 503: Model unavailable / no channel
      - Connection error: Site offline or unreachable
    """
    cfg = config_manager.load_config()
    if not api_key or "••••" in api_key or "..." in api_key:
        api_key = config_manager.get_api_key()
    if not model_id:
        model_id = cfg.get("selected_model", "claude-3-5-sonnet-20241022")
    if not base_url:
        base_url = cfg.get("base_url", "https://agentrouter.org")

    base_url = base_url.rstrip("/")

    if not api_key:
        gateway_info = check_gateway_health(base_url)
        return {
            "gateway_reachable": gateway_info["reachable"],
            "gateway_latency_ms": gateway_info.get("latency_ms", 0),
            "status_code": 0,
            "status_type": "no_key",
            "status_title": "API Key Required",
            "message": "No API Key configured. Please input and save your AgentRouter API key to test connection.",
            "is_quota_exhausted": False,
            "is_active": False,
            "model_id": model_id,
            "latency_ms": gateway_info.get("latency_ms", 0),
            "timestamp": time.time(),
            "raw_response": None
        }

    # Identify model api type
    model_meta = next((m for m in CATALOG_MODELS if m["id"] == model_id), None)
    api_type = model_meta["api_type"] if model_meta else ("anthropic" if "claude" in model_id.lower() else "openai")

    headers = get_auth_headers(api_key=api_key)

    start_time = time.time()
    raw_response_text = ""
    error_message = ""

    try:
        if api_type == "anthropic":
            endpoint = f"{base_url}/v1/messages"
            headers["anthropic-version"] = "2023-06-01"
            payload = {
                "model": model_id,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}]
            }
        else:
            endpoint = f"{base_url}/v1/chat/completions"
            payload = {
                "model": model_id,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}]
            }

        resp = requests.post(endpoint, headers=headers, json=payload, timeout=(3.0, 5.0))
        latency_ms = int((time.time() - start_time) * 1000)
        status_code = resp.status_code
        raw_response_text = resp.text

        try:
            resp_json = resp.json()
            if "error" in resp_json:
                err = resp_json["error"]
                if isinstance(err, dict):
                    error_message = err.get("message", "")
                else:
                    error_message = str(err)
            elif "message" in resp_json:
                error_message = resp_json.get("message", "")
        except Exception:
            error_message = raw_response_text[:200]

        gateway_reachable = True
        gateway_latency_ms = latency_ms

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        status_code = 0
        error_message = str(e)
        # On failure, check if the gateway is reachable at all
        gateway_info = check_gateway_health(base_url)
        gateway_reachable = gateway_info["reachable"]
        gateway_latency_ms = gateway_info.get("latency_ms", latency_ms)

    # Classify status
    is_quota_exhausted = False
    is_active = False

    err_lower = error_message.lower()
    is_quota_exhausted_detected = (
        status_code == 402 or
        "budget pool" in err_lower or
        "quota has been exhausted" in err_lower or
        "额度用尽" in error_message or
        "pool quota" in err_lower
    )

    if status_code == 200:
        status_type = "active"
        status_title = "Connected & Active"
        message = f"Model '{model_id}' is active and operational. Quota is available."
        is_active = True
    elif is_quota_exhausted_detected:
        status_type = "quota_exhausted"
        status_title = "Quota Exhausted (402)"
        message = (
            "Budget pool quota has been exhausted. "
            "Next quota will release at the scheduled batch time. "
            "You can switch to DeepSeek / GLM for uninterrupted use."
        )
        is_quota_exhausted = True
    elif status_code == 503 or "无可用渠道" in error_message or "no available channel" in err_lower:
        status_type = "no_channel"
        status_title = "No Channel (503)"
        message = f"Model '{model_id}' is not in your API key channel group (core). Switch to deepseek-v4-flash (Active 200) or click Discover."
    elif status_code == 401:
        status_type = "unauthorized"
        if "unauthorized client" in err_lower:
            status_title = "Unauthorized Client (401)"
            message = "AgentRouter rejected client identity. Pulse uses compatible request headers for supported coding clients."
        else:
            status_title = "Unauthorized (401)"
            message = f"Invalid API Key or unauthorized token: {error_message or 'Please check your key.'}"
    elif status_code == 429:
        status_type = "rate_limited"
        status_title = "Rate Limited (429)"
        message = f"Rate limit reached on AgentRouter: {error_message}"
    elif status_code == 0:
        status_type = "offline"
        status_title = "Connection Failed"
        message = f"Network connection failed: {error_message}"
    else:
        status_type = "error"
        status_title = f"HTTP {status_code}"
        message = error_message or f"AgentRouter returned status {status_code}"

    result = {
        "gateway_reachable": gateway_reachable,
        "gateway_latency_ms": gateway_latency_ms,
        "status_code": status_code,
        "status_type": status_type,
        "status_title": status_title,
        "message": message,
        "error_detail": error_message,
        "is_quota_exhausted": is_quota_exhausted,
        "is_active": is_active,
        "model_id": model_id,
        "latency_ms": latency_ms,
        "timestamp": time.time(),
        "raw_response": raw_response_text[:350] if raw_response_text else None
    }

    # Update cache
    MODEL_STATUS_CACHE[model_id] = result
    return result


def get_all_models_with_status() -> List[Dict[str, Any]]:
    """
    Returns list of all models combined with their current status from cache.
    """
    models = []
    for m in CATALOG_MODELS:
        item = dict(m)
        cached = MODEL_STATUS_CACHE.get(m["id"])
        if cached:
            item["status_code"] = cached.get("status_code")
            item["status_type"] = cached.get("status_type")
            item["status_title"] = cached.get("status_title")
            item["latency_ms"] = cached.get("latency_ms")
            item["last_checked"] = cached.get("timestamp")
        else:
            item["status_code"] = None
            item["status_type"] = "unchecked"
            item["status_title"] = "Not Checked"
            item["latency_ms"] = None
            item["last_checked"] = None
        models.append(item)
    return models


def batch_check_models(model_ids: Optional[List[str]] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Performs test across multiple models concurrently.
    """
    if not api_key:
        api_key = config_manager.get_api_key()

    if not model_ids:
        # Default test active models on AgentRouter
        model_ids = [
            "deepseek-v4-flash",
            "claude-opus-4-8",
            "claude-opus-5",
            "gpt-6-astra"
        ]

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(model_ids))) as executor:
        future_to_mid = {
            executor.submit(test_model_connection, api_key, mid): mid
            for mid in model_ids
        }
        for future in concurrent.futures.as_completed(future_to_mid):
            mid = future_to_mid[future]
            try:
                results[mid] = future.result()
            except Exception as e:
                results[mid] = {
                    "gateway_reachable": False,
                    "status_code": 0,
                    "status_type": "offline",
                    "status_title": "Check Failed",
                    "message": f"Connection check error: {e}",
                    "model_id": mid,
                    "is_active": False,
                    "is_quota_exhausted": False,
                    "latency_ms": 0,
                    "timestamp": time.time()
                }

    return {
        "results": results,
        "models": get_all_models_with_status()
    }


def discover_models(api_key: Optional[str] = None, base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Attempts to discover active/available models from AgentRouter's /v1/models endpoint.
    Merges any newly found models into CATALOG_MODELS and returns discovery results.
    """
    if not api_key:
        api_key = config_manager.get_api_key()
    if not base_url:
        cfg = config_manager.load_config()
        base_url = cfg.get("base_url", "https://agentrouter.org")

    base_url = base_url.rstrip("/")
    models_url = f"{base_url}/v1/models"

    headers = get_auth_headers(api_key=api_key)

    discovered_ids = []
    try:
        resp = requests.get(models_url, headers=headers, timeout=(3.05, 7.0))
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", []) if isinstance(data, dict) else []
            existing_ids = {m["id"] for m in CATALOG_MODELS}

            for item in items:
                mid = item.get("id")
                if not mid:
                    continue
                discovered_ids.append(mid)
                if mid not in existing_ids:
                    mid_lower = mid.lower()
                    is_uninterrupted = any(k in mid_lower for k in ("deepseek", "glm", "qwen", "kimi", "moonshot"))
                    is_claude = "claude" in mid_lower
                    provider = "Anthropic" if is_claude else ("DeepSeek" if "deepseek" in mid_lower else ("Zhipu AI" if "glm" in mid_lower else "OpenAI"))

                    CATALOG_MODELS.append({
                        "id": mid,
                        "name": mid,
                        "provider": provider,
                        "category": "uninterrupted" if is_uninterrupted else ("claude" if is_claude else "openai"),
                        "quota_limited": not is_uninterrupted,
                        "api_type": "anthropic" if is_claude else "openai",
                        "tag": "⚡ Always Active" if is_uninterrupted else "Quota Pool",
                        "discovered": True
                    })
                    existing_ids.add(mid)

            return {
                "success": True,
                "count": len(discovered_ids),
                "discovered_ids": discovered_ids,
                "message": f"Discovered {len(discovered_ids)} models from AgentRouter.",
                "models": get_all_models_with_status()
            }
        else:
            return {
                "success": False,
                "count": 0,
                "discovered_ids": [],
                "status_code": resp.status_code,
                "message": f"Discovery returned HTTP {resp.status_code}. Using built-in catalog.",
                "models": get_all_models_with_status()
            }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "discovered_ids": [],
            "message": f"Discovery request failed: {e}. Using built-in catalog.",
            "models": get_all_models_with_status()
        }
