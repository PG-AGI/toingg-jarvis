import unittest
from unittest.mock import patch

import jarvis_launcher as j


class BrowserWindowConfigurationTests(unittest.TestCase):
    def test_default_matches_existing_grid_settings(self):
        self.assertEqual(j._browser_window_options({}), (860, 580, "active", "grid"))

    def test_parses_size_position_and_monitor(self):
        self.assertEqual(
            j._browser_window_options({
                "JARVIS_WINDOW_SIZE": "1600x900",
                "JARVIS_WINDOW_POSITION": "center",
                "JARVIS_WINDOW_MONITOR": "primary",
            }),
            (1600, 900, "primary", "center"),
        )

    def test_rejects_invalid_options(self):
        cases = [
            {"JARVIS_WINDOW_SIZE": "huge"},
            {"JARVIS_WINDOW_SIZE": "100x100"},
            {"JARVIS_WINDOW_SIZE": "99999x100"},
            {"JARVIS_WINDOW_POSITION": "off"},
            {"JARVIS_WINDOW_POSITION": "900000,500"},
            {"JARVIS_WINDOW_MONITOR": "monitor-99"},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                j._browser_window_options(case)

    def test_primary_center_uses_primary_desktop_bounds(self):
        with patch.object(j, "get_screen_size", return_value=(1920, 1080)), patch.object(
            j, "get_active_screen_bounds", side_effect=AssertionError("not primary")
        ):
            self.assertEqual(
                j._configured_window_geometry(2, (1600, 900, "primary", "center")),
                (1600, 900, 160, 90),
            )

    def test_active_window_clamps_grid_to_monitor(self):
        with patch.object(j, "get_active_screen_bounds", return_value=(1920, -200, 1200, 800)):
            self.assertEqual(
                j._configured_window_geometry(3, (860, 580, "active", "grid")),
                (860, 580, 2260, 20),
            )

    def test_explicit_absolute_coordinates_are_clamped(self):
        with patch.object(j, "get_active_screen_bounds", return_value=(1920, 0, 1200, 800)):
            self.assertEqual(
                j._configured_window_geometry(0, (860, 580, "active", "999,999")),
                (860, 580, 1920, 220),
            )

    def test_size_larger_than_display_is_reduced(self):
        with patch.object(j, "get_active_screen_bounds", return_value=(0, 0, 700, 400)):
            self.assertEqual(
                j._configured_window_geometry(0, (1200, 900, "active", "center")),
                (700, 400, 0, 0),
            )


if __name__ == "__main__":
    unittest.main()
