"""
Integration tests for server.py.
Verifies HTTP serving of static files and REST API endpoints.
"""

import unittest
import threading
import time
import requests
import json

import server
import app


import tempfile
import os
import config_manager


class TestServerEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.test_cfg_path = os.path.join(cls.tmp_dir.name, "config.json")
        cls.original_config_file = config_manager.CONFIG_FILE
        config_manager.CONFIG_FILE = cls.test_cfg_path

        cls.port = app.find_free_port(9870)
        cls.httpd = server.run_server(port=cls.port)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        config_manager.CONFIG_FILE = cls.original_config_file
        cls.tmp_dir.cleanup()
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_serve_index_html(self):
        resp = requests.get(f"{self.base_url}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("AgentRouter", resp.text)
        self.assertIn("NEXT QUOTA RELEASE", resp.text)

    def test_serve_style_css(self):
        resp = requests.get(f"{self.base_url}/style.css")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("widget-container", resp.text)
        
        # Verify exact user-specified color palette in served CSS
        required_colors = [
            "#0A0A0A",  # Background
            "#111111",  # Surface
            "#171717",  # Elevated
            "#242424",  # Border
            "#F5F5F5",  # Primary
            "#8A8A8A",  # Secondary
            "#B8FF3D",  # Accent / Lime (Available)
            "#1D2910",  # Accent subtle
            "#FFB84D",  # Amber (Scheduled / waiting)
            "#FF4D4D",  # Red (Exhausted / error)
            "#666666",  # Gray (Offline / unknown)
        ]
        for color in required_colors:
            self.assertIn(color, resp.text, f"Required theme color {color} missing from style.css")

    def test_serve_widget_js(self):
        resp = requests.get(f"{self.base_url}/widget.js")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("tickCountdown", resp.text)

    def test_api_status_endpoint(self):
        resp = requests.get(f"{self.base_url}/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("gateway", data)
        self.assertIn("schedule", data)
        self.assertIn("config", data)

    def test_api_schedule_endpoint_ist(self):
        resp = requests.get(f"{self.base_url}/api/schedule?offset=330")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("07:30 AM & 04:30 PM", data["daily_schedule_local"])
        self.assertIn("countdown_formatted", data)
        self.assertIn("seconds_remaining", data)

    def test_api_models_endpoint(self):
        resp = requests.get(f"{self.base_url}/api/models")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("models", data)
        self.assertGreater(len(data["models"]), 5)

    def test_api_config_key_save_and_clear(self):
        # Save key
        resp = requests.post(f"{self.base_url}/api/config/key", json={
            "api_key": "sk-endpoint-test-12345",
            "action": "save"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["has_api_key"])
        self.assertIn("••••••••", data["masked_api_key"])

        # Clear key
        resp_clear = requests.post(f"{self.base_url}/api/config/key", json={
            "action": "clear"
        })
        self.assertEqual(resp_clear.status_code, 200)
        data_clear = resp_clear.json()
        self.assertFalse(data_clear["has_api_key"])

    def test_api_config_key_get_endpoint(self):
        # Save key first
        requests.post(f"{self.base_url}/api/config/key", json={
            "api_key": "sk-reveal-test-key-5555",
            "action": "save"
        })
        # Fetch raw key via GET
        resp = requests.get(f"{self.base_url}/api/config/key")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["has_api_key"])
        self.assertEqual(data["api_key"], "sk-reveal-test-key-5555")
        self.assertIn("••••••••", data["masked_api_key"])

        # Clean up
        requests.post(f"{self.base_url}/api/config/key", json={"action": "clear"})

    def test_api_models_discover_endpoint(self):
        resp = requests.post(f"{self.base_url}/api/models/discover", json={
            "api_key": "sk-test-fake"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("success", data)
        self.assertIn("models", data)


if __name__ == "__main__":
    unittest.main()
