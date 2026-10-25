"""
Unit tests for app.py single-instance mutex and focus handling.
"""

import unittest
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import app


class TestSingleInstance(unittest.TestCase):

    def tearDown(self):
        app.release_single_instance_lock()

    @unittest.skipUnless(sys.platform == "win32", "Windows named mutex")
    def test_acquire_and_release_single_instance_lock(self):
        """Verifies named mutex allows first acquisition and blocks concurrent acquisition."""
        test_mutex_name = "Local\\TestPulseSingleInstance_1"
        acquired1 = app.acquire_single_instance_lock(test_mutex_name)
        self.assertTrue(acquired1, "First instance must successfully acquire mutex")

        # Second attempt with same mutex name must fail
        acquired2 = app.acquire_single_instance_lock(test_mutex_name)
        self.assertFalse(acquired2, "Second instance must be denied mutex")

        # Release lock
        app.release_single_instance_lock()

        # After release, acquire must succeed again
        acquired3 = app.acquire_single_instance_lock(test_mutex_name)
        self.assertTrue(acquired3, "Must re-acquire mutex after previous lock released")

    @unittest.skipUnless(sys.platform == "win32", "Windows named mutex")
    def test_mutex_preserves_64_bit_handle(self):
        kernel32 = MagicMock()
        handle = 0x1234567887654321
        kernel32.CreateMutexW.return_value = handle
        with patch.object(app.ctypes, "WinDLL", return_value=kernel32), \
             patch.object(app.ctypes, "get_last_error", return_value=0):
            self.assertTrue(app.acquire_single_instance_lock("Local\\TestPulseWideHandle"))
            try:
                self.assertEqual(app._SINGLE_INSTANCE_MUTEX, handle)
                self.assertIs(kernel32.CreateMutexW.restype, app.wintypes.HANDLE)
            finally:
                app.release_single_instance_lock()
            kernel32.CloseHandle.assert_called_once_with(handle)

    @unittest.skipUnless(sys.platform == "win32", "Windows named mutex")
    def test_mutex_creation_failure_does_not_launch_unlocked(self):
        kernel32 = MagicMock()
        kernel32.CreateMutexW.return_value = None
        with patch.object(app.ctypes, "WinDLL", return_value=kernel32), \
             patch.object(app.ctypes, "get_last_error", return_value=5):
            self.assertFalse(app.acquire_single_instance_lock("Local\\TestPulseFailedHandle"))

    def test_unrecoverable_duplicate_does_not_start_server_or_kill_processes(self):
        with patch.object(sys, "argv", ["Pulse.exe"]), \
             patch.object(app, "acquire_single_instance_lock", return_value=False), \
             patch.object(app, "focus_existing_instance", return_value=False), \
             patch.object(app, "start_server_thread") as start_server, \
             patch.object(app.webview, "start"), \
             patch.object(app.webview, "create_window"), \
             patch("psutil.process_iter", return_value=[]) as process_iter:
            app.main()
        start_server.assert_not_called()
        process_iter.assert_not_called()

    def test_focus_existing_instance_runs_safely(self):
        """Verifies focus_existing_instance does not crash even if no window is found."""
        result = app.focus_existing_instance(timeout_sec=0.1)
        # On headless test environment or when window is not present, returns False without raising
        self.assertIn(result, (True, False))


if __name__ == "__main__":
    unittest.main()
