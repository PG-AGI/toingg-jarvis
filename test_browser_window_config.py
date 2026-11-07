import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from browser_window_config import (
    BrowserWindowConfig,
    BrowserWindowConfigError,
    MonitorBounds,
    WindowPosition,
    WindowSize,
    build_chromium_window_args,
    compute_window_geometry,
    load_browser_window_config,
    parse_preferred_monitor,
    parse_window_position,
    parse_window_size,
    resolve_monitor_bounds,
)
import jarvis_launcher


class BrowserWindowConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        jarvis_launcher.set_browser_window_config({})

    def tearDown(self):
        jarvis_launcher.set_browser_window_config({})
        self.tmpdir.cleanup()

    def test_parse_preferred_monitor_supports_named_and_indexed_monitors(self):
        self.assertEqual(parse_preferred_monitor("primary"), "primary")
        self.assertEqual(parse_preferred_monitor("ACTIVE"), "active")
        self.assertEqual(parse_preferred_monitor("monitor-1"), "monitor-1")
        self.assertEqual(parse_preferred_monitor("monitor-2"), "monitor-2")
        self.assertEqual(parse_preferred_monitor(2), "monitor-2")
        self.assertEqual(parse_preferred_monitor("2"), "monitor-2")
        self.assertEqual(parse_preferred_monitor(None, default="active"), "active")

        for invalid in ("monitor-0", 0, -1, "left-screen", True, []):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BrowserWindowConfigError):
                    parse_preferred_monitor(invalid)

    def test_parse_window_size_supports_strings_mappings_and_tuples(self):
        self.assertEqual(parse_window_size("1600x900"), WindowSize(1600, 900))
        self.assertEqual(parse_window_size("1920X1080"), WindowSize(1920, 1080))
        self.assertEqual(
            parse_window_size({"width": 1440, "height": 900}),
            WindowSize(1440, 900),
        )
        self.assertEqual(parse_window_size((1280, 720)), WindowSize(1280, 720))

        for invalid in ("100x100", "bad", {"width": "wide", "height": 900}, (True, 500)):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BrowserWindowConfigError):
                    parse_window_size(invalid)

    def test_parse_window_position_supports_presets_and_coordinates(self):
        self.assertEqual(parse_window_position("center"), WindowPosition("center"))
        self.assertEqual(parse_window_position("top-left"), WindowPosition("top-left"))
        self.assertEqual(parse_window_position("top_right"), WindowPosition("top-right"))
        self.assertEqual(
            parse_window_position("x=1920,y=0"),
            WindowPosition("coordinates", x=1920, y=0),
        )
        self.assertEqual(
            parse_window_position("320, 180"),
            WindowPosition("coordinates", x=320, y=180),
        )
        self.assertEqual(
            parse_window_position({"x": 1920, "y": 40}),
            WindowPosition("coordinates", x=1920, y=40),
        )

        for invalid in ("middle-ish", "x=abc,y=0", {"x": True, "y": 0}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BrowserWindowConfigError):
                    parse_window_position(invalid)

    def test_load_browser_window_config_precedence_cli_over_env_over_file(self):
        cfg_file = self.root / "config.json"
        cfg_file.write_text(
            json.dumps(
                {
                    "browser": {
                        "preferred_monitor": "primary",
                        "window_size": {"width": 1280, "height": 720},
                        "position": "top-left",
                    }
                }
            ),
            encoding="utf-8",
        )

        # 1. File config only
        from_file = load_browser_window_config(config_path=cfg_file, env={})
        self.assertEqual(from_file.preferred_monitor, "primary")
        self.assertEqual(from_file.window_size, WindowSize(1280, 720))
        self.assertEqual(from_file.position, WindowPosition("top-left"))

        # 2. Environment overrides file
        env_vars = {
            "JARVIS_PREFERRED_MONITOR": "monitor-2",
            "JARVIS_WINDOW_SIZE": "1600x900",
            "JARVIS_WINDOW_POSITION": "center",
        }
        from_env = load_browser_window_config(config_path=cfg_file, env=env_vars)
        self.assertEqual(from_env.preferred_monitor, "monitor-2")
        self.assertEqual(from_env.window_size, WindowSize(1600, 900))
        self.assertEqual(from_env.position, WindowPosition("center"))

        # 3. CLI arguments override environment and file
        cli_args = {
            "monitor": "active",
            "window_size": "1920x1080",
            "position": "x=1920,y=0",
        }
        from_cli = load_browser_window_config(
            cli_args=cli_args,
            config_path=cfg_file,
            env=env_vars,
        )
        self.assertEqual(from_cli.preferred_monitor, "active")
        self.assertEqual(from_cli.window_size, WindowSize(1920, 1080))
        self.assertEqual(from_cli.position, WindowPosition("coordinates", x=1920, y=0))

    def test_resolve_monitor_bounds_and_compute_geometry(self):
        monitors = [
            MonitorBounds(x=0, y=0, width=1920, height=1080, name="monitor-1", is_primary=True),
            MonitorBounds(x=1920, y=0, width=2560, height=1440, name="monitor-2", is_primary=False),
        ]
        self.assertEqual(
            resolve_monitor_bounds("primary", monitors=monitors),
            (0, 0, 1920, 1080),
        )
        self.assertEqual(
            resolve_monitor_bounds("monitor-2", monitors=monitors),
            (1920, 0, 2560, 1440),
        )
        self.assertEqual(
            resolve_monitor_bounds("active", monitors=monitors, active_bounds=(1920, 0, 2560, 1440)),
            (1920, 0, 2560, 1440),
        )

        centered_cfg = BrowserWindowConfig(
            preferred_monitor="monitor-2",
            window_size=WindowSize(1600, 900),
            position=WindowPosition("center"),
        )
        w, h, x, y = compute_window_geometry(
            centered_cfg,
            monitor_bounds=(1920, 0, 2560, 1440),
        )
        self.assertEqual((w, h, x, y), (1600, 900, 1920 + (2560 - 1600) // 2, (1440 - 900) // 2))
        self.assertEqual(
            build_chromium_window_args(centered_cfg, monitor_bounds=(1920, 0, 2560, 1440)),
            ["--window-size=1600,900", "--window-position=2400,270"],
        )

    def test_launcher_cli_and_open_url_in_slot_use_configured_window_geometry(self):
        cfg = jarvis_launcher.parse_launcher_cli_args(
            ["--monitor", "monitor-2", "--window-size", "1600x900", "--position", "center"]
        )
        self.assertEqual(cfg.preferred_monitor, "monitor-2")
        self.assertEqual(cfg.window_size, WindowSize(1600, 900))
        self.assertEqual(cfg.position, WindowPosition("center"))

        spawned_args: list[list[str]] = []

        class DummyProc:
            def terminate(self):
                pass

        with (
            mock.patch.object(jarvis_launcher, "find_chrome", return_value="/usr/bin/google-chrome"),
            mock.patch.object(
                jarvis_launcher,
                "_target_monitor_bounds",
                return_value=(1920, 0, 2560, 1440),
            ),
            mock.patch("jarvis_launcher.subprocess.Popen", side_effect=lambda args, **kw: (spawned_args.append(args), DummyProc())[1]),
        ):
            jarvis_launcher.open_url_in_slot("https://example.com", 0)

        self.assertEqual(len(spawned_args), 1)
        chrome_cmd = spawned_args[0]
        self.assertIn("--window-size=1600,900", chrome_cmd)
        self.assertIn("--window-position=2400,270", chrome_cmd)

    def test_browser_client_accepts_window_configuration_arguments(self):
        fake_ws_mod = sys.modules.get("websocket") or types.ModuleType("websocket")
        if not hasattr(fake_ws_mod, "WebSocketApp"):
            fake_ws_mod.WebSocketApp = object
        fake_pw_sync = types.ModuleType("playwright.sync_api")
        fake_pw_sync.sync_playwright = lambda: None
        fake_pw_sync.Page = object
        fake_pw_sync.Playwright = object
        fake_pw_pkg = types.ModuleType("playwright")
        fake_pw_pkg.sync_api = fake_pw_sync

        with mock.patch.dict(
            sys.modules,
            {
                "websocket": fake_ws_mod,
                "playwright": fake_pw_pkg,
                "playwright.sync_api": fake_pw_sync,
            },
        ):
            import importlib
            import browserClient

            importlib.reload(browserClient)

            client = browserClient.BrowserClient(
                ws_url="ws://localhost:8002/ws",
                headless=False,
                monitor="monitor-2",
                window_size="1600x900",
                position="x=1920,y=0",
            )
            self.assertEqual(client.window_config.preferred_monitor, "monitor-2")
            self.assertEqual(client.window_config.window_size.to_dict(), {"width": 1600, "height": 900})
            self.assertEqual(
                build_chromium_window_args(
                    client.window_config,
                    monitor_bounds=(1920, 0, 2560, 1440),
                ),
                ["--window-size=1600,900", "--window-position=3840,0"],
            )


if __name__ == "__main__":
    unittest.main()
