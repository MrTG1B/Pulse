"""Regression tests for DPI-scaled placement and native Pulse window recovery."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import app


class TestWindowGeometry(unittest.TestCase):
    def assert_fits_work_area(self, work, scale, geometry):
        left, top = geometry["x"] * scale, geometry["y"] * scale
        right = left + geometry["width"] * scale
        bottom = top + geometry["height"] * scale
        self.assertLess(left, right)
        self.assertLess(top, bottom)
        self.assertGreaterEqual(left, work[0])
        self.assertGreaterEqual(top, work[1])
        self.assertLessEqual(right, work[2])
        self.assertLessEqual(bottom, work[3])

    def test_150_percent_scaling_does_not_place_window_beyond_right_edge(self):
        work = (0, 0, 1920, 1080)
        geometry = app.calculate_window_geometry(work, scale=1.5)
        self.assertEqual(geometry["x"], 850)
        self.assertEqual(geometry["width"], 410)
        self.assertLess(geometry["height"], 720)
        self.assert_fits_work_area(work, 1.5, geometry)

    def test_common_scaling_factors_fit_below_taskbar(self):
        work = (0, 0, 1920, 1040)
        for scale in (1.0, 1.25, 1.5, 1.75, 2.0):
            with self.subTest(scale=scale):
                self.assert_fits_work_area(work, scale, app.calculate_window_geometry(work, scale))

    def test_negative_monitor_origin_is_preserved(self):
        work = (-1920, -300, 0, 740)
        geometry = app.calculate_window_geometry(work, scale=1.5)
        self.assertLess(geometry["x"], 0)
        self.assert_fits_work_area(work, 1.5, geometry)

    def test_small_display_reduces_window_size(self):
        work = (0, 0, 640, 480)
        geometry = app.calculate_window_geometry(work, scale=2.0)
        self.assertLess(geometry["width"], 360)
        self.assert_fits_work_area(work, 2.0, geometry)

    def test_invalid_work_area_or_scale_is_rejected(self):
        for work, scale in (((0, 0, 0, 720), 1), ((0, 0, 1280, 720), 0)):
            with self.subTest(work=work, scale=scale), self.assertRaises(ValueError):
                app.calculate_window_geometry(work, scale)

    def test_windows_geometry_uses_work_area_and_dpi(self):
        user32 = MagicMock()
        user32.GetDpiForSystem.return_value = 144

        def read_work_area(action, size, rect_pointer, flags):
            self.assertEqual(action, 0x0030)
            rect = rect_pointer._obj
            rect.left, rect.top, rect.right, rect.bottom = (0, 0, 1920, 1040)
            return True

        user32.SystemParametersInfoW.side_effect = read_work_area
        with patch.object(app.sys, "platform", "win32"), \
             patch.object(app.ctypes, "windll", SimpleNamespace(user32=user32), create=True):
            geometry = app.get_initial_window_geometry()
        self.assert_fits_work_area((0, 0, 1920, 1040), 1.5, geometry)
        user32.SetProcessDPIAware.assert_called_once()
        user32.GetDpiForSystem.assert_called_once()

    def test_work_area_failure_uses_native_centering(self):
        user32 = MagicMock()
        user32.SystemParametersInfoW.return_value = False
        with patch.object(app.sys, "platform", "win32"), \
             patch.object(app.ctypes, "windll", SimpleNamespace(user32=user32), create=True):
            self.assertEqual(app.get_initial_window_geometry(),
                             {"x": None, "y": None, "width": 410, "height": 720})


class TestPulseWindowRecovery(unittest.TestCase):
    def setUp(self):
        self.hwnd = 100
        self.work = (0, 0, 1920, 1080)
        self.state = {"visible": True, "minimized": False, "rect": (2220, 247, 2813, 1271)}
        self.gui = MagicMock()
        self.api = MagicMock()
        self.constants = SimpleNamespace(
            SW_RESTORE=9, SW_SHOW=5, MONITOR_DEFAULTTONEAREST=2,
            SWP_NOZORDER=0x0004, SWP_NOACTIVATE=0x0010, SWP_SHOWWINDOW=0x0040,
        )
        self.gui.IsWindow.return_value = True
        self.gui.IsWindowVisible.side_effect = lambda hwnd: self.state["visible"]
        self.gui.IsIconic.side_effect = lambda hwnd: self.state["minimized"]
        self.gui.GetWindowRect.side_effect = lambda hwnd: self.state["rect"]
        self.gui.GetWindowText.return_value = "Pulse"
        self.gui.GetClassName.return_value = "WindowsForms10.Window"
        self.gui.EnumWindows.side_effect = lambda callback, param: callback(self.hwnd, param)
        self.api.GetMonitorInfo.return_value = {"Work": self.work}

        def show(hwnd, command):
            self.state.update(visible=True, minimized=False)

        def position(hwnd, after, x, y, width, height, flags):
            self.state["rect"] = (x, y, x + width, y + height)

        self.gui.ShowWindow.side_effect = show
        self.gui.SetWindowPos.side_effect = position
        platform = patch.object(app.sys, "platform", "win32")
        modules = patch.dict(sys.modules, {"win32gui": self.gui, "win32api": self.api,
                                           "win32con": self.constants})
        platform.start()
        modules.start()
        self.addCleanup(platform.stop)
        self.addCleanup(modules.stop)

    def assert_visible_and_fits(self):
        left, top, right, bottom = self.state["rect"]
        self.assertTrue(self.state["visible"])
        self.assertFalse(self.state["minimized"])
        self.assertGreaterEqual(left, self.work[0])
        self.assertGreaterEqual(top, self.work[1])
        self.assertLessEqual(right, self.work[2])
        self.assertLessEqual(bottom, self.work[3])

    def test_offscreen_window_is_moved_onto_monitor(self):
        self.assertTrue(app.restore_pulse_window(self.hwnd))
        self.assert_visible_and_fits()

    def test_window_larger_than_work_area_is_resized(self):
        self.state["rect"] = (3000, 1500, 6000, 3500)
        self.assertTrue(app.restore_pulse_window(self.hwnd))
        self.assert_visible_and_fits()

    def test_recovery_preserves_always_on_top(self):
        self.assertTrue(app.restore_pulse_window(self.hwnd))
        flags = self.gui.SetWindowPos.call_args.args[-1]
        self.assertTrue(flags & self.constants.SWP_NOZORDER)
        self.assertEqual(self.gui.SetWindowPos.call_args.args[1], 0)

    def test_reopening_finds_and_shows_hidden_window(self):
        self.state["visible"] = False
        self.assertTrue(app.focus_existing_instance(timeout_sec=0))
        self.gui.ShowWindow.assert_called_once_with(self.hwnd, self.constants.SW_SHOW)
        self.assert_visible_and_fits()

    def test_reopening_restores_minimized_window(self):
        self.state["minimized"] = True
        self.assertTrue(app.focus_existing_instance(timeout_sec=0))
        self.gui.ShowWindow.assert_called_once_with(self.hwnd, self.constants.SW_RESTORE)
        self.assert_visible_and_fits()

    def test_focus_permission_denied_still_recovers_visible_window(self):
        self.gui.SetForegroundWindow.side_effect = RuntimeError("Foreground permission denied")
        self.assertTrue(app.restore_pulse_window(self.hwnd))
        self.assert_visible_and_fits()

    def test_invalid_window_is_not_reported_as_recovered(self):
        self.gui.IsWindow.return_value = False
        self.assertFalse(app.restore_pulse_window(self.hwnd))
        self.gui.SetWindowPos.assert_not_called()

    def test_unrelated_browser_window_named_pulse_is_ignored(self):
        self.gui.GetClassName.return_value = "Chrome_WidgetWin_1"
        self.assertFalse(app.focus_existing_instance(timeout_sec=0))
        self.gui.SetWindowPos.assert_not_called()

    def test_failed_recovery_is_not_reported_as_success(self):
        self.gui.SetWindowPos.side_effect = RuntimeError("Window no longer exists")
        self.assertFalse(app.focus_existing_instance(timeout_sec=0))

    def test_expanding_compact_window_keeps_it_on_screen(self):
        window = MagicMock()
        window.native.Handle.ToInt64.return_value = self.hwnd
        window.resize.side_effect = lambda width, height: self.state.update(rect=(1500, 500, 2115, 1580))
        api = app.DesktopApi({"window": window})
        self.assertTrue(api.resize_window(410, 720))
        self.assert_visible_and_fits()


if __name__ == "__main__":
    unittest.main()
