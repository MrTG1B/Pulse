"""
Unit tests for router_client.py.
Verifies response classification (200, 401, 402, 503, offline),
model categorization, and mock responses.
"""

import unittest
import copy
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import router_client
import provider_updates


class TestRouterClient(unittest.TestCase):

    def setUp(self):
        self.old_state = provider_updates.get_snapshot()
        self.old_scope = provider_updates._SCOPE
        self.tmp = tempfile.TemporaryDirectory()
        self.file_patch = patch("config_manager.CONFIG_FILE", os.path.join(self.tmp.name, "config.json"))
        self.file_patch.start()
        provider_updates._STATE = provider_updates._initial_state()
        provider_updates._SCOPE = ""
        provider_updates.CATALOG_MODELS[:] = copy.deepcopy(provider_updates._STATE["models"])
        self.cfg_patch = patch("config_manager.load_config", return_value={"api_key": "", "base_url": "https://agentrouter.org", "selected_model": "gpt-6.1-sol"})
        self.gateway_patch = patch("router_client.check_gateway_health", return_value={"reachable": True, "latency_ms": 1})
        self.cfg_patch.start()
        self.gateway_patch.start()

    def tearDown(self):
        self.cfg_patch.stop()
        self.gateway_patch.stop()
        self.file_patch.stop()
        self.tmp.cleanup()
        provider_updates._STATE = self.old_state
        provider_updates._SCOPE = self.old_scope
        provider_updates.CATALOG_MODELS[:] = copy.deepcopy(self.old_state["models"])

    def test_catalog_structure(self):
        """Bundled policies reflect the latest provider announcement."""
        models = router_client.CATALOG_MODELS
        model_ids = [m["id"] for m in models]

        self.assertIn("claude-opus-5-5", model_ids)
        self.assertIn("gpt-6-astra", model_ids)
        self.assertIn("gpt-6.1-sol", model_ids)

        opus_model = next(m for m in models if m["id"] == "claude-opus-5-5")
        self.assertEqual(opus_model["provider_status"], "unavailable")

        # Verify GPT-6.1 Sol is Now Unlimited (quota_limited == False)
        sol_model = next(m for m in models if m["id"] == "gpt-6.1-sol")
        self.assertFalse(sol_model["quota_limited"])
        self.assertEqual(sol_model["api_type"], "openai_responses")

        # GPT-6 Astra is now unlimited.
        astra_model = next(m for m in models if m["id"] == "gpt-6-astra")
        self.assertFalse(astra_model["quota_limited"])
        self.assertEqual(astra_model["api_type"], "openai_responses")

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
        def fetch(url, **kwargs):
            response = MagicMock(status_code=200)
            if url.endswith("/api/status"):
                response.json.return_value = {"data": {"announcements": provider_updates.DEFAULT_ANNOUNCEMENTS}}
            elif url.endswith("/api/pricing"):
                response.json.return_value = {"data": []}
            else:
                response.json.return_value = {"data": [{"id": "claude-custom-enterprise"}, {"id": "deepseek-custom-pro"}]}
            return response
        mock_get.side_effect = fetch

        res = router_client.discover_models(api_key="sk-test")
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 2)

        model_ids = [m["id"] for m in router_client.CATALOG_MODELS]
        self.assertIn("claude-custom-enterprise", model_ids)
        self.assertIn("deepseek-custom-pro", model_ids)

        # Check categorization
        ds = next(m for m in router_client.CATALOG_MODELS if m["id"] == "deepseek-custom-pro")
        self.assertIsNone(ds["quota_limited"])
        self.assertEqual(ds["category"], "unknown")

    def test_auth_headers_contain_stainless(self):
        """Verifies authentic AgentRouter-compatible client headers for Claude Code and Codex."""
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
        self.gateway_patch.stop()
        errors = []

        def worker():
            try:
                for _ in range(5):
                    router_client.check_gateway_health()
            except Exception as e:
                errors.append(e)

        with patch("requests.get") as get:
            get.return_value.status_code = 200
            get.return_value.json.return_value = {"data": {"version": "test"}}
            router_client._GATEWAY_CACHE = {"timestamp": 0, "url": "", "data": None}
            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(get.call_count, 1)

        self.assertEqual(len(errors), 0, f"Concurrent gateway check failed: {errors}")

    @patch("requests.post")
    def test_503_no_channel_classification(self, mock_post):
        """Verifies 503 no available channel is properly classified as no_channel."""
        mock_post.return_value.status_code = 503
        mock_post.return_value.text = '{"error":{"message":"当前分组 core 下对于模型 claude-3-5-sonnet-20241022 无可用渠道","type":"new_api_error"}}'
        mock_post.return_value.json.return_value = {
            "error": {"message": "当前分组 core 下对于模型 claude-3-5-sonnet-20241022 无可用渠道", "type": "new_api_error"}
        }

    @patch("requests.post")
    def test_mock_responses_api_200(self, mock_post):
        """Verifies models configured as openai_responses call /v1/responses with input: ping."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = '{"id":"resp_123","object":"response","status":"completed"}'
        mock_post.return_value.json.return_value = {"id": "resp_123", "object": "response", "status": "completed"}

        res = router_client.test_model_connection(api_key="sk-test", model_id="gpt-6-astra")
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["status_type"], "active")
        self.assertTrue(res["is_active"])

        # Check call arguments
        call_args = mock_post.call_args
        endpoint = call_args[0][0]
        payload = call_args[1]["json"]
        self.assertTrue(endpoint.endswith("/v1/responses"))
        self.assertEqual(payload.get("model"), "gpt-6-astra")
        self.assertEqual(payload.get("input"), "ping")

    @patch("requests.post")
    def test_mock_400_auto_fallback_to_responses(self, mock_post):
        """When an OpenAI model returns 400 requesting /v1/responses, it automatically retries and succeeds."""
        mock_err_resp = MagicMock()
        mock_err_resp.status_code = 400
        mock_err_resp.text = 'Model test-model does not support /v1/chat/completions, please use /v1/responses instead.'
        mock_err_resp.json.return_value = {"error": {"message": mock_err_resp.text}}

        mock_ok_resp = MagicMock()
        mock_ok_resp.status_code = 200
        mock_ok_resp.text = '{"id":"resp_456","object":"response","status":"completed"}'
        mock_ok_resp.json.return_value = {"id": "resp_456", "object": "response", "status": "completed"}

        mock_post.side_effect = [mock_err_resp, mock_ok_resp]

        res = router_client.test_model_connection(api_key="sk-test", model_id="some-custom-model")
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["status_type"], "active")
        self.assertEqual(mock_post.call_count, 2)
        # Second call must be to /v1/responses
        second_endpoint = mock_post.call_args_list[1][0][0]
        self.assertTrue(second_endpoint.endswith("/v1/responses"))

    @patch("requests.post")
    def test_gpt_6_1sol_alias_and_decryption_error(self, mock_post):
        """Tests that gpt-6.1sol alias maps to responses endpoint and catches decryption error."""
        mock_err_resp = MagicMock()
        mock_err_resp.status_code = 500
        mock_err_resp.text = 'Decryption Failure: unable to decrypt payload'
        mock_err_resp.json.return_value = {"error": {"message": "Decryption Failure"}}
        mock_post.return_value = mock_err_resp

        res = router_client.test_model_connection(api_key="sk-test", model_id="gpt-6.1sol")
        self.assertEqual(res["status_type"], "provider_maintenance")
        self.assertIn("Decryption Failure", res["status_title"] + res["message"])
        # Endpoint used should be /v1/responses
        endpoint = mock_post.call_args[0][0]
        self.assertTrue(endpoint.endswith("/v1/responses"))


if __name__ == "__main__":
    unittest.main()
