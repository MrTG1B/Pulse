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

# Ensure standard output and error never crash with UnicodeEncodeError or NoneType in --noconsole mode
if sys.platform == "win32":
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config_manager
import server as backend_server

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
    """Runs the backend HTTP server in a background thread."""
    httpd = backend_server.run_server(port=port)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    return httpd


def main():
    parser = argparse.ArgumentParser(description="Pulse — Commercial Floating Monitor Widget")
    parser.add_argument("--browser", action="store_true", help="Launch in default web browser instead of desktop window")
    parser.add_argument("--port", type=int, default=8765, help="Port for local widget server")
    args = parser.parse_args()

    port = find_free_port(args.port)
    start_server_thread(port)
    widget_url = f"http://127.0.0.1:{port}"

    print("=" * 60)
    print(" Pulse — Floating Monitor Widget")
    print(f" URL: {widget_url}")
    print("=" * 60)

    cfg = config_manager.load_config()
    always_on_top = cfg.get("always_on_top", True)

    if args.browser or not HAS_WEBVIEW:
        print("[Launcher] Opening widget in web browser...")
        webbrowser.open(widget_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Launcher] Exiting.")
            sys.exit(0)

    window_holder = {}
    api = DesktopApi(window_holder)

    try:
        window = webview.create_window(
            title="Pulse",
            url=widget_url,
            width=410,
            height=720,
            min_size=(360, 90),
            resizable=True,
            frameless=True,
            on_top=always_on_top,
            easy_drag=False,
            background_color="#0A0A0A",
            js_api=api
        )
        window_holder["window"] = window
        webview.start(debug=False)
    except Exception as e:
        print(f"[Launcher] pywebview window error ({e}), falling back to browser...")
        webbrowser.open(widget_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Launcher] Exiting.")
            sys.exit(0)


if __name__ == "__main__":
    main()
