"""
Unit tests for config_manager.py.
Verifies API key saving, editing, clearing, and masking.
"""

import unittest
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
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

    def test_save_and_load_widget_settings(self):
        """Verifies persistence of settings like always_on_top and sound_alert_enabled."""
        updates = {
            "always_on_top": False,
            "sound_alert_enabled": False,
            "user_timezone_offset": 480,
            "selected_model": "deepseek-v4-flash"
        }
        config_manager.save_config(updates)
        cfg = config_manager.load_config()
        self.assertFalse(cfg["always_on_top"])
        self.assertFalse(cfg["sound_alert_enabled"])
        self.assertEqual(cfg["user_timezone_offset"], 480)
        self.assertEqual(cfg["selected_model"], "deepseek-v4-flash")

    def test_mask_key_edge_cases(self):
        """Verifies mask_key handles None, whitespace, and boundaries."""
        self.assertEqual(config_manager.mask_key(None), "")
        self.assertEqual(config_manager.mask_key("   "), "")
        self.assertEqual(config_manager.mask_key("12345678"), "••••••••")
        self.assertEqual(config_manager.mask_key("123456789"), "1234••••••••6789")

    def test_dpapi_encryption_at_rest(self):
        """Verifies that API keys are stored encrypted at rest with Windows DPAPI and never in plaintext on disk."""
        secret_key = "sk-super-secret-dpapi-live-token-9999"
        config_manager.set_api_key(secret_key)

        # Inspect raw content of config.json on disk
        self.assertTrue(os.path.exists(config_manager.CONFIG_FILE))
        with open(config_manager.CONFIG_FILE, "r", encoding="utf-8") as f:
            raw_disk_text = f.read()
            disk_json = json.loads(raw_disk_text)

        # Plaintext must NEVER appear in the disk file
        self.assertNotIn(secret_key, raw_disk_text)
        self.assertEqual(disk_json.get("api_key"), "")
        self.assertTrue(disk_json.get("api_key_encrypted", "").startswith(("enc:dpapi:", "dev:b64:")))

        # In-memory retrieval must transparently decrypt via DPAPI
        self.assertEqual(config_manager.get_api_key(), secret_key)
        self.assertEqual(config_manager.load_config()["api_key"], secret_key)

    def test_legacy_plaintext_migration(self):
        """Verifies that legacy unencrypted config.json files are automatically encrypted and purged on first load."""
        legacy_plaintext = "sk-legacy-unencrypted-token-8888"
        with open(config_manager.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "api_key": legacy_plaintext,
                "base_url": "https://agentrouter.org"
            }, f, indent=2)

        # First load should read legacy key and migrate
        cfg = config_manager.load_config()
        self.assertEqual(cfg["api_key"], legacy_plaintext)

        # Check file on disk: plaintext key must be purged and replaced by encrypted blob
        with open(config_manager.CONFIG_FILE, "r", encoding="utf-8") as f:
            disk_text = f.read()
            disk_json = json.loads(disk_text)

        self.assertNotIn(legacy_plaintext, disk_text)
        self.assertEqual(disk_json.get("api_key"), "")
        self.assertTrue(disk_json.get("api_key_encrypted", "").startswith(("enc:dpapi:", "dev:b64:")))

    def test_encrypt_decrypt_secret_roundtrip(self):
        """Verifies encrypt_secret and decrypt_secret functions."""
        sample = "sk-ant-test-token-777-XYZ"
        ciphertext = config_manager.encrypt_secret(sample)
        self.assertTrue(ciphertext.startswith(("enc:dpapi:", "dev:b64:")))
        self.assertNotEqual(ciphertext, sample)
        decrypted = config_manager.decrypt_secret(ciphertext)
        self.assertEqual(decrypted, sample)

        # Empty / whitespace tests
        self.assertEqual(config_manager.encrypt_secret(""), "")
        self.assertEqual(config_manager.decrypt_secret(""), "")


if __name__ == "__main__":
    unittest.main()
