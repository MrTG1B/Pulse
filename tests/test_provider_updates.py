"""Provider contracts, policy precedence, persistence, and background refresh."""

import copy
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import provider_updates as updates
import router_client


LATEST = updates.DEFAULT_ANNOUNCEMENTS[0]
OLDER = {
    "id": 18, "publishDate": "2026-10-19T03:35:20.513Z",
    "content": "claude-opus-5-5 is supplied in limited quantities. Quotas are released daily at 09:00 Beijing Time (UTC+8) / 01:00 UTC.",
}


def response(data, status=200):
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = data
    return mock


class TestAnnouncementPolicies(unittest.TestCase):
    def models(self, *ids):
        return [updates._make_model(mid) for mid in ids]

    def test_current_bilingual_notice_overrides_old_schedule(self):
        models = updates.apply_announcements(self.models("claude-opus-5-5", "gpt-6-astra", "gpt-6.1-sol"), [OLDER, LATEST])
        opus, astra, sol = models
        self.assertEqual(opus["provider_status"], "unavailable")
        self.assertEqual(opus["release_minutes_utc"], [])
        self.assertFalse(astra["quota_limited"])
        self.assertEqual(astra["release_minutes_utc"], [])
        self.assertFalse(sol["quota_limited"])
        self.assertTrue(sol["recommended"])
        self.assertTrue(sol["low_multiplier"])

    def test_newest_date_wins_over_input_order_and_id(self):
        old = {"id": 999, "publishDate": "2026-10-01T00:00:00Z", "content": "gpt-6-astra is limited. Release times: 07:00 / 19:00 UTC."}
        astra = updates.apply_announcements(self.models("gpt-6-astra"), [old, LATEST])[0]
        self.assertEqual(astra["provider_status"], "unlimited")
        self.assertEqual(updates.normalize_announcements([old, LATEST])[0]["id"], 19)

    def test_unknown_model_does_not_inherit_quota_by_provider_name(self):
        model = updates.apply_announcements(self.models("gpt-future", "deepseek-future"), [LATEST])
        self.assertTrue(all(m["quota_limited"] is None for m in model))
        self.assertTrue(all(m["provider_status"] == "unknown" for m in model))

    def test_future_policy_changes_clear_unlimited_recommendation(self):
        future = {"id": 20, "publishDate": "2026-10-26T00:00:00Z", "content": "gpt-6.1-sol is now limited. Release times: 01:45 / 13:15 UTC."}
        model = updates.apply_announcements(self.models("gpt-6.1-sol"), [LATEST, future])[0]
        self.assertTrue(model["quota_limited"])
        self.assertFalse(model["recommended"])
        self.assertEqual(model["release_minutes_utc"], [105, 795])

    def test_restore_does_not_reuse_old_release_schedule(self):
        future = {"id": 20, "publishDate": "2026-10-26T00:00:00Z", "content": "claude-opus-5.5 is back online. Supply restored."}
        model = updates.apply_announcements(self.models("claude-opus-5-5"), [OLDER, LATEST, future])[0]
        self.assertEqual(model["provider_status"], "available")
        self.assertIsNone(model["quota_limited"])
        self.assertEqual(model["release_minutes_utc"], [])

    def test_compact_chinese_and_multiple_models_do_not_bleed_policies(self):
        notice = {"id": 20, "content": "gpt-6-astra取消限量，全天候供应。claude-opus-5.5暂时下线。gpt-6.1sol不限量低倍率供应，建议优先使用。"}
        astra, opus, sol = updates.apply_announcements(self.models("gpt-6-astra", "claude-opus-5-5", "gpt-6.1-sol"), [notice])
        self.assertFalse(astra["quota_limited"])
        self.assertEqual(opus["provider_status"], "unavailable")
        self.assertTrue(sol["recommended"])

    def test_explicit_timezones_and_minute_slots(self):
        cases = {
            "03:00 / 15:00 Beijing Time (19:00 / 07:00 UTC)": [420, 1140],
            "daily at 09:00 Beijing Time (UTC+8) / 01:00 UTC": [60],
            "北京时间 3:00 / 15:00": [420, 1140],
            "UTC 01:45 / 13:15": [105, 795],
            "24:00 UTC": [], "12:99 UTC": [], "Time to be announced": [],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(updates.parse_release_minutes(text), expected)

    def test_malformed_announcements_are_ignored(self):
        self.assertEqual(updates.normalize_announcements(None), [])
        result = updates.normalize_announcements([None, {}, {"content": 3}, {"content": " "}, LATEST])
        self.assertEqual(len(result), 1)


class TestProviderSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_state = updates.get_snapshot()
        self.old_scope = updates._SCOPE
        self.config = {"base_url": "https://agentrouter.org", "api_key": "sk-provider-test", "selected_model": "gpt-6.1-sol"}
        self.file_patch = patch("config_manager.CONFIG_FILE", os.path.join(self.tmp.name, "config.json"))
        self.cfg_patch = patch("config_manager.load_config", side_effect=lambda: dict(self.config))
        self.file_patch.start()
        self.cfg_patch.start()
        with updates._LOCK:
            updates._SCOPE = ""
            updates._STATE = updates._initial_state()
            updates.CATALOG_MODELS[:] = copy.deepcopy(updates._STATE["models"])
        self.account_ids = ["gpt-5.6-sol", "gpt-6-astra", "gpt-6.1-sol"]
        self.announcements = [OLDER, LATEST]
        self.calls = []

    def tearDown(self):
        updates.stop()
        with updates._LOCK:
            updates._STATE = self.old_state
            updates._SCOPE = self.old_scope
            updates.CATALOG_MODELS[:] = copy.deepcopy(self.old_state["models"])
        self.cfg_patch.stop()
        self.file_patch.stop()
        self.tmp.cleanup()

    def fetch(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/api/status"):
            return response({"success": True, "data": {"announcements": self.announcements}})
        if url.endswith("/api/pricing"):
            return response({"success": True, "data": [{"model_name": mid, "model_ratio": 0.5 if mid == "gpt-6.1-sol" else 1} for mid in self.account_ids]})
        if url.endswith("/v1/models"):
            return response({"data": [{"id": mid} for mid in self.account_ids]})
        if url.endswith("/api/notice"):
            return response({"success": True, "data": "gpt-6-astra is still limited. 07:00 / 19:00 UTC."})
        raise AssertionError(url)

    def sync(self):
        with patch("requests.get", side_effect=self.fetch), patch("requests.post") as post:
            snapshot = updates.refresh()
            post.assert_not_called()
            return snapshot

    def test_live_account_catalog_and_dated_notices(self):
        snapshot = self.sync()
        self.assertFalse(snapshot["models_stale"])
        self.assertFalse(snapshot["notices_stale"])
        self.assertEqual(snapshot["notice_source"], "status")
        self.assertEqual(snapshot["model_source"], "account")
        self.assertEqual(snapshot["recommended_model"], "gpt-6.1-sol")
        self.assertEqual(updates.get_model("gpt-6.1sol")["multiplier"], 0.5)
        self.assertEqual(updates.get_model("claude-opus-5.5")["provider_status"], "unavailable")
        self.assertFalse(updates.get_model("claude-opus-5.5")["available_in_account"])
        self.assertFalse(any(url.endswith("/api/notice") for url, _ in self.calls))
        for url, kwargs in self.calls:
            if "/api/" in url:
                self.assertNotIn("Authorization", kwargs.get("headers", {}))

    def test_models_added_and_removed_on_later_refresh(self):
        self.sync()
        self.account_ids = ["gpt-6.1-sol", "brand-new-model"]
        self.sync()
        self.assertIsNone(updates.get_model("gpt-5.6-sol"))
        self.assertIsNone(updates.get_model("gpt-6-astra"))
        self.assertIsNotNone(updates.get_model("brand-new-model"))
        self.assertIsNotNone(updates.get_model("claude-opus-5-5"))

    def test_failure_keeps_last_successful_data(self):
        good = self.sync()
        with patch("requests.get", side_effect=requests.Timeout("contains-sensitive-response-text")):
            stale = updates.refresh()
        self.assertEqual(stale["models"], good["models"])
        self.assertEqual(stale["announcements"], good["announcements"])
        self.assertEqual(stale["models_updated_at"], good["models_updated_at"])
        self.assertTrue(stale["models_stale"])
        self.assertTrue(stale["notices_stale"])
        self.assertNotIn("sensitive", stale["error"])

    def test_cache_survives_restart_and_never_contains_key(self):
        good = self.sync()
        with open(updates._cache_path(), encoding="utf-8") as handle:
            cache_text = handle.read()
        self.assertNotIn(self.config["api_key"], cache_text)
        self.assertNotIn("Authorization", cache_text)
        updates._SCOPE = ""
        updates._ensure_scope(self.config["base_url"], self.config["api_key"])
        cached = updates.get_snapshot()
        self.assertEqual(cached["models"], good["models"])
        self.assertTrue(cached["models_stale"])

    def test_key_change_does_not_reuse_another_accounts_models(self):
        self.account_ids = ["private-account-model"]
        self.sync()
        self.config["api_key"] = "sk-different-account"
        with patch("requests.get", side_effect=requests.Timeout()):
            stale = updates.refresh()
        self.assertNotIn("private-account-model", [m["id"] for m in stale["models"]])

    def test_key_change_during_refresh_discards_old_response(self):
        self.account_ids = ["private-account-model"]
        started, release = threading.Event(), threading.Event()
        def blocked(url, **kwargs):
            if url.endswith('/api/status'):
                started.set()
                release.wait(3)
            return self.fetch(url, **kwargs)
        with patch('requests.get', side_effect=blocked):
            thread = threading.Thread(target=updates.refresh)
            thread.start()
            try:
                self.assertTrue(started.wait(2))
                self.config['api_key'] = 'sk-new-account'
                updates.request_refresh()
                release.set()
                thread.join(3)
                self.assertNotIn('private-account-model', [m['id'] for m in updates.get_snapshot()['models']])
            finally:
                release.set()
                thread.join(3)

    def test_no_key_uses_public_catalog_without_authenticated_request(self):
        self.config["api_key"] = ""
        snapshot = self.sync()
        self.assertEqual(snapshot["model_source"], "pricing")
        self.assertFalse(snapshot["models_stale"])
        self.assertFalse(any(url.endswith("/v1/models") for url, _ in self.calls))

    def test_notice_endpoint_is_fallback_when_announcements_are_absent(self):
        self.announcements = []
        snapshot = self.sync()
        self.assertEqual(snapshot["notice_source"], "notice")
        self.assertTrue(updates.get_model("gpt-6-astra")["quota_limited"])
        self.assertEqual(updates.get_model("gpt-6-astra")["release_minutes_utc"], [420, 1140])

    def test_malformed_account_list_does_not_remove_good_models(self):
        good = self.sync()
        def malformed(url, **kwargs):
            return response({"data": [None, {}]}) if url.endswith("/v1/models") else self.fetch(url, **kwargs)
        with patch("requests.get", side_effect=malformed):
            snapshot = updates.refresh()
        self.assertEqual([m["id"] for m in snapshot["models"]], [m["id"] for m in good["models"]])
        self.assertTrue(snapshot["models_stale"])

    def test_malformed_announcements_do_not_replace_dated_notice_with_old_text(self):
        good = self.sync()
        def malformed(url, **kwargs):
            return response({'data': {'announcements': {}}}) if url.endswith('/api/status') else self.fetch(url, **kwargs)
        with patch('requests.get', side_effect=malformed):
            snapshot = updates.refresh()
        self.assertEqual(snapshot['announcements'], good['announcements'])
        self.assertTrue(snapshot['notices_stale'])
        self.assertFalse(updates.get_model('gpt-6-astra')['quota_limited'])

    def test_failed_pricing_preserves_multiplier_and_marks_it_stale(self):
        self.sync()
        def bad_pricing(url, **kwargs):
            return response({'data': [None, {}]}) if url.endswith('/api/pricing') else self.fetch(url, **kwargs)
        with patch('requests.get', side_effect=bad_pricing):
            snapshot = updates.refresh()
        self.assertEqual(updates.get_model('gpt-6.1-sol')['multiplier'], 0.5)
        self.assertTrue(snapshot['pricing_stale'])

    def test_empty_account_catalog_removes_all_selectable_models(self):
        self.sync()
        self.account_ids = []
        snapshot = self.sync()
        self.assertEqual(snapshot["recommended_model"], None)
        self.assertTrue(all(m["provider_status"] == "unavailable" for m in snapshot["models"]))
        self.assertFalse(snapshot["models_stale"])

    def test_overlapping_refresh_does_not_block_cached_reads_or_duplicate_fetches(self):
        self.sync()
        started = threading.Event()
        release = threading.Event()
        def blocked(url, **kwargs):
            if url.endswith("/api/status"):
                started.set()
                release.wait(3)
            return self.fetch(url, **kwargs)
        with patch("requests.get", side_effect=blocked) as get:
            thread = threading.Thread(target=updates.refresh)
            thread.start()
            try:
                self.assertTrue(started.wait(2))
                before = time.monotonic()
                snapshot = updates.refresh()
                self.assertLess(time.monotonic() - before, 0.2)
                self.assertTrue(snapshot["refreshing"])
                self.assertLessEqual(get.call_count, 3)
            finally:
                release.set()
                thread.join(3)
            self.assertFalse(thread.is_alive())

    def test_background_refresh_repeats_and_stops(self):
        twice = threading.Event()
        calls = []
        def sync_stub(**kwargs):
            calls.append(time.monotonic())
            if len(calls) >= 2:
                twice.set()
        with patch.object(updates, "refresh", side_effect=sync_stub):
            updates.start(interval_seconds=0.02)
            self.assertTrue(twice.wait(2))
            updates.stop()
            self.assertFalse(updates._THREAD.is_alive())

    def test_wakeup_refreshes_before_regular_interval(self):
        first, second = threading.Event(), threading.Event()
        calls = []
        def sync_stub(**kwargs):
            calls.append(1)
            (first if len(calls) == 1 else second).set()
        with patch.object(updates, "refresh", side_effect=sync_stub):
            updates.start(interval_seconds=60)
            self.assertTrue(first.wait(2))
            updates.request_refresh()
            self.assertTrue(second.wait(2))
            updates.stop()

    def test_suspended_alias_never_sends_model_probe(self):
        self.sync()
        with patch("requests.post") as post, patch("requests.get") as get:
            result = router_client.test_model_connection(api_key="sk-provider-test", model_id="claude-opus-5.5")
            self.assertEqual(result["model_id"], "claude-opus-5-5")
            self.assertEqual(result["status_type"], "unavailable")
            post.assert_not_called()
            get.assert_not_called()

    def test_old_success_cannot_override_new_suspension(self):
        self.sync()
        with patch.dict(router_client.MODEL_STATUS_CACHE, {"claude-opus-5-5": {"status_type": "active", "status_code": 200, "timestamp": time.time() + 10}}):
            model = next(m for m in router_client.get_all_models_with_status() if m["id"] == "claude-opus-5-5")
        self.assertEqual(model["status_type"], "unavailable")

    def test_old_key_success_is_not_used_for_new_key(self):
        self.sync()
        with patch('requests.post') as post:
            post.return_value.status_code = 200
            post.return_value.text = '{}'
            post.return_value.json.return_value = {}
            router_client.test_model_connection(api_key=self.config['api_key'], model_id='gpt-6.1-sol')
        checked = next(m for m in router_client.get_all_models_with_status() if m['id'] == 'gpt-6.1-sol')
        self.assertEqual(checked['status_type'], 'active')
        self.config['api_key'] = 'sk-new-key'
        self.sync()
        checked = next(m for m in router_client.get_all_models_with_status() if m['id'] == 'gpt-6.1-sol')
        self.assertEqual(checked['status_type'], 'unchecked')


if __name__ == "__main__":
    unittest.main()
