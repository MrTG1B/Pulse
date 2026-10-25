"""Reported credit units, unlimited key caps, recent log scope, and privacy."""

import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import usage_service as usage


class TestUsageService(unittest.TestCase):
    def setUp(self):
        self.old_state = usage.get_snapshot()
        self.old_scope = usage._SCOPE
        self.cfg = {"api_key": "sk-test-usage", "base_url": "https://agentrouter.org"}
        self.cfg_patch = patch("config_manager.load_config", side_effect=lambda: dict(self.cfg))
        self.cfg_patch.start()
        usage._STATE = usage._empty(True)
        usage._SCOPE = ""
        self.cap = 100
        self.used = 2500
        self.logs = [{"type": 2, "model_name": "gpt-6.1-sol", "prompt_tokens": 100, "completion_tokens": 20},
                     {"type": 2, "model_name": "gpt-6.1-sol", "prompt_tokens": 50, "completion_tokens": 10}]

    def tearDown(self):
        usage.stop()
        usage._STATE = self.old_state
        usage._SCOPE = self.old_scope
        self.cfg_patch.stop()

    def fetch(self, url, **kwargs):
        mock = MagicMock(status_code=200)
        if "subscription" in url:
            mock.json.return_value = {"hard_limit_usd": self.cap}
        elif "billing/usage" in url:
            mock.json.return_value = {"total_usage": self.used}
        else:
            mock.json.return_value = {"success": True, "data": self.logs}
        return mock

    def sync(self):
        with patch("requests.get", side_effect=self.fetch), patch("requests.post") as post:
            snapshot = usage.refresh()
            post.assert_not_called()
            return snapshot

    def test_billing_usage_units_and_remaining_key_credit(self):
        snapshot = self.sync()
        self.assertEqual(snapshot["used_credit"], 25)
        self.assertEqual(snapshot["remaining_key_credit"], 75)
        self.assertFalse(snapshot["unlimited_key_cap"])
        self.assertIsNone(snapshot["account_balance"])
        self.assertIsNone(snapshot["shared_pool_remaining"])

    def test_unlimited_key_sentinel_is_not_account_balance(self):
        self.cap = 100000000
        snapshot = self.sync()
        self.assertTrue(snapshot["unlimited_key_cap"])
        self.assertIsNone(snapshot["remaining_key_credit"])
        self.assertIsNone(snapshot["total_credit_cap"])
        self.assertIsNone(snapshot["account_balance"])

    def test_recent_logs_have_explicit_partial_history_scope(self):
        snapshot = self.sync()
        model = snapshot["per_model"]["gpt-6.1-sol"]
        self.assertEqual(model["prompt_tokens"], 150)
        self.assertEqual(model["completion_tokens"], 30)
        self.assertEqual(model["total_tokens"], 180)
        self.assertEqual(model["requests"], 2)
        self.assertIn("recent", snapshot["usage_coverage"])
        self.assertIn("not lifetime", snapshot["message"])

    def test_empty_logs_do_not_claim_zero_lifetime_usage(self):
        self.logs = []
        snapshot = self.sync()
        self.assertEqual(snapshot["per_model"], {})
        self.assertIn("not reported", snapshot["message"])

    def test_error_logs_and_invalid_counters_are_not_counted(self):
        result = usage.summarize_logs([
            {"type": 5, "model_name": "m", "prompt_tokens": 20, "completion_tokens": 1},
            {"model_name": "m", "prompt_tokens": -1, "completion_tokens": 1},
            {"model_name": "m", "prompt_tokens": float("nan"), "completion_tokens": 1},
            {"model_name": "m", "prompt_tokens": True, "completion_tokens": 1}, None,
        ])
        self.assertEqual(result, {})

    def test_failures_keep_reported_values_and_mark_stale(self):
        good = self.sync()
        with patch("requests.get", side_effect=requests.Timeout("private upstream details")):
            snapshot = usage.refresh()
        self.assertEqual(snapshot["used_credit"], good["used_credit"])
        self.assertEqual(snapshot["per_model"], good["per_model"])
        self.assertTrue(snapshot["stale"])
        self.assertNotIn("private", snapshot["message"])

    def test_key_change_clears_previous_usage_before_next_request(self):
        self.sync()
        self.cfg["api_key"] = "sk-another-key"
        usage.request_refresh()
        snapshot = usage.get_snapshot()
        self.assertIsNone(snapshot["used_credit"])
        self.assertEqual(snapshot["per_model"], {})

    def test_no_key_does_not_make_network_calls(self):
        self.cfg["api_key"] = ""
        with patch("requests.get") as get:
            snapshot = usage.refresh()
            get.assert_not_called()
        self.assertEqual(snapshot["status"], "no_key")

    def test_api_payload_never_contains_credentials(self):
        snapshot = self.sync()
        self.assertNotIn(self.cfg["api_key"], str(snapshot))
        self.assertNotIn("Authorization", str(snapshot))

    def test_background_refresh_is_independent_and_stops(self):
        ready = threading.Event()
        with patch.object(usage, "refresh", side_effect=lambda **kwargs: ready.set()):
            usage.start(interval_seconds=60)
            self.assertTrue(ready.wait(2))
            usage.stop()
            self.assertFalse(usage._THREAD.is_alive())


if __name__ == "__main__":
    unittest.main()
