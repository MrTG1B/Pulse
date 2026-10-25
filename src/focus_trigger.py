"""
Focus Trigger — Windows App Focus & Keypress Automation.
Detects Codex and Claude Code (both Electron/Chromium desktop apps) and:
  1. Finds open windows:
       - Codex: matches codex.exe, OpenAI.Codex package (ChatGPT.exe), or title
       - Claude Code: matches claude.exe, claude-code path, or title
  2. Focuses them: Win32 Alt-key input privilege + HWND_TOPMOST Z-order trick
       (Zero WScript.Shell SendKeys — 100% immune to the Windows NumLock glitch!)
  3. Presses Enter: Hardware-level Win32 VK_RETURN keybd_event

Technical notes:
  - Codex on Windows 11 installs as an MSIX package under D:\\WindowsApps\\OpenAI.Codex_...
    where its executable name is ChatGPT.exe! Matching proc.exe() is required.
  - Claude Code can run as claude.exe from AppData\\Local\\Claude-3p\\claude-code or WindowsApps.
  - WScript.Shell.SendKeys('%') has a documented bug on Windows where it flips NumLock.
    We avoid SendKeys entirely and use pure Win32 keybd_event and SetWindowPos.
  - PostMessage(WM_KEYDOWN) is ignored by Chromium; keybd_event sends a real hardware-level
    scancode that Chromium input handlers properly process.
"""

import time
import logging
import ctypes
from ctypes import wintypes
from typing import List, Dict, Any, Optional, Callable

try:
    import psutil
    import win32gui
    import win32con
    import win32api
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

logger = logging.getLogger(__name__)

# Fallback keywords for window titles
CODEX_TITLE_KEYWORDS = ["codex"]
CLAUDE_TITLE_KEYWORDS = ["claude"]


def _get_all_visible_windows() -> List[Dict[str, Any]]:
    """Return all visible, titled windows with hwnd, title, pid, pname, and pexe."""
    if not HAS_WIN32:
        return []
    results: List[Dict[str, Any]] = []

    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if not title:
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                pname = proc.name().lower()
                try:
                    pexe = proc.exe().lower()
                except Exception:
                    pexe = ""
            except Exception:
                pid, pname, pexe = 0, "", ""
            results.append({
                "hwnd": hwnd,
                "title": title,
                "pid": pid,
                "pname": pname,
                "pexe": pexe,
            })
        except Exception:
            pass
        return True

    cb_func = WNDENUMPROC(_cb)
    user32.EnumWindows(cb_func, 0)
    return results


def is_codex_window(w: Dict[str, Any]) -> bool:
    """Check if window belongs to OpenAI Codex."""
    pname = w.get("pname", "").lower()
    pexe = w.get("pexe", "").lower()
    title = w.get("title", "").lower()

    # 1. Process name is codex.exe or codex
    if pname in ["codex.exe", "codex"]:
        return True
    # 2. Exe path contains openai.codex (e.g. OpenAI.Codex_...app\\ChatGPT.exe)
    if "openai.codex" in pexe or "\\codex\\" in pexe or "/codex/" in pexe:
        return True
    # 3. Process is chatgpt.exe and path contains codex
    if "chatgpt" in pname and "codex" in pexe:
        return True
    # 4. Fallback: title explicitly contains "codex"
    if any(kw in title for kw in CODEX_TITLE_KEYWORDS):
        return True
    return False


def is_claude_window(w: Dict[str, Any], custom_keywords: Optional[List[str]] = None) -> bool:
    """Check if window belongs to Anthropic Claude Code."""
    pname = w.get("pname", "").lower()
    pexe = w.get("pexe", "").lower()
    title = w.get("title", "").lower()

    # 1. Process name is claude.exe
    if pname in ["claude.exe", "claude"]:
        return True
    # 2. Exe path contains claude (e.g. Claude-3p\\claude-code)
    if "claude" in pexe:
        return True
    # 3. Fallback: title contains "claude" or custom keyword
    kws = custom_keywords or CLAUDE_TITLE_KEYWORDS
    if any(kw in title for kw in kws):
        return True
    return False


