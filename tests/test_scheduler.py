"""
Tests for scheduler module.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure src/ is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import scheduler


class TestScheduler(unittest.TestCase):

    def setUp(self):
        scheduler.stop()

    def tearDown(self):
        scheduler.stop()

    def test_scheduler_lifecycle(self):
        self.assertFalse(scheduler.is_running())
        scheduler.start()
        self.assertTrue(scheduler.is_running())
        jobs = scheduler.get_jobs_info()
        self.assertEqual(len(jobs), 0)
        scheduler.stop()
        self.assertFalse(scheduler.is_running())

    def test_on_release_skipped_when_disabled(self):
        with patch('config_manager.load_config', return_value={"scheduler_enabled": False}), \
             patch('focus_trigger.trigger_all_targets') as mock_trigger:
            scheduler._on_release()
            mock_trigger.assert_not_called()

    def test_on_release_runs_when_enabled(self):
        with patch('config_manager.load_config', return_value={
                "scheduler_enabled": True,
                "scheduler_press_enter": True,
                "gemini_enabled": False,
                "gemini_api_key": ""
            }), \
            patch('provider_updates.get_model', return_value={"provider_status": "limited", "release_minutes_utc": [420]}), \
            patch('focus_trigger.trigger_all_targets', return_value={"message": "ok"}) as mock_trigger:
            scheduler._on_release()
            mock_trigger.assert_called_once()

    def test_jobs_follow_changed_provider_schedule(self):
        with patch('provider_updates.get_model', return_value={"provider_status": "limited", "release_minutes_utc": [420, 1140]}):
            scheduler.start()
        self.assertEqual({j['id'] for j in scheduler.get_jobs_info()}, {'release_0700', 'release_1900'})
        with patch('provider_updates.get_model', return_value={"provider_status": "unlimited", "release_minutes_utc": []}):
            scheduler.refresh_jobs()
        self.assertEqual(scheduler.get_jobs_info(), [])
        with patch('provider_updates.get_model', return_value={"provider_status": "limited", "release_minutes_utc": [105]}):
            scheduler.refresh_jobs()
        self.assertEqual([j['id'] for j in scheduler.get_jobs_info()], ['release_0145'])

    def test_obsolete_release_never_triggers_enter(self):
        with patch('provider_updates.get_model', return_value={"provider_status": "unlimited", "release_minutes_utc": []}), \
             patch('focus_trigger.trigger_all_targets') as trigger:
            scheduler._on_release(420)
            trigger.assert_not_called()
        with patch('provider_updates.get_model', return_value={"provider_status": "limited", "release_minutes_utc": [105]}), \
             patch('focus_trigger.trigger_all_targets') as trigger:
            scheduler._on_release(420)
            trigger.assert_not_called()


if __name__ == '__main__':
    unittest.main()
