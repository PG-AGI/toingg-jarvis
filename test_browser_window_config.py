import sys
import types
import unittest
from unittest.mock import patch

import jarvis_launcher
sys.modules.setdefault("websocket", types.SimpleNamespace(WebSocketApp=object))
sys.modules.setdefault("playwright", types.ModuleType("playwright"))
playwright_sync_api = types.ModuleType("playwright.sync_api")
playwright_sync_api.Page = object
playwright_sync_api.Playwright = object
playwright_sync_api.sync_playwright = lambda: None
sys.modules.setdefault("playwright.sync_api", playwright_sync_api)
import browserClient
from browser_window_config import (
    BrowserWindowConfig,
    chrome_window_args,
    choose_screen_bounds,
    parse_browser_window_config,
    parse_window_position,
    parse_window_size,
    resolve_window_geometry,
)


class BrowserWindowConfigTests(unittest.TestCase):
    def test_parse_window_size_accepts_common_terminal_format(self):
        self.assertEqual(parse_window_size("1600x900"), (1600, 900))
        self.assertEqual(parse_window_size(" 1024 X 768 "), (1024, 768))

    def test_parse_window_position_accepts_named_and_coordinate_values(self):
        self.assertEqual(parse_window_position("center"), "center")
        self.assertEqual(parse_window_position("top-left"), "top-left")
        self.assertEqual(parse_window_position("x=1920,y=0"), (1920, 0))

    def test_cli_values_override_environment_and_config_file_values(self):
        config = parse_browser_window_config(
            config_data={
                "browser": {
                    "preferred_monitor": "primary",
                    "window_size": {"width": 1200, "height": 800},
                    "position": "top-left",
                }
            },
            environ={
                "JARVIS_BROWSER_MONITOR": "monitor-2",
                "JARVIS_BROWSER_WINDOW_SIZE": "1400x850",
                "JARVIS_BROWSER_POSITION": "center",
            },
            cli_values={
                "preferred_monitor": "active",
                "window_size": "1600x900",
                "position": "x=1920,y=0",
            },
        )

        self.assertEqual(config.preferred_monitor, "active")
        self.assertEqual(config.window_size, (1600, 900))
        self.assertEqual(config.position, (1920, 0))

    def test_resolve_window_geometry_uses_configured_size_and_position(self):
        config = BrowserWindowConfig(
            preferred_monitor="active",
            window_size=(1600, 900),
            position="center",
        )

        self.assertEqual(
            resolve_window_geometry(
                config,
                default_size=(700, 420),
                default_position=(100, 20),
                screen_bounds=(1920, 0, 1920, 1080),
            ),
            (1600, 900, 2080, 90),
        )

    def test_chrome_window_args_formats_size_and_position_switches(self):
        self.assertEqual(
            chrome_window_args(1600, 900, 1920, 0),
            ["--window-size=1600,900", "--window-position=1920,0"],
        )

    def test_choose_screen_bounds_supports_active_primary_and_numbered_monitors(self):
        screens = [(0, 0, 1280, 720), (1280, 0, 1920, 1080)]
        active = (1280, 0, 1920, 1080)
        fallback = (0, 0, 1920, 1080)

        self.assertEqual(choose_screen_bounds("active", screens, active, fallback), active)
        self.assertEqual(choose_screen_bounds("primary", screens, active, fallback), screens[0])
        self.assertEqual(choose_screen_bounds("monitor-2", screens, active, fallback), screens[1])
        self.assertEqual(choose_screen_bounds("monitor-9", screens, active, fallback), active)

    def test_launcher_applies_configured_web_window_geometry(self):
        jarvis_launcher.configure_browser_windows(
            ["--window-size", "900x500", "--position", "center"]
        )
        jarvis_launcher._web_proc = None

        with patch.object(jarvis_launcher, "find_chrome", return_value="chrome"), \
                patch.object(jarvis_launcher, "get_active_screen_bounds", return_value=(0, 0, 1000, 800)), \
                patch.object(jarvis_launcher.subprocess, "Popen") as popen:
            popen.return_value.poll.return_value = None

            jarvis_launcher.open_jarvis_web_bg()

        chrome_args = popen.call_args.args[0]
        self.assertIn("--window-size=900,500", chrome_args)
        self.assertIn("--window-position=50,150", chrome_args)
        jarvis_launcher.configure_browser_windows([])

    def test_browser_client_launch_options_include_window_config(self):
        config = BrowserWindowConfig(
            preferred_monitor="active",
            window_size=(1440, 900),
            position=(20, 40),
        )

        options = browserClient.build_launch_options(config)

        self.assertEqual(options["viewport"], {"width": 1440, "height": 900})
        self.assertIn("--window-size=1440,900", options["args"])
        self.assertIn("--window-position=20,40", options["args"])


if __name__ == "__main__":
    unittest.main()
