"""
Gemini Live Helper — Multimodal AI Feedback System for Pulse Focus Trigger.

Roles:
  A) Multimodal Feedback Gate — Captures window screenshot and uses Gemini Live /
     Multimodal model (gemini-3.8-live / gemini-3.8-flash) to inspect the app state
     (e.g., verifying 402 quota error, pending prompt, billing alert).
  B) Live Narrator — Generates real-time feedback narrations for the Pulse desktop widget.

Graceful degradation: if the SDK is missing or the API call fails, defaults are
returned so the core scheduler is never blocked.
"""

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Preferred Live & Multimodal model endpoints
GEMINI_LIVE_MODELS = [
    "gemini-3.8-live",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash-exp",
]

# Check for google.genai (new official SDK) or google.generativeai (legacy)
HAS_GENAI = False
USE_NEW_SDK = False

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
    USE_NEW_SDK = True
except Exception:
    try:
        import google.generativeai as gai
        HAS_GENAI = True
        USE_NEW_SDK = False
    except Exception:
        HAS_GENAI = False


def capture_window_screenshot(hwnd: int):
    """
    Capture a screenshot of a specific window by HWND or the primary screen.
    Returns a PIL Image, or None if capture fails.
    """
    try:
        from PIL import ImageGrab
        import win32gui
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        if right > left and bottom > top:
            # Crop to window bounds
            return ImageGrab.grab(bbox=(max(0, left), max(0, top), right, bottom))
        return ImageGrab.grab()
    except Exception as exc:
        logger.warning("[Gemini Vision] Window screenshot capture failed: %s", exc)
        try:
            from PIL import ImageGrab
            return ImageGrab.grab()
        except Exception:
            return None


def _get_image_bytes(img) -> Optional[bytes]:
    """Convert a PIL Image to JPEG bytes."""
    if img is None:
        return None
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("[Gemini Vision] Image conversion error: %s", exc)
        return None


def ai_verify_window_from_screenshot(hwnd: int, window_title: str, api_key: str) -> bool:
    """
    Multimodal Feedback Gate:
    Captures the app window screenshot and asks Gemini Live / Multimodal model
    to verify if the window is currently in a 402 quota error or awaiting prompt resume.
    """
    if not HAS_GENAI or not api_key:
        return True

    img = capture_window_screenshot(hwnd)
    img_bytes = _get_image_bytes(img)

    prompt = (
        f"You are the Pulse AI Gate verifying a desktop coding assistant ('{window_title}'). "
        f"Quota just dropped at release time. Inspect this window screen. "
        f"Is there a 402 Payment Required error, budget pool exhausted error, billing issue, "
        f"or prompt ready to resume where pressing Enter is appropriate? "
        f"Answer YES if we should press Enter to resume, or NO if the user is typing or no action needed. "
        f"Include YES or NO in your answer."
    )

    # 1. Try with new google.genai SDK
    if USE_NEW_SDK:
        try:
            client = genai.Client(api_key=api_key)
            for model_name in GEMINI_LIVE_MODELS:
                try:
                    contents = [prompt]
                    if img_bytes:
                        contents.append(
                            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
                        )
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                    )
                    text = resp.text.strip().upper()
                    logger.info("[Gemini Live Gate: %s] Result: %s", model_name, text[:100])
                    return "YES" in text or "NO" not in text
                except Exception as model_err:
                    logger.debug("[Gemini Live Gate] %s failed: %s — trying next", model_name, model_err)
                    continue
        except Exception as exc:
            logger.warning("[Gemini Live Gate] SDK error: %s", exc)

    # 2. Fallback to legacy google.generativeai or text gate
    return ai_should_press_enter(window_title, api_key)


def ai_should_press_enter(window_title: str, api_key: str) -> bool:
    """
    Text-based gate fallback: Ask Gemini whether pressing Enter is appropriate.
    Defaults to True when Gemini is unavailable.
    """
    if not HAS_GENAI or not api_key:
        return True
    try:
        if USE_NEW_SDK:
            client = genai.Client(api_key=api_key)
            for model_name in GEMINI_LIVE_MODELS:
                try:
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=(
                            f"The desktop app window '{window_title}' is either Codex or Claude Code. "
                            f"AgentRouter quota just released. A 402 quota error may be pending. "
                            f"Should we press Enter now to resume the pending task? Answer YES or NO."
                        ),
                    )
                    answer = resp.text.strip().upper()
                    return "YES" in answer or "NO" not in answer
                except Exception:
                    continue
            return True
        else:
            import google.generativeai as gai
            gai.configure(api_key=api_key)
            model = gai.GenerativeModel("gemini-2.5-flash")
            resp = model.generate_content(
                f"Should we press Enter now on '{window_title}' to resume quota-blocked task? Reply YES or NO."
            )
            return "YES" in resp.text.strip().upper()
    except Exception as exc:
        logger.warning("[Gemini Gate] Error (%s) — defaulting YES", exc)
        return True


def ai_narrate_trigger(results: dict, api_key: str) -> str:
    """
    Ask Gemini Live model to write a short, friendly Pulse UI notification sentence
    summarizing what happened after the trigger fired.
    """
    if not HAS_GENAI or not api_key:
        return results.get("message", "Trigger complete.")

    prompt = (
        f"Pulse auto-focus fired at AgentRouter quota release time. "
        f"Apps found: {[w['title'] for w in results.get('found', [])]}. "
        f"Enter pressed on: {results.get('entered', [])}. "
        f"Write ONE friendly desktop notification sentence (max 10 words, with emoji). "
        f"Example: 'Quota released — Codex & Claude Code are back online! ⚡'"
    )

    if USE_NEW_SDK:
        try:
            client = genai.Client(api_key=api_key)
            for model_name in GEMINI_LIVE_MODELS:
                try:
                    resp = client.models.generate_content(model=model_name, contents=prompt)
                    narration = resp.text.strip()
                    if narration:
                        return narration
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("[Gemini Narrate] Error: %s", exc)

    return results.get("message", "Trigger complete.")
