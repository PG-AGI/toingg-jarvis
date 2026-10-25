import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import jarvis_launcher
from browser_window_config import (
    BrowserWindowConfigError,
    build_launcher_arg_parser,
    compute_window_geometry,
    load_browser_window_config,
    parse_preferred_monitor,
    parse_window_position,
    parse_window_size,
    resolve_monitor_bounds,
)


class BrowserWindowConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self.tmpdir.name) / "config.json"
        self.monitors = [
            (0, 0, 1920, 1080),
            (1920, 0, 2560, 1440),
        ]

    def tearDown(self):
        jarvis_launcher.update_browser_window_config(
            {"preferred_monitor": "active", "window_size": "860x580", "position": "grid"},
            persist=False,
        )
        self.tmpdir.cleanup()

    def test_parse_preferred_monitor_and_resolve_bounds(self):
        self.assertEqual(parse_preferred_monitor("active"), "active")
        self.assertEqual(parse_preferred_monitor("primary"), "primary")
        self.assertEqual(parse_preferred_monitor("1"), 1)

        # Monitor index 1 selects secondary monitor
        self.assertEqual(
            resolve_monitor_bounds(1, monitors=self.monitors, active_screen_bounds=self.monitors[0]),
            (1920, 0, 2560, 1440),
        )
        # Out-of-range monitor index falls back safely to primary monitor
        self.assertEqual(
            resolve_monitor_bounds(5, monitors=self.monitors, active_screen_bounds=self.monitors[1]),
            (0, 0, 1920, 1080),
        )

    def test_parse_window_size_strings_presets_and_validation(self):
        self.assertEqual(parse_window_size("1280x720"), (1280, 720))
        self.assertEqual(parse_window_size("large"), (1280, 800))
        self.assertEqual(parse_window_size({"width": 1000, "height": 650}), (1000, 650))
        self.assertEqual(
            parse_window_size("fullscreen", screen_bounds=(0, 0, 1920, 1080)),
            (1880, 1040),
        )
        with self.assertRaises(BrowserWindowConfigError):
            parse_window_size("100x80")
        with self.assertRaises(BrowserWindowConfigError):
            parse_window_size("invalid-size")

    def test_compute_window_geometry_presets_and_custom_coordinates(self):
        # Center on monitor 1 (1920, 0, 2560, 1440) with 1000x600 window
        w, h, x, y = compute_window_geometry(
            {"preferred_monitor": 1, "window_size": "1000x600", "position": "center"},
            monitors=self.monitors,
        )
        self.assertEqual((w, h), (1000, 600))
        self.assertEqual(x, 1920 + (2560 - 1000) // 2)
        self.assertEqual(y, 0 + (1440 - 600) // 2)

        # Custom x=150,y=120 on monitor 1
        w2, h2, x2, y2 = compute_window_geometry(
            {"preferred_monitor": 1, "window_size": "860x580", "position": "x=150,y=120"},
            monitors=self.monitors,
        )
        self.assertEqual((w2, h2, x2, y2), (860, 580, 1920 + 150, 120))

        # Off-screen custom coordinates clamp safely within monitor work area
        _, _, x3, y3 = compute_window_geometry(
            {"preferred_monitor": 0, "window_size": "860x580", "position": "x=9999,y=9999"},
            monitors=self.monitors,
        )
        self.assertEqual(x3, 1920 - 860 - 20)
        self.assertEqual(y3, 1080 - 580 - 20)

    def test_precedence_cli_overrides_env_overrides_config_file(self):
        self.cfg_path.write_text(
            json.dumps(
                {
                    "browser": {
                        "preferred_monitor": 0,
                        "window_size": "800x600",
                        "position": "top-left",
                    }
                }
            ),
            encoding="utf-8",
        )
        env = {
            "JARVIS_BROWSER_MONITOR": "1",
            "JARVIS_BROWSER_WINDOW_SIZE": "1024x720",
            "JARVIS_BROWSER_POSITION": "bottom-right",
        }
        # Env overrides config.json
        from_env = load_browser_window_config(config_path=self.cfg_path, environ=env)
        self.assertEqual(from_env["preferred_monitor"], 1)
        self.assertEqual(from_env["window_size"], "1024x720")
        self.assertEqual(from_env["position"], "bottom-right")

        # CLI overrides both Env and config.json
        parser = build_launcher_arg_parser()
        cli_ns = parser.parse_args(
            ["--monitor", "primary", "--window-size", "1280x800", "--position", "center"]
        )
        from_cli = load_browser_window_config(
            config_path=self.cfg_path,
            cli_args=vars(cli_ns),
            environ=env,
        )
        self.assertEqual(from_cli["preferred_monitor"], "primary")
        self.assertEqual(from_cli["window_size"], "1280x800")
        self.assertEqual(from_cli["position"], "center")

    def test_open_url_in_slot_uses_configured_browser_window_geometry(self):
        jarvis_launcher.update_browser_window_config(
            {
                "preferred_monitor": "primary",
                "window_size": "1200x750",
                "position": "center",
            },
            persist=False,
        )
        with mock.patch.object(jarvis_launcher, "find_chrome", return_value="/usr/bin/google-chrome"), \
             mock.patch.object(jarvis_launcher, "enumerate_monitors", return_value=[(0, 0, 1920, 1080)]), \
             mock.patch.object(jarvis_launcher, "get_active_screen_bounds", return_value=(0, 0, 1920, 1080)), \
             mock.patch("subprocess.Popen") as popen_mock:
            jarvis_launcher.open_url_in_slot("https://example.com", 0, {"title": "Test"})

        popen_mock.assert_called_once()
        launched_args = popen_mock.call_args[0][0]
        self.assertIn("--window-size=1200,750", launched_args)
        self.assertIn("--window-position=360,165", launched_args)


if __name__ == "__main__":
    unittest.main()
