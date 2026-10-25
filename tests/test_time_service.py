"""
Unit tests for time_service.py.
Verifies explicit per-model release schedule calculations and UTC+05:30 IST conversions.
"""

import unittest
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import time_service


class TestTimeService(unittest.TestCase):

    def test_utc_0700_release_slot(self):
        """When current time is 05:00 UTC, next release must be 07:00 UTC (Batch 1 / 15:00 Beijing)."""
        mock_now = datetime(2026, 10, 3, 5, 0, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now, release_minutes_utc=(420, 1140))

        self.assertEqual(res["batch_number"], 1)
        self.assertEqual(res["next_slot_utc"], "2026-10-03T07:00:00+00:00")
        self.assertEqual(res["seconds_remaining"], 2 * 3600)
        self.assertEqual(res["hours_remaining"], 2)
        self.assertEqual(res["minutes_remaining"], 0)
        self.assertEqual(res["seconds_part"], 0)

    def test_utc_1900_release_slot(self):
        """When current time is 08:00 UTC, next release must be 19:00 UTC (Batch 2 / 03:00 Beijing)."""
        mock_now = datetime(2026, 10, 3, 8, 0, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now, release_minutes_utc=(420, 1140))

        self.assertEqual(res["batch_number"], 2)
        self.assertEqual(res["next_slot_utc"], "2026-10-03T19:00:00+00:00")
        self.assertEqual(res["seconds_remaining"], 11 * 3600)
        self.assertEqual(res["hours_remaining"], 11)

    def test_day_rollover_slot(self):
        """When current time is 20:00 UTC, next release must be tomorrow 07:00 UTC (Batch 1)."""
        mock_now = datetime(2026, 10, 3, 20, 0, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now, release_minutes_utc=(420, 1140))

        self.assertEqual(res["batch_number"], 1)
        self.assertEqual(res["next_slot_utc"], "2026-10-04T07:00:00+00:00")
        self.assertEqual(res["seconds_remaining"], 11 * 3600)
        self.assertEqual(res["hours_remaining"], 11)

    def test_exact_release_time_moves_to_next(self):
        """At exactly 07:00:00 UTC, the next future release must be 19:00:00 UTC."""
        mock_now = datetime(2026, 10, 3, 7, 0, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now, release_minutes_utc=(420, 1140))

        self.assertEqual(res["batch_number"], 2)
        self.assertEqual(res["next_slot_utc"], "2026-10-03T19:00:00+00:00")

    def test_user_local_timezone_ist_conversion(self):
        """
        User's timezone is UTC+05:30 (India Standard Time).
        - 07:00 UTC must format to 12:30 PM IST (Afternoon Release).
        - 19:00 UTC must format to 12:30 AM IST (Night Release).
        """
        # Test Afternoon Drop (07:00 UTC -> 12:30 PM IST)
        mock_now_afternoon = datetime(2026, 10, 3, 5, 0, 0, tzinfo=timezone.utc)
        info_afternoon = time_service.format_release_info(now_utc=mock_now_afternoon, user_offset_minutes=330, release_minutes_utc=(420, 1140))

        self.assertIn("12:30 PM", info_afternoon["local_time"])
        self.assertEqual(info_afternoon["user_timezone"], "UTC+05:30")
        self.assertIn("12:30 PM & 12:30 AM", info_afternoon["daily_schedule_local"])

        # Test Night Drop (19:00 UTC -> 12:30 AM IST)
        mock_now_night = datetime(2026, 10, 3, 10, 0, 0, tzinfo=timezone.utc)
        info_night = time_service.format_release_info(now_utc=mock_now_night, user_offset_minutes=330, release_minutes_utc=(420, 1140))
        self.assertIn("12:30 AM", info_night["local_time"])

    def test_beijing_reference_time(self):
        """Beijing time must format to 15:00 CST (for 07:00 UTC) and 03:00 CST (for 19:00 UTC)."""
        mock_now = datetime(2026, 10, 3, 5, 0, 0, tzinfo=timezone.utc)
        info = time_service.format_release_info(now_utc=mock_now, release_minutes_utc=(420, 1140))
        self.assertIn("15:00", info["beijing_time"])

        mock_now2 = datetime(2026, 10, 3, 10, 0, 0, tzinfo=timezone.utc)
        info2 = time_service.format_release_info(now_utc=mock_now2, release_minutes_utc=(420, 1140))
        self.assertIn("03:00", info2["beijing_time"])

    def test_cycle_progress_percentage(self):
        """Cycle progress must be between 0% and 100%."""
        mock_now = datetime(2026, 10, 3, 6, 30, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now, release_minutes_utc=(420, 1140))
        self.assertGreaterEqual(res["cycle_progress_percent"], 0.0)
        self.assertLessEqual(res["cycle_progress_percent"], 100.0)

    def test_negative_timezone_offsets(self):
        """Verifies get_timezone_from_offset correctly formats negative offsets."""
        tz_ny = time_service.get_timezone_from_offset(-300)
        self.assertEqual(tz_ny.tzname(None), "UTC-05:00")

        tz_nst = time_service.get_timezone_from_offset(-210)
        self.assertEqual(tz_nst.tzname(None), "UTC-03:30")

        tz_half = time_service.get_timezone_from_offset(-330)
        self.assertEqual(tz_half.tzname(None), "UTC-05:30")

        tz_zero = time_service.get_timezone_from_offset(0)
        self.assertEqual(tz_zero.tzname(None), "UTC+00:00")

    def test_unlimited_models_have_no_countdown(self):
        for model_id in ('gpt-6-astra', 'gpt-6.1-sol'):
            info = time_service.format_release_info(model_id=model_id)
            self.assertFalse(info['enabled'])
            self.assertIsNone(info['next_slot_utc'])
            self.assertIsNone(info['seconds_remaining'])
            self.assertIn('Unlimited', info['availability_title'])

    def test_suspended_model_has_no_restoration_countdown(self):
        info = time_service.format_release_info(model_id='claude-opus-5.5')
        self.assertFalse(info['enabled'])
        self.assertIn('restoration time', info['schedule_message'])

    def test_minute_schedule_is_derived_from_model_policy(self):
        with patch('provider_updates.get_model', return_value={
            'id': 'new-model', 'provider_status': 'limited', 'available_in_account': True,
            'release_minutes_utc': [105]
        }):
            info = time_service.format_release_info(
                now_utc=datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc),
                model_id='new-model', user_offset_minutes=330)
        self.assertTrue(info['enabled'])
        self.assertEqual(info['next_slot_utc'], '2026-10-25T01:45:00+00:00')
        self.assertEqual(info['local_time'], '07:15 AM')
        self.assertEqual(info['seconds_remaining'], 2700)

    def test_no_default_quota_windows(self):
        self.assertFalse(time_service.calculate_next_release()['enabled'])

    def test_unknown_or_unpublished_schedule_has_no_countdown(self):
        with patch('provider_updates.get_model', return_value={
            'id': 'new-model', 'provider_status': 'limited', 'release_minutes_utc': []
        }):
            info = time_service.format_release_info(model_id='new-model')
        self.assertFalse(info['enabled'])
        self.assertIn('not announced', info['availability_title'])


if __name__ == "__main__":
    unittest.main()
