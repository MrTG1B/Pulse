"""
Lightweight HTTP Server & REST API for AgentRouter Monitor Widget.
Runs locally on 127.0.0.1 to serve widget frontend and bridge API calls.
"""

import json
import os
import sys
import time
import mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

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
import time_service
import router_client
import provider_updates
import usage_service
import focus_trigger
import scheduler as release_scheduler


def get_bundle_dir() -> str:
    """Returns base directory for bundled assets, supporting PyInstaller onefile and dev tree."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    # In development mode, check root directory (parent of src/) then adjacent
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.exists(os.path.join(parent_dir, "static")):
        return parent_dir
    return os.path.dirname(os.path.abspath(__file__))


STATIC_DIR = os.path.join(get_bundle_dir(), "static")


class AgentRouterRequestHandler(BaseHTTPRequestHandler):
    """Handles API requests and static file serving for the widget."""
    timeout = 10  # Prevent zombie sockets on Windows

    def log_message(self, format, *args):
        """Suppress noisy request logs, print errors safely without Unicode or NoneType errors."""
        try:
            if sys.stderr and args and str(args[1]).startswith(('4', '5')):
                msg = "%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args)
                if hasattr(sys.stderr, 'buffer'):
                    sys.stderr.buffer.write(msg.encode('utf-8', errors='replace'))
                else:
                    sys.stderr.write(msg)
                sys.stderr.flush()
        except Exception:
            pass

    def _send_json(self, data: dict, status: int = 200):
        self.close_connection = True
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def do_OPTIONS(self):
        """Handle CORS pre-flight safely for local requests."""
        self.close_connection = True
        self.send_response(204)
        self.send_header("Connection", "close")
        self.end_headers()

    def _read_json_body(self) -> dict:
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if 0 < content_len <= 1024 * 1024:  # Max 1MB payload
                raw = self.rfile.read(content_len).decode("utf-8", errors="ignore")
                return json.loads(raw)
        except Exception:
            return {}
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # API Routes
        if path == "/api/status":
            gateway = router_client.check_gateway_health()
            cfg = config_manager.get_safe_config()
            schedule = time_service.format_release_info(model_id=cfg.get("selected_model"), user_offset_minutes=cfg.get("user_timezone_offset"))
            self._send_json({
                "gateway": gateway,
                "schedule": schedule,
                "config": cfg,
                "provider": provider_updates.get_snapshot(),
                "server_time": time.time()
            })
            return

        elif path == "/api/schedule":
            offset_param = query.get("offset")
            model_id = query.get("model", [None])[0]
            try:
                offset_minutes = int(offset_param[0]) if offset_param else None
                schedule = time_service.format_release_info(user_offset_minutes=offset_minutes, model_id=model_id)
            except ValueError:
                self._send_json({"error": "Invalid timezone offset"}, status=400)
                return
            self._send_json(schedule)
            return

        elif path == "/api/provider":
            snapshot = provider_updates.get_snapshot()
            snapshot["models"] = router_client.get_all_models_with_status()
            snapshot["usage"] = usage_service.get_snapshot()
            model_id = query.get("model", [None])[0]
            try:
                offset_minutes = int(query["offset"][0]) if "offset" in query else None
                snapshot["schedule"] = time_service.format_release_info(model_id=model_id, user_offset_minutes=offset_minutes)
            except ValueError:
                self._send_json({"error": "Invalid timezone offset"}, status=400)
                return
            self._send_json(snapshot)
            return

        elif path == "/api/usage":
            self._send_json(usage_service.get_snapshot())
            return

        elif path == "/api/models":
            models = router_client.get_all_models_with_status()
            self._send_json({"models": models})
            return

        elif path == "/api/config":
            self._send_json(config_manager.get_safe_config())
            return

        elif path == "/api/config/key":
            raw_key = config_manager.get_api_key()
            self._send_json({
                "has_api_key": bool(raw_key),
                "masked_api_key": config_manager.mask_key(raw_key)
            })
            return

        elif path == "/api/focus/scan":
            windows = focus_trigger.find_target_windows()
            self._send_json({
                "found": [{"hwnd": w["hwnd"], "title": w["title"], "app": w["app"]} for w in windows],
                "count": len(windows)
            })
            return

        elif path == "/api/scheduler/status":
            cfg = config_manager.load_config()
            self._send_json({
                "running": release_scheduler.is_running(),
                "enabled": cfg.get("scheduler_enabled", True),
                "press_enter": cfg.get("scheduler_press_enter", True),
                "gemini_enabled": cfg.get("gemini_enabled", False),
                "has_gemini_key": bool(cfg.get("gemini_api_key")),
                "jobs": release_scheduler.get_jobs_info(),
            })
            return

        # Static File Routes
        if path in ("/", "/index.html"):
            file_path = os.path.join(STATIC_DIR, "index.html")
        elif path in ("/favicon.ico", "/icon.ico"):
            file_path = os.path.join(STATIC_DIR, "icon.ico")
            if not os.path.isfile(file_path):
                file_path = os.path.join(STATIC_DIR, "icon.png")
        else:
            rel_path = path.lstrip("/").replace("/", os.sep)
            file_path = os.path.join(STATIC_DIR, rel_path)

        if os.path.isfile(file_path):
            ctype, _ = mimetypes.guess_type(file_path)
            if not ctype:
                ctype = "application/octet-stream"
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                self.close_connection = True
                self.send_response(200)
                self.send_header("Content-Type", f"{ctype}; charset=utf-8" if "text" in ctype or "javascript" in ctype else ctype)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error reading file: {e}")
        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/check":
            api_key = body.get("api_key")
            model_id = body.get("model_id")
            base_url = body.get("base_url")
            result = router_client.test_model_connection(api_key=api_key, model_id=model_id, base_url=base_url)
            self._send_json(result)
            return

        elif path == "/api/models/test-all":
            model_ids = body.get("models")
            api_key = body.get("api_key")
            result = router_client.batch_check_models(model_ids=model_ids, api_key=api_key)
            self._send_json(result)
            return

        elif path == "/api/models/discover":
            api_key = body.get("api_key")
            base_url = body.get("base_url")
            result = router_client.discover_models(api_key=api_key, base_url=base_url)
            usage_service.request_refresh()
            if "provider" in result:
                result["provider"]["usage"] = usage_service.get_snapshot()
            self._send_json(result)
            return

        elif path == "/api/provider/refresh":
            provider_updates.request_refresh()
            usage_service.request_refresh()
            self._send_json({"refresh_requested": True})
            return

        elif path == "/api/config":
            saved = config_manager.save_config(body)
            if "base_url" in body or "api_key" in body:
                provider_updates.request_refresh()
                usage_service.request_refresh()
            self._send_json(config_manager.get_safe_config())
            return

        elif path == "/api/config/key":
            key = body.get("api_key", "")
            action = body.get("action", "save")
            if action == "clear":
                config_manager.clear_api_key()
            else:
                config_manager.set_api_key(key)
            provider_updates.request_refresh()
            usage_service.request_refresh()
            raw_key = config_manager.get_api_key()
            self._send_json({
                "has_api_key": bool(raw_key),
                "masked_api_key": config_manager.mask_key(raw_key)
            })
            return

        elif path == "/api/focus/trigger":
            press = body.get("press_enter", True)
            cfg = config_manager.load_config()
            gemini_key = cfg.get("gemini_api_key", "").strip()
            gemini_on = cfg.get("gemini_enabled", False) and bool(gemini_key)

            ai_gate = None
            if gemini_on:
                try:
                    from gemini_helper import ai_verify_window_from_screenshot
                    ai_gate = lambda hwnd, title: ai_verify_window_from_screenshot(hwnd, title, gemini_key)
                except Exception:
                    pass

            results = focus_trigger.trigger_all_targets(press_enter=press, ai_gate_fn=ai_gate)

            if gemini_on:
                try:
                    from gemini_helper import ai_narrate_trigger
                    results["ai_message"] = ai_narrate_trigger(results, gemini_key)
                except Exception:
                    pass

            self._send_json(results)
            return

        elif path == "/api/scheduler/toggle":
            enabled = bool(body.get("enabled", True))
            config_manager.save_config({"scheduler_enabled": enabled})
            self._send_json({"scheduler_enabled": enabled})
            return

        else:
            self.send_error(404, "Endpoint Not Found")


class ProviderHTTPServer(ThreadingHTTPServer):
    def server_close(self):
        provider_updates.stop()
        usage_service.stop()
        super().server_close()


def run_server(port: int = 8765, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Starts the ThreadingHTTPServer on specified host/port with daemon threads."""
    ThreadingHTTPServer.allow_reuse_address = True
    server = ProviderHTTPServer((host, port), AgentRouterRequestHandler)
    server.daemon_threads = True
    server.block_on_close = False
    provider_updates.start()
    usage_service.start()
    print(f"[Server] Running AgentRouter monitor on http://{host}:{port}")
    return server


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = run_server(port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down.")
        server.server_close()
