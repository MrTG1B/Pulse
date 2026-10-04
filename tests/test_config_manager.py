"""
Unit tests for config_manager.py.
Verifies API key saving, editing, clearing, and masking.
"""

import unittest
import os
import json
import tempfile
import config_manager


class TestConfigManager(unittest.TestCase):

    def setUp(self):
        # Create isolated temporary config file
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_cfg_path = os.path.join(self.tmp_dir.name, "config.json")
        self.original_config_file = config_manager.CONFIG_FILE
        config_manager.CONFIG_FILE = self.test_cfg_path

    def tearDown(self):
        config_manager.CONFIG_FILE = self.original_config_file
        self.tmp_dir.cleanup()

    def test_default_config_loading(self):
        cfg = config_manager.load_config()
        self.assertEqual(cfg["api_key"], "")
        self.assertEqual(cfg["base_url"], "https://agentrouter.org")
        self.assertTrue(cfg["always_on_top"])

    def test_save_and_load_api_key(self):
        test_key = "sk-ar-test-1234567890abcdef"
        config_manager.set_api_key(test_key)

        loaded = config_manager.load_config()
        self.assertEqual(loaded["api_key"], test_key)

    def test_mask_api_key(self):
        key = "sk-12345678abcdef"
        masked = config_manager.mask_key(key)
        self.assertTrue(masked.startswith("sk-1"))
        self.assertTrue(masked.endswith("cdef"))
        self.assertIn("••••••••", masked)

        # Empty key
        self.assertEqual(config_manager.mask_key(""), "")
        # Short key
        self.assertEqual(config_manager.mask_key("short"), "••••••••")

    def test_safe_config_does_not_leak_key(self):
        key = "sk-supersecretkey123456"
        config_manager.set_api_key(key)

        safe = config_manager.get_safe_config()
        self.assertTrue(safe["has_api_key"])
        self.assertNotEqual(safe["api_key"], key)
        self.assertIn("••••••••", safe["api_key"])

    def test_clear_api_key(self):
        config_manager.set_api_key("sk-to-delete")
        config_manager.clear_api_key()

        cfg = config_manager.load_config()
        self.assertEqual(cfg["api_key"], "")
        safe = config_manager.get_safe_config()
        self.assertFalse(safe["has_api_key"])

    def test_get_api_key_returns_raw_key(self):
        test_key = "sk-ar-raw-key-777888999"
        config_manager.set_api_key(test_key)
        self.assertEqual(config_manager.get_api_key(), test_key)

    def test_concurrent_save_and_load(self):
        """Verifies concurrent threads saving and loading config do not deadlock or throw PermissionError."""
        import threading
        errors = []

        def worker(idx):
            try:
                for i in range(10):
                    config_manager.save_config({"test_counter": f"{idx}_{i}"})
                    cfg = config_manager.load_config()
                    self.assertIn("test_counter", cfg)
                    safe = config_manager.get_safe_config()
                    self.assertIn("has_api_key", safe)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent config operations failed with: {errors}")

    def test_get_config_path(self):
        """Verifies get_config_path returns a valid path ending in config.json."""
        path = config_manager.get_config_path()
        self.assertTrue(path.endswith("config.json"))

    def test_get_template_config(self):
        """Verifies get_template_config returns a dictionary of defaults."""
        tmpl = config_manager.get_template_config()
        self.assertIsInstance(tmpl, dict)


if __name__ == "__main__":
    unittest.main()
