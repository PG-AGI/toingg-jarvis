import json
import os
import tempfile
import unittest
from unittest.mock import patch

import jarvis_launcher


class PackagingRuntimeTests(unittest.TestCase):
    def test_required_web_resources_resolve_from_source_tree(self):
        self.assertTrue(os.path.isfile(jarvis_launcher.WEB_HTML))
        self.assertTrue(os.path.isfile(jarvis_launcher.VISUAL_HTML))
        self.assertTrue(
            os.path.isfile(jarvis_launcher._resource_path("config.example.json"))
        )

    def test_config_is_bootstrapped_in_writable_user_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with (
                patch.object(jarvis_launcher, "_CONFIG_DIR", temp_dir),
                patch.object(jarvis_launcher, "CONFIG_PATH", config_path),
            ):
                created_path = jarvis_launcher._ensure_config_file()
                jarvis_launcher._save_token("a" * 24)

                self.assertEqual(created_path, config_path)
                with open(config_path, "r", encoding="utf-8") as config_file:
                    config = json.load(config_file)
                self.assertEqual(config["TOKEN"], "a" * 24)

    def test_config_directory_can_be_overridden_for_automation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"JARVIS_CONFIG_DIR": temp_dir}):
                self.assertEqual(jarvis_launcher._platform_config_dir(), temp_dir)
                self.assertEqual(jarvis_launcher._runtime_config_dir(), temp_dir)


if __name__ == "__main__":
    unittest.main()
