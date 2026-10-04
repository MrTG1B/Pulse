"""
Unit tests for time_service.py.
Verifies UTC 02:00 and 11:00 release schedule calculations and UTC+05:30 IST conversions.
"""

import unittest
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import time_service


class TestTimeService(unittest.TestCase):

    def test_utc_0200_release_slot(self):
        """When current time is 01:00 UTC, next release must be 02:00 UTC (Batch 1)."""
        mock_now = datetime(2026, 10, 3, 1, 0, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now)

        self.assertEqual(res["batch_number"], 1)
        self.assertEqual(res["next_slot_utc"], "2026-10-03T02:00:00+00:00")
        self.assertEqual(res["seconds_remaining"], 3600)
        self.assertEqual(res["hours_remaining"], 1)
        self.assertEqual(res["minutes_remaining"], 0)
        self.assertEqual(res["seconds_part"], 0)

    def test_utc_1100_release_slot(self):
        """When current time is 05:00 UTC, next release must be 11:00 UTC (Batch 2)."""
        mock_now = datetime(2026, 10, 3, 5, 0, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now)

        self.assertEqual(res["batch_number"], 2)
        self.assertEqual(res["next_slot_utc"], "2026-10-03T11:00:00+00:00")
        self.assertEqual(res["seconds_remaining"], 6 * 3600)
        self.assertEqual(res["hours_remaining"], 6)

    def test_day_rollover_slot(self):
        """When current time is 18:00 UTC, next release must be tomorrow 02:00 UTC (Batch 1)."""
        mock_now = datetime(2026, 10, 3, 18, 0, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now)

        self.assertEqual(res["batch_number"], 1)
        self.assertEqual(res["next_slot_utc"], "2026-10-04T02:00:00+00:00")
        self.assertEqual(res["seconds_remaining"], 8 * 3600)
        self.assertEqual(res["hours_remaining"], 8)

    def test_exact_release_time_moves_to_next(self):
        """At exactly 02:00:00 UTC, the next future release must be 11:00:00 UTC."""
        mock_now = datetime(2026, 10, 3, 2, 0, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now)

        self.assertEqual(res["batch_number"], 2)
        self.assertEqual(res["next_slot_utc"], "2026-10-03T11:00:00+00:00")

    def test_user_local_timezone_ist_conversion(self):
        """
        User's timezone is UTC+05:30 (India Standard Time).
        - 02:00 UTC must format to 07:30 AM IST.
        - 11:00 UTC must format to 04:30 PM IST.
        """
        # Test Morning Drop (02:00 UTC -> 07:30 AM IST)
        mock_now = datetime(2026, 10, 3, 0, 0, 0, tzinfo=timezone.utc)
        info = time_service.format_release_info(now_utc=mock_now, user_offset_minutes=330)

        self.assertIn("07:30 AM", info["local_time"])
        self.assertEqual(info["user_timezone"], "UTC+05:30")
        self.assertIn("07:30 AM & 04:30 PM", info["daily_schedule_local"])

        # Test Afternoon Drop (11:00 UTC -> 04:30 PM IST)
        mock_now_afternoon = datetime(2026, 10, 3, 3, 0, 0, tzinfo=timezone.utc)
        info_afternoon = time_service.format_release_info(now_utc=mock_now_afternoon, user_offset_minutes=330)
        self.assertIn("04:30 PM", info_afternoon["local_time"])

    def test_beijing_reference_time(self):
        """Beijing time must format to 10:00 CST (for 02:00 UTC) and 19:00 CST (for 11:00 UTC)."""
        mock_now = datetime(2026, 10, 3, 0, 0, 0, tzinfo=timezone.utc)
        info = time_service.format_release_info(now_utc=mock_now)
        self.assertIn("10:00", info["beijing_time"])

        mock_now2 = datetime(2026, 10, 3, 3, 0, 0, tzinfo=timezone.utc)
        info2 = time_service.format_release_info(now_utc=mock_now2)
        self.assertIn("19:00", info2["beijing_time"])

    def test_cycle_progress_percentage(self):
        """Cycle progress must be between 0% and 100%."""
        mock_now = datetime(2026, 10, 3, 6, 30, 0, tzinfo=timezone.utc)
        res = time_service.calculate_next_release(mock_now)
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


if __name__ == "__main__":
    unittest.main()
