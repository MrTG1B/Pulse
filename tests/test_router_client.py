"""
Unit tests for router_client.py.
Verifies response classification (200, 401, 402, 503, offline),
model categorization, and mock responses.
"""

import unittest
import os
import sys
from unittest.mock import patch, MagicMock
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import router_client


class TestRouterClient(unittest.TestCase):

    def test_catalog_structure(self):
        """Verifies presence of Claude, GPT, and Uninterrupted models."""
        models = router_client.CATALOG_MODELS
        model_ids = [m["id"] for m in models]

        # Claude models
        self.assertIn("claude-opus-4-8", model_ids)
        self.assertIn("claude-opus-5", model_ids)

        # GPT models
        self.assertIn("gpt-6-astra", model_ids)

        # Uninterrupted models (DeepSeek)
        self.assertIn("deepseek-v4-flash", model_ids)

        # Verify uninterrupted models have quota_limited == False
        ds_model = next(m for m in models if m["id"] == "deepseek-v4-flash")
        self.assertFalse(ds_model["quota_limited"])

        claude_model = next(m for m in models if m["id"] == "claude-opus-4-8")
        self.assertTrue(claude_model["quota_limited"])

    def test_test_connection_no_key(self):
        """When no key is configured, returns no_key status."""
        with patch("config_manager.load_config", return_value={"api_key": ""}):
            res = router_client.test_model_connection(api_key="")
            self.assertEqual(res["status_type"], "no_key")
            self.assertEqual(res["status_code"], 0)
            self.assertIn("API Key", res["status_title"])

    @patch("requests.get")
    @patch("requests.post")
    def test_mock_200_active(self, mock_post, mock_get):
        """HTTP 200 should return status_type active."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": {"version": "1.0"}}

        mock_post.return_value.status_code = 200
        mock_post.return_value.text = '{"content": [{"text": "hello"}]}'
        mock_post.return_value.json.return_value = {"content": [{"text": "hello"}]}

        res = router_client.test_model_connection(api_key="sk-test", model_id="claude-3-5-sonnet-20241022")
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["status_type"], "active")
        self.assertTrue(res["is_active"])
        self.assertFalse(res["is_quota_exhausted"])

    @patch("requests.get")
    @patch("requests.post")
    def test_mock_402_quota_exhausted(self, mock_post, mock_get):
        """HTTP 402 with budget pool message must classify as quota_exhausted."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": {"version": "1.0"}}

        mock_post.return_value.status_code = 402
        mock_post.return_value.text = '{"error":{"message":"Budget pool quota has been exhausted."}}'
        mock_post.return_value.json.return_value = {
            "error": {"message": "Budget pool quota has been exhausted."}
        }

        res = router_client.test_model_connection(api_key="sk-test", model_id="claude-3-5-sonnet-20241022")
        self.assertEqual(res["status_code"], 402)
        self.assertEqual(res["status_type"], "quota_exhausted")
        self.assertTrue(res["is_quota_exhausted"])
        self.assertFalse(res["is_active"])
        self.assertIn("quota has been exhausted", res["message"].lower())

    @patch("requests.get")
    @patch("requests.post")
    def test_mock_401_unauthorized(self, mock_post, mock_get):
        """HTTP 401 must classify as unauthorized."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": {"version": "1.0"}}

        mock_post.return_value.status_code = 401
        mock_post.return_value.text = '{"error":{"message":"unauthorized client"}}'
        mock_post.return_value.json.return_value = {
            "error": {"message": "unauthorized client"}
        }

        res = router_client.test_model_connection(api_key="sk-test", model_id="claude-3-5-sonnet-20241022")
        self.assertEqual(res["status_code"], 401)
        self.assertEqual(res["status_type"], "unauthorized")

    @patch("requests.get")
    @patch("requests.post")
    def test_mock_network_failure(self, mock_post, mock_get):
        """Network exception must classify as offline."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        res = router_client.test_model_connection(api_key="sk-test", model_id="claude-3-5-sonnet-20241022")
        self.assertEqual(res["status_code"], 0)
        self.assertEqual(res["status_type"], "offline")
    @patch("requests.get")
    @patch("requests.post")
    def test_mock_chinese_quota_exhausted(self, mock_post, mock_get):
        """Chinese error notice '额度用尽' must classify as quota_exhausted."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": {"version": "1.0"}}

        mock_post.return_value.status_code = 402
        mock_post.return_value.text = '{"error":{"message":"额度用尽后会报错 402 Budget pool quota has been exhausted"}}'
        mock_post.return_value.json.return_value = {
            "error": {"message": "额度用尽后会报错 402 Budget pool quota has been exhausted"}
        }

        res = router_client.test_model_connection(api_key="sk-test", model_id="claude-3-5-sonnet-20241022")
        self.assertEqual(res["status_code"], 402)
        self.assertEqual(res["status_type"], "quota_exhausted")
        self.assertTrue(res["is_quota_exhausted"])

    @patch("requests.get")
    def test_discover_models_merges_new_models(self, mock_get):
        """Verifies discover_models parses /v1/models response and categorizes."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "data": [
                {"id": "claude-custom-enterprise", "object": "model"},
                {"id": "deepseek-custom-pro", "object": "model"}
            ]
        }

        res = router_client.discover_models(api_key="sk-test")
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 2)

        model_ids = [m["id"] for m in router_client.CATALOG_MODELS]
        self.assertIn("claude-custom-enterprise", model_ids)
        self.assertIn("deepseek-custom-pro", model_ids)

        # Check categorization
        ds = next(m for m in router_client.CATALOG_MODELS if m["id"] == "deepseek-custom-pro")
        self.assertFalse(ds["quota_limited"])
        self.assertEqual(ds["category"], "uninterrupted")

    def test_auth_headers_contain_stainless(self):
        """Verifies authentic client headers required to bypass AgentRouter WAF."""
        headers = router_client.get_auth_headers(api_key="sk-test-12345")
        self.assertEqual(headers["User-Agent"], "claude-cli/1.0.108 (external, cli)")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(headers["Authorization"], "Bearer sk-test-12345")
        self.assertEqual(headers["x-api-key"], "sk-test-12345")

    def test_masked_key_fallback(self):
        """Passing a masked key should fall back to configured real key."""
        with patch("config_manager.get_api_key", return_value="sk-real-secret-key"):
            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.text = '{"content":[{"text":"ok"}]}'
                mock_post.return_value.json.return_value = {"content": [{"text": "ok"}]}

                router_client.test_model_connection(api_key="sk-ab••••••••cdef")
                called_headers = mock_post.call_args[1]["headers"]
                self.assertEqual(called_headers["Authorization"], "Bearer sk-real-secret-key")

    def test_gateway_cache_thread_safety(self):
        """Verifies concurrent check_gateway_health calls execute safely."""
        import threading
        errors = []

        def worker():
            try:
                for _ in range(5):
                    router_client.check_gateway_health()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent gateway check failed: {errors}")

    @patch("requests.post")
    def test_503_no_channel_classification(self, mock_post):
        """Verifies 503 no available channel is properly classified as no_channel."""
        mock_post.return_value.status_code = 503
        mock_post.return_value.text = '{"error":{"message":"当前分组 core 下对于模型 claude-3-5-sonnet-20241022 无可用渠道","type":"new_api_error"}}'
        mock_post.return_value.json.return_value = {
            "error": {"message": "当前分组 core 下对于模型 claude-3-5-sonnet-20241022 无可用渠道", "type": "new_api_error"}
        }

        res = router_client.test_model_connection(api_key="sk-test", model_id="claude-3-5-sonnet-20241022")
        self.assertEqual(res["status_code"], 503)
        self.assertEqual(res["status_type"], "no_channel")
        self.assertIn("No Channel", res["status_title"])


if __name__ == "__main__":
    unittest.main()
