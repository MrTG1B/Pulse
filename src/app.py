"""
AgentRouter Pulse — Floating Desktop Widget Launcher.
Runs the lightweight backend server and displays an always-on-top,
frameless, sleek desktop floating widget using pywebview (Edge WebView2).
"""

import sys
import os
import time
import socket
import threading
import webbrowser
import argparse
import math

_USER_HOME = os.path.expanduser("~")
LOG_DIR = os.path.join(_USER_HOME, ".pulse")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_PATH = os.path.join(LOG_DIR, "pulse.log")
except Exception:
    LOG_PATH = os.path.join(os.environ.get("TEMP", "."), "pulse.log")


def log_debug(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [PID:{os.getpid()}] {msg}\n")
    except Exception:
        pass


def _excepthook(exc_type, exc_val, exc_tb):
    import traceback
    err = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
    log_debug(f"FATAL UNCAUGHT EXCEPTION:\n{err}")


def _thread_excepthook(args):
    import traceback
    err = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    thread_name = getattr(args.thread, "name", "unknown")
    log_debug(f"FATAL UNCAUGHT THREAD EXCEPTION ({thread_name}):\n{err}")


sys.excepthook = _excepthook
if hasattr(threading, "excepthook"):
    threading.excepthook = _thread_excepthook

import logging
try:
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )
except Exception:
    pass

# Ensure standard output and error are redirected to log file in --noconsole mode
if sys.platform == "win32":
    if sys.stdout is None:
        try:
            sys.stdout = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        try:
            sys.stderr = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import config_manager
import server as backend_server
import scheduler as release_scheduler
import atexit
import ctypes
from ctypes import wintypes

_SINGLE_INSTANCE_MUTEX = None


def _get_kernel32():
    """Keep Windows mutex handles pointer-sized on 64-bit Python."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def acquire_single_instance_lock(mutex_name: str = "Local\\AgentRouterPulseSingleInstanceMutex") -> bool:
    """
    Acquires a process-lifetime named mutex on Windows.
    Returns True if this is the first/only instance.
    Returns False if another instance is already running.
    """
    global _SINGLE_INSTANCE_MUTEX
    if sys.platform != "win32":
        return True

    try:
        kernel32 = _get_kernel32()
        mutex = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = ctypes.get_last_error()
        log_debug(f"acquire_single_instance_lock: handle={mutex}, last_error={last_error}")
        if not mutex:
            log_debug(f"acquire_single_instance_lock: unable to create mutex, error={last_error}")
            return False
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            if mutex:
                kernel32.CloseHandle(mutex)
            log_debug("acquire_single_instance_lock: mutex already exists, lock denied.")
            return False
        _SINGLE_INSTANCE_MUTEX = mutex
        log_debug("acquire_single_instance_lock: mutex successfully acquired.")
        return True
    except Exception as exc:
        log_debug(f"Single-instance mutex warning: {exc}")
        return False


def release_single_instance_lock():
    """Releases the named mutex handle if held."""
    global _SINGLE_INSTANCE_MUTEX
    if sys.platform == "win32" and _SINGLE_INSTANCE_MUTEX:
        try:
            _get_kernel32().CloseHandle(_SINGLE_INSTANCE_MUTEX)
            log_debug("release_single_instance_lock: mutex handle closed.")
        except Exception:
            pass
        _SINGLE_INSTANCE_MUTEX = None


atexit.register(release_single_instance_lock)


def calculate_window_geometry(work_area, scale: float = 1.0, width: int = 410, height: int = 720) -> dict:
    """Convert a physical monitor work area into pywebview's logical pixels."""
    if scale <= 0:
        raise ValueError("Display scale must be positive")
    left, top, right, bottom = work_area
    if right <= left or bottom <= top:
        raise ValueError("Monitor work area must have a positive size")

    # Round inward so scaling the result back never crosses a monitor edge.
    left, top = math.ceil(left / scale), math.ceil(top / scale)
    right, bottom = math.floor(right / scale), math.floor(bottom / scale)
    available_width, available_height = max(1, right - left), max(1, bottom - top)
    margin_x, margin_y = min(20, available_width // 4), min(20, available_height // 4)
    width = max(1, min(int(width), available_width - 2 * margin_x))
    height = max(1, min(int(height), available_height - 2 * margin_y))
    return {
        "x": right - margin_x - width,
        "y": top + (available_height - height) // 2,
        "width": width,
        "height": height,
    }


def get_initial_window_geometry(width: int = 410, height: int = 720) -> dict:
    """Dock Pulse inside the usable primary monitor, including display scaling."""
    fallback = {"x": None, "y": None, "width": width, "height": height}
    if sys.platform != "win32":
        return fallback
    try:
        user32 = ctypes.windll.user32
        # Match the DPI awareness used by pywebview before reading physical pixels.
        user32.SetProcessDPIAware()
        user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
        user32.SystemParametersInfoW.restype = wintypes.BOOL
        work = wintypes.RECT()
        if not user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0):  # SPI_GETWORKAREA
            raise OSError("Unable to read the monitor work area")
        get_dpi = getattr(user32, "GetDpiForSystem", None)
        dpi = 96
        if get_dpi:
            get_dpi.argtypes = []
            get_dpi.restype = wintypes.UINT
            dpi = get_dpi() or 96
        work_area = (work.left, work.top, work.right, work.bottom)
        geometry = calculate_window_geometry(work_area, dpi / 96.0, width, height)
        log_debug(f"Monitor work area={work_area}, DPI={dpi}, logical window geometry={geometry}")
        return geometry
    except Exception as exc:
        log_debug(f"Window positioning warning: {exc}; using automatic centering")
        return fallback


