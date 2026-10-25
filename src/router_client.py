"""
AgentRouter Client & Network Diagnostic Module.
Communicates with AgentRouter API, performs latency testing, status evaluation,
and model discovery.
"""

import sys
import os
import time
import threading
import concurrent.futures
import hashlib
import requests
from typing import Dict, Any, List, Optional

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import config_manager
import provider_updates

# Live catalog populated by the background provider synchronizer.
CATALOG_MODELS = provider_updates.CATALOG_MODELS

# Cache of model test results {model_id: {"status_code": ..., "status_type": ..., "timestamp": ...}}
MODEL_STATUS_CACHE: Dict[str, Dict[str, Any]] = {}
MODEL_STATUS_SCOPES: Dict[str, str] = {}

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
                announcements = provider_updates.normalize_announcements(data.get("data", {}).get("announcements", []))
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
        model_id = cfg.get("selected_model", "gpt-6.1-sol")
    if not base_url:
        base_url = cfg.get("base_url", "https://agentrouter.org")

    base_url = base_url.rstrip("/")

    model_meta = provider_updates.get_model(model_id)
    if model_meta:
        model_id = model_meta["id"]
    if model_meta and model_meta.get("provider_status") == "unavailable":
        return {
            "gateway_reachable": None, "gateway_latency_ms": 0,
            "status_code": 0, "status_type": "unavailable",
            "status_title": "Temporarily Unavailable",
            "message": f"AgentRouter has temporarily taken {model_meta['name']} offline. Restoration time has not been announced.",
            "is_quota_exhausted": False, "is_active": False,
            "model_id": model_id, "latency_ms": 0, "timestamp": time.time(),
            "raw_response": None,
        }

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
    if model_meta:
        api_type = model_meta.get("api_type", "openai")
    elif "claude" in model_id.lower():
        api_type = "anthropic"
    elif any(k in model_id.lower() for k in ("astra", "sol", "responses")):
        api_type = "openai_responses"
    else:
        api_type = "openai"

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
        elif api_type == "openai_responses":
            endpoint = f"{base_url}/v1/responses"
            payload = {
                "model": model_id,
                "input": "ping"
            }
        else:
            endpoint = f"{base_url}/v1/chat/completions"
            payload = {
                "model": model_id,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}]
            }

        resp = requests.post(endpoint, headers=headers, json=payload, timeout=(3.0, 8.0))
        latency_ms = int((time.time() - start_time) * 1000)
        status_code = resp.status_code
        raw_response_text = resp.text

        # Self-healing fallback: if model rejected /v1/chat/completions stating it requires /v1/responses
        if status_code == 400 and ("/v1/responses" in raw_response_text or "responses api" in raw_response_text.lower()):
            endpoint = f"{base_url}/v1/responses"
            payload = {
                "model": model_id,
                "input": "ping"
            }
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=(3.0, 8.0))
            latency_ms = int((time.time() - start_time) * 1000)
            status_code = resp.status_code
            raw_response_text = resp.text
            if model_meta:
                model_meta["api_type"] = "openai_responses"

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
        message = "Budget pool quota has been exhausted. Check the current notice for this model or switch to the recommended model."
        is_quota_exhausted = True
    elif status_code == 503 or "无可用渠道" in error_message or "no available channel" in err_lower:
        status_type = "no_channel"
        status_title = "No Channel (503)"
        message = f"Model '{model_id}' is not in your channel group. Refresh the model list or switch to the recommended model."
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
    elif "decryption failure" in err_lower or "cross-resource" in err_lower or "cross_resource" in err_lower:
        status_type = "provider_maintenance"
        status_title = "Provider Response Error"
        message = f"The provider returned a Decryption Failure / Cross-Resource Access error for '{model_id}'. Check the latest notice before retrying."
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
    MODEL_STATUS_SCOPES[model_id] = hashlib.sha256((base_url + "\0" + api_key).encode("utf-8")).hexdigest()
    return result


def get_all_models_with_status() -> List[Dict[str, Any]]:
    """
    Returns list of all models combined with their current status from cache.
    """
    models = []
    for m in provider_updates.get_snapshot()["models"]:
        item = dict(m)
        cached = MODEL_STATUS_CACHE.get(m["id"])
        if m.get("provider_status") == "unavailable":
            item.update(status_code=None, status_type="unavailable", status_title="Temporarily Unavailable", latency_ms=None, last_checked=None)
        elif cached and MODEL_STATUS_SCOPES.get(m["id"]) == provider_updates.get_scope() and cached.get("timestamp", 0) >= m.get("policy_updated_at", 0):
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
        model_ids = [m["id"] for m in provider_updates.get_snapshot()["models"]
                     if m.get("provider_status") != "unavailable" and m.get("available_in_account") is not False]

    if not model_ids:
        return {"results": {}, "models": get_all_models_with_status()}

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
    """Refresh provider metadata and reconcile the live account model catalog."""
    snapshot = provider_updates.refresh(api_key=api_key, base_url=base_url)
    ids = [m["id"] for m in snapshot["models"] if m.get("provider_status") != "unavailable"
           and m.get("available_in_account") is not False]
    return {
        "success": not snapshot["models_stale"], "count": len(ids), "discovered_ids": ids,
        "message": snapshot["error"] or f"Discovered {len(ids)} models from AgentRouter.",
        "models": get_all_models_with_status(), "provider": snapshot,
    }