def find_target_windows(
    custom_keywords: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Find open Codex and Claude Code windows.

    Detection strategy:
      CODEX       → pname is codex.exe OR pexe path contains "openai.codex"
                    OR title contains "codex"
      CLAUDE CODE → pname is claude.exe OR pexe path contains "claude"
                    OR title contains "claude"

    Returns list of dicts: {hwnd, title, pid, app: "codex"|"claude"}
    """
    all_windows = _get_all_visible_windows()
    found: List[Dict[str, Any]] = []
    seen: set = set()

    for w in all_windows:
        hwnd = w["hwnd"]
        if hwnd in seen:
            continue

        if is_codex_window(w):
            found.append({**w, "app": "codex"})
            seen.add(hwnd)
            continue

        if is_claude_window(w, custom_keywords):
            found.append({**w, "app": "claude"})
            seen.add(hwnd)
            continue

    logger.info(
        "[FocusTrigger] Found %d target window(s): %s",
        len(found),
        [(w["app"], w["title"][:60]) for w in found],
    )
    return found


def force_foreground(hwnd: int) -> bool:
    """
    Bring a window to foreground reliably on Windows 10/11.

    Zero WScript.Shell SendKeys — prevents the famous NumLock glitch!
    Bypasses Windows focus-stealing lock by:
      1. Restoring if minimized (SW_RESTORE only when IsIconic).
      2. Simulating native VK_MENU (Alt key) event to gain input privilege.
      3. Using the Z-order TopMost trick (HWND_TOPMOST -> HWND_NOTOPMOST)
         to force the OS to pop the window to the top.
      4. Calling BringWindowToTop and SetForegroundWindow.
    """
    if not HAS_WIN32:
        return False
    try:
        # Step 1: restore ONLY if minimised
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.15)

        # Step 2: Acquire foreground permission via native Win32 Alt-key event (VK_MENU)
        # Note: We do NOT use WScript.Shell.SendKeys('%') because that toggles NumLock!
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)

        # Step 3: Z-order trick (HWND_TOPMOST -> HWND_NOTOPMOST)
        # Forces Windows to elevate the window above other layers
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_NOTOPMOST,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )

        # Release Alt-key
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

        # Step 4: AttachThreadInput to safely transfer focus privilege on Windows 10/11
        fg_hwnd = win32gui.GetForegroundWindow()
        if fg_hwnd and fg_hwnd != hwnd:
            fg_thread = win32process.GetWindowThreadProcessId(fg_hwnd)[0]
            cur_thread = win32api.GetCurrentThreadId()
            if fg_thread and fg_thread != cur_thread:
                try:
                    win32process.AttachThreadInput(cur_thread, fg_thread, True)
                    win32gui.BringWindowToTop(hwnd)
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
                finally:
                    try:
                        win32process.AttachThreadInput(cur_thread, fg_thread, False)
                    except Exception:
                        pass
            else:
                try:
                    win32gui.BringWindowToTop(hwnd)
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
        else:
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass

        time.sleep(0.15)
        return True

    except Exception as exc:
        logger.error("[FocusTrigger] force_foreground hwnd=%d error: %s", hwnd, exc)
        return False


def simulate_enter(hwnd: int, app_type: str = "unknown") -> bool:
    """
    Send an Enter keypress to the target window.
    Uses pure Win32 keybd_event(VK_RETURN) hardware keystroke.
    Does NOT toggle NumLock and delivers directly to the foreground app.
    """
    try:
        # Re-confirm target is foreground
        if HAS_WIN32:
            if win32gui.GetForegroundWindow() != hwnd:
                force_foreground(hwnd)
                time.sleep(0.1)

        # Hardware-level Enter key press and release
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        logger.info("[FocusTrigger] Native Enter pressed on %s window.", app_type)
        return True

    except Exception as exc:
        logger.error("[FocusTrigger] simulate_enter error: %s", exc)
        if HAS_PYAUTOGUI:
            try:
                pyautogui.press('enter')
                return True
            except Exception:
                pass
        return False


def trigger_all_targets(
    press_enter: bool = True,
    custom_keywords: Optional[List[str]] = None,
    ai_gate_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Full pipeline: scan → focus → (optional Gemini Live gate) → Enter.

    Args:
        press_enter:     Whether to press Enter after focusing.
        custom_keywords: Extra window title keywords to match.
        ai_gate_fn:      Optional callable(hwnd, title) -> bool.
                         If provided, Enter is only pressed when it returns True.

    Returns a results dict consumed by the REST API and Pulse UI.
    """
    results: Dict[str, Any] = {
        "found": [],
        "focused": [],
        "entered": [],
        "skipped_by_ai": [],
        "errors": [],
        "message": "",
        "ai_message": "",
    }

    targets = find_target_windows(custom_keywords)
    if not targets:
        results["message"] = (
            "No Codex or Claude Code windows found — apps may be closed."
        )
        return results

    for win in targets:
        hwnd = win["hwnd"]
        title = win["title"]
        app = win["app"]
        results["found"].append({"hwnd": hwnd, "title": title, "app": app})

        focused = force_foreground(hwnd)
        if not focused:
            results["errors"].append(f"Could not focus: {title}")
            continue
        results["focused"].append(title)
        time.sleep(0.25)

        if press_enter:
            # Optional Gemini gate: ask AI whether Enter should fire (supports vision/live feedback)
            if ai_gate_fn is not None:
                try:
                    import inspect
                    sig = inspect.signature(ai_gate_fn)
                    if len(sig.parameters) >= 2:
                        should_enter = ai_gate_fn(hwnd, title)
                    else:
                        should_enter = ai_gate_fn(title)
                except Exception as exc:
                    logger.warning("[FocusTrigger] AI gate error: %s — defaulting YES", exc)
                    should_enter = True

                if not should_enter:
                    results["skipped_by_ai"].append(title)
                    logger.info("[FocusTrigger] AI gate said NO for '%s' — skipping Enter.", title)
                    continue

            if simulate_enter(hwnd, app_type=app):
                results["entered"].append(title)
            else:
                results["errors"].append(f"Enter failed: {title}")

    n_found = len(results["found"])
    n_focused = len(results["focused"])
    n_entered = len(results["entered"])
    n_skipped = len(results["skipped_by_ai"])

    results["message"] = (
        f"Found {n_found} app(s) · Focused {n_focused} · Pressed Enter on {n_entered}"
        + (f" · AI skipped {n_skipped}" if n_skipped else "")
    )
    return results