def restore_pulse_window(hwnd: int) -> bool:
    """Show Pulse and fit it to its nearest monitor without changing its pin state."""
    if sys.platform != "win32":
        return False
    try:
        import win32api
        import win32con
        import win32gui

        if not win32gui.IsWindow(hwnd):
            return False
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        elif not win32gui.IsWindowVisible(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        work = win32api.GetMonitorInfo(monitor)["Work"]
        width = min(max(1, right - left), work[2] - work[0])
        height = min(max(1, bottom - top), work[3] - work[1])
        x = max(work[0], min(left, work[2] - width))
        y = max(work[1], min(top, work[3] - height))
        win32gui.SetWindowPos(
            hwnd, 0, x, y, width, height,
            win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
        )
        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as exc:
            # Windows can deny focus stealing; the window must still be visible.
            log_debug(f"Pulse foreground activation notice: {exc}")

        rect = win32gui.GetWindowRect(hwnd)
        visible = bool(win32gui.IsWindowVisible(hwnd)) and not win32gui.IsIconic(hwnd)
        fits = work[0] <= rect[0] < rect[2] <= work[2] and work[1] <= rect[1] < rect[3] <= work[3]
        log_debug(f"Pulse window recovery: hwnd={hwnd}, rect={rect}, work_area={work}, visible={visible}, fits={fits}")
        return visible and fits
    except Exception as exc:
        log_debug(f"Pulse window recovery warning: {exc}")
        return False


def focus_existing_instance(timeout_sec: float = 3.5) -> bool:
    """
    Finds and brings any already running Pulse instance window to the foreground.
    Retries up to timeout_sec to allow a launching instance to complete showing its window.
    """
    if sys.platform != "win32":
        return False
    log_debug("focus_existing_instance: attempting to find existing Pulse window...")
    end_time = time.monotonic() + timeout_sec
    while True:
        try:
            import win32gui
            candidates = []

            def _enum_cb(hwnd, _lparam):
                title = win32gui.GetWindowText(hwnd)
                if title == "Pulse" or title.startswith(("Pulse —", "Pulse -")):
                    # Include hidden/minimized windows, but exclude browser tabs named Pulse.
                    if win32gui.GetClassName(hwnd).startswith("WindowsForms"):
                        candidates.append(hwnd)
                return True

            win32gui.EnumWindows(_enum_cb, None)
            for hwnd in candidates:
                if restore_pulse_window(hwnd):
                    return True
        except Exception as exc:
            log_debug(f"focus_existing_instance error: {exc}")

        if time.monotonic() >= end_time:
            break
        time.sleep(0.3)

    log_debug("focus_existing_instance: no recoverable Pulse window found within timeout")
    return False


try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False


def find_free_port(start_port: int = 8765) -> int:
    """Finds an available TCP port starting from start_port."""
    port = start_port
    while port < 65535:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            port += 1
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DesktopApi:
    """API bridge exposed to JavaScript inside pywebview."""

    def __init__(self, window_holder):
        self.window_holder = window_holder

    def close_window(self):
        w = self.window_holder.get("window")
        if w:
            try:
                w.destroy()
                return True
            except Exception:
                pass
        return False

    def minimize_window(self):
        w = self.window_holder.get("window")
        if w:
            try:
                w.minimize()
                return True
            except Exception:
                pass
        return False

    def resize_window(self, width: int, height: int):
        w = self.window_holder.get("window")
        if w:
            try:
                w.resize(int(width), int(height))
                if sys.platform == "win32" and getattr(w, "native", None) is not None:
                    restore_pulse_window(int(w.native.Handle.ToInt64()))
                return True
            except Exception:
                pass
        return False

    def toggle_always_on_top(self, pinned: bool):
        w = self.window_holder.get("window")
        if w:
            try:
                w.on_top = bool(pinned)
                return True
            except Exception:
                pass
        return False

    def open_external_url(self, url: str):
        try:
            if url and (url.startswith("http://") or url.startswith("https://")):
                webbrowser.open(url)
                return True
        except Exception:
            pass
        return False


def start_server_thread(port: int):
    """Runs the backend HTTP server in a background thread and starts the release scheduler."""
    httpd = backend_server.run_server(port=port)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    # Start release scheduler for auto-focus feature (07:30 AM & 04:30 PM IST)
    try:
        release_scheduler.start()
    except Exception as e:
        print(f"[Launcher] Scheduler start notice: {e}")
    return httpd


def main():
    import multiprocessing
    multiprocessing.freeze_support()

    log_debug(f"=== Pulse main() started. PID={os.getpid()} ARGS={sys.argv} ===")

    parser = argparse.ArgumentParser(description="Pulse — Floating Availability Monitor Widget")
    parser.add_argument("--browser", action="store_true", help="Launch in default web browser instead of desktop window")
    parser.add_argument("--port", type=int, default=8765, help="Port for local widget server")
    parser.add_argument("--allow-multiple", action="store_true", help="Allow multiple instances of Pulse (e.g. for testing)")
    args = parser.parse_args()

    # Enforce strict single instance: if another instance is already running, focus its window and exit.
    if not args.allow_multiple and not acquire_single_instance_lock():
        log_debug("Single-instance mutex held by another process. Focusing existing window and exiting duplicate...")
        focused = focus_existing_instance(timeout_sec=10.0)
        if focused:
            log_debug("Existing visible Pulse window focused successfully. Exiting duplicate instance.")
            print("[Launcher] Another instance of Pulse is already running. Focused existing window.")
        else:
            log_debug("The existing Pulse instance may still be starting. Exiting duplicate without terminating processes.")
            print(f"[Launcher] Pulse is already running or starting. See {LOG_PATH} for details.")
        return

    port = find_free_port(args.port)
    start_server_thread(port)
    widget_url = f"http://127.0.0.1:{port}"
    log_debug(f"Local server listening on {widget_url}")

    print("=" * 60)
    print(" Pulse — Floating Monitor Widget")
    print(f" URL: {widget_url}")
    print("=" * 60)

    cfg = config_manager.load_config()
    always_on_top = cfg.get("always_on_top", True)

    if args.browser or not HAS_WEBVIEW:
        log_debug("Launching in default web browser...")
        print("[Launcher] Opening widget in web browser...")
        webbrowser.open(widget_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log_debug("Browser mode interrupted. Exiting.")
            sys.exit(0)

    window_holder = {}
    api = DesktopApi(window_holder)

    try:
        geometry = get_initial_window_geometry()
        log_debug(f"Creating pywebview window (title='Pulse', geometry={geometry})...")
        window = webview.create_window(
            title="Pulse",
            url=widget_url,
            width=geometry["width"],
            height=geometry["height"],
            x=geometry["x"],
            y=geometry["y"],
            min_size=(min(360, geometry["width"]), min(90, geometry["height"])),
            resizable=True,
            frameless=True,
            on_top=always_on_top,
            easy_drag=False,
            background_color="#0A0A0A",
            js_api=api
        )
        window_holder["window"] = window

        def _on_shown():
            log_debug("EVENT: Window shown on screen!")
            if sys.platform == "win32" and getattr(window, "native", None) is not None:
                restore_pulse_window(int(window.native.Handle.ToInt64()))

        def _on_loaded():
            log_debug("EVENT: Window UI content loaded!")

        window.events.shown += _on_shown
        window.events.loaded += _on_loaded

        # Explicit test instances must not contend for the normal WebView2 profile.
        profile = f"webview_cache_{os.getpid()}" if args.allow_multiple else "webview_cache"
        cache_dir = os.path.join(LOG_DIR, profile)
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            pass

        log_debug(f"Calling webview.start(storage_path={cache_dir})...")
        try:
            webview.start(debug=False, private_mode=False, storage_path=cache_dir)
        except Exception as we:
            log_debug(f"webview.start primary cache error ({we}), falling back to unique session cache...")
            alt_cache_dir = os.path.join(LOG_DIR, f"webview_cache_{os.getpid()}")
            try:
                os.makedirs(alt_cache_dir, exist_ok=True)
            except Exception:
                pass
            webview.start(debug=False, private_mode=False, storage_path=alt_cache_dir)
        log_debug("webview.start() completed cleanly.")
    except BaseException as e:
        log_debug(f"pywebview window error ({type(e).__name__}: {e}), falling back to browser...")
        print(f"[Launcher] pywebview window error ({e}), falling back to browser...")
        webbrowser.open(widget_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log_debug("Browser fallback interrupted. Exiting.")
            sys.exit(0)


if __name__ == "__main__":
    main()
