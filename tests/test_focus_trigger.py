"""
Tests for focus_trigger module (app finding and decision pipeline).
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure src/ is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import focus_trigger


class TestFocusTrigger(unittest.TestCase):

    def test_find_target_windows_codex_by_process_name(self):
        """Codex is detected by process name (codex.exe), not title."""
        mock_windows = [
            {"hwnd": 1001, "title": "http://127.0.0.1:27182/mcp connect to fusion", "pid": 1234, "pname": "codex.exe", "pexe": "c:\\codex\\codex.exe"},
            {"hwnd": 1002, "title": "Visual Studio Code", "pid": 5678, "pname": "code.exe", "pexe": "c:\\vscode\\code.exe"},
            {"hwnd": 1003, "title": "Google Chrome", "pid": 9999, "pname": "chrome.exe", "pexe": "c:\\chrome\\chrome.exe"},
        ]
        with patch.object(focus_trigger, '_get_all_visible_windows', return_value=mock_windows):
            results = focus_trigger.find_target_windows()
            apps = [r["app"] for r in results]
            self.assertIn("codex", apps)
            codex_win = next(r for r in results if r["app"] == "codex")
            self.assertEqual(codex_win["hwnd"], 1001)

    def test_find_target_windows_codex_windowsapps_chatgpt_exe(self):
        """Codex installed from WindowsApps package runs as ChatGPT.exe with OpenAI.Codex in exe path."""
        mock_windows = [
            {
                "hwnd": 1005,
                "title": "http://127.0.0.1:27182/mcp connect to fusion",
                "pid": 3784,
                "pname": "chatgpt.exe",
                "pexe": r"d:\windowsapps\openai.codex_26.1007.2314.0_x64__2p2nqsd0c76g0\app\chatgpt.exe",
            },
            {
                "hwnd": 1006,
                "title": "ChatGPT Classic",
                "pid": 3228,
                "pname": "chatgpt classic.exe",
                "pexe": r"d:\windowsapps\openai.chatgpt-desktop_1.2026.190.0_x64__2p2nqsd0c76g0\app\chatgpt classic.exe",
            },
        ]
        with patch.object(focus_trigger, '_get_all_visible_windows', return_value=mock_windows):
            results = focus_trigger.find_target_windows()
            apps = [r["app"] for r in results]
            self.assertIn("codex", apps)
            self.assertEqual(len(results), 1)
            codex_win = results[0]
            self.assertEqual(codex_win["hwnd"], 1005)

    def test_find_target_windows_codex_by_title_fallback(self):
        """Codex title fallback: if process name doesn't match but title contains 'codex'."""
        mock_windows = [
            {"hwnd": 1001, "title": "Codex", "pid": 1234, "pname": "electron.exe", "pexe": "c:\\electron.exe"},
        ]
        with patch.object(focus_trigger, '_get_all_visible_windows', return_value=mock_windows):
            results = focus_trigger.find_target_windows()
            apps = [r["app"] for r in results]
            self.assertIn("codex", apps)

    def test_find_target_windows_claude_by_process_name(self):
        mock_windows = [
            {"hwnd": 2001, "title": "Gemini Live model capabilities", "pid": 4321, "pname": "claude.exe", "pexe": "c:\\claude.exe"},
            {"hwnd": 2002, "title": "File Explorer", "pid": 1111, "pname": "explorer.exe", "pexe": "c:\\explorer.exe"},
        ]
        with patch.object(focus_trigger, '_get_all_visible_windows', return_value=mock_windows):
            results = focus_trigger.find_target_windows()
            apps = [r["app"] for r in results]
            self.assertIn("claude", apps)
            claude_win = next(r for r in results if r["app"] == "claude")
            self.assertEqual(claude_win["hwnd"], 2001)

    def test_find_both_apps_simultaneously(self):
        """Both Codex (via OpenAI.Codex path) and Claude Code detected at the same time."""
        mock_windows = [
            {
                "hwnd": 1001,
                "title": "MCP Task",
                "pid": 100,
                "pname": "chatgpt.exe",
                "pexe": r"d:\windowsapps\openai.codex_26.1007.2314.0_x64__2p2nqsd0c76g0\app\chatgpt.exe",
            },
            {
                "hwnd": 2001,
                "title": "Claude Task",
                "pid": 200,
                "pname": "claude.exe",
                "pexe": r"c:\users\hp\appdata\local\claude-3p\claude-code\2.1.295\claude.exe",
            },
            {"hwnd": 3001, "title": "Chrome", "pid": 300, "pname": "chrome.exe", "pexe": "chrome.exe"},
        ]
        with patch.object(focus_trigger, '_get_all_visible_windows', return_value=mock_windows):
            results = focus_trigger.find_target_windows()
            apps = sorted([r["app"] for r in results])
            self.assertEqual(apps, ["claude", "codex"])

    def test_trigger_all_targets_empty(self):
        with patch.object(focus_trigger, 'find_target_windows', return_value=[]):
            results = focus_trigger.trigger_all_targets()
            self.assertEqual(len(results["found"]), 0)
            self.assertIn("No Codex or Claude Code windows found", results["message"])

    def test_trigger_all_targets_with_mock_targets(self):
        mock_targets = [
            {"hwnd": 3001, "title": "Codex", "pid": 101, "app": "codex"},
        ]
        with patch.object(focus_trigger, 'find_target_windows', return_value=mock_targets), \
             patch.object(focus_trigger, 'force_foreground', return_value=True), \
             patch.object(focus_trigger, 'simulate_enter', return_value=True):
            results = focus_trigger.trigger_all_targets(press_enter=True)
            self.assertEqual(len(results["found"]), 1)
            self.assertEqual(len(results["focused"]), 1)
            self.assertEqual(len(results["entered"]), 1)
            self.assertIn("Pressed Enter on 1", results["message"])

    def test_ai_gate_skips_when_false(self):
        mock_targets = [
            {"hwnd": 4001, "title": "Codex", "pid": 202, "app": "codex"},
        ]
        ai_gate_no = lambda title: False
        with patch.object(focus_trigger, 'find_target_windows', return_value=mock_targets), \
             patch.object(focus_trigger, 'force_foreground', return_value=True), \
             patch.object(focus_trigger, 'simulate_enter') as mock_enter:
            results = focus_trigger.trigger_all_targets(press_enter=True, ai_gate_fn=ai_gate_no)
            self.assertEqual(len(results["skipped_by_ai"]), 1)
            self.assertEqual(len(results["entered"]), 0)
            mock_enter.assert_not_called()


if __name__ == '__main__':
    unittest.main()
