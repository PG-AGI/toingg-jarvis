# -*- coding: utf-8 -*-
"""Unit tests for WindowConfig (Issue #8)."""
import unittest
from window_config import WindowConfig

class TestWindowConfig(unittest.TestCase):
    def test_default_size_and_position(self):
        cfg = WindowConfig()
        self.assertEqual(cfg.parse_size(), (1366, 768))
        self.assertIsNone(cfg.parse_position())
        self.assertEqual(cfg.get_chromium_args(), ["--window-size=1366,768"])
        self.assertEqual(cfg.get_viewport(), {"width": 1366, "height": 768})

    def test_custom_size(self):
        cfg = WindowConfig(window_size="1600x900")
        self.assertEqual(cfg.parse_size(), (1600, 900))
        self.assertEqual(cfg.get_viewport(), {"width": 1600, "height": 900})
        self.assertIn("--window-size=1600,900", cfg.get_chromium_args())

    def test_position_presets(self):
        cfg_tl = WindowConfig(window_size="1600x900", position="top-left")
        self.assertEqual(cfg_tl.parse_position(1600, 900), (0, 0))
        self.assertIn("--window-position=0,0", cfg_tl.get_chromium_args())

        cfg_center = WindowConfig(window_size="1600x900", position="center")
        pos = cfg_center.parse_position(1600, 900)
        self.assertEqual(pos, (160, 90))
        self.assertIn("--window-position=160,90", cfg_center.get_chromium_args())

    def test_explicit_coordinates(self):
        cfg = WindowConfig(position="x=1920,y=0")
        self.assertEqual(cfg.parse_position(), (1920, 0))
        self.assertIn("--window-position=1920,0", cfg.get_chromium_args())

        cfg2 = WindowConfig(position="200,300")
        self.assertEqual(cfg2.parse_position(), (200, 300))
        self.assertIn("--window-position=200,300", cfg2.get_chromium_args())

    def test_multi_monitor_offset(self):
        cfg = WindowConfig(window_size="1920x1080", position="top-left", monitor="monitor-2")
        pos = cfg.parse_position(1920, 1080)
        self.assertEqual(pos, (1920, 0))
        self.assertIn("--window-position=1920,0", cfg.get_chromium_args())

if __name__ == "__main__":
    unittest.main()
