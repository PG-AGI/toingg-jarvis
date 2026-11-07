"""Unit tests for cross-platform native file manager validation and command building.

Verifies OS command generation across Windows, macOS, and Linux as well as
strict input validation rejecting unhashable or non-string action payloads
before any subprocess can be spawned.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native_file_manager import (
    NativeFileActionError,
    build_file_manager_command,
    handle_file_action_payload,
    plan_file_action,
)


class NativeFileManagerTests(unittest.TestCase):
    """Test suite covering file action command generation and payload validation."""

    def setUp(self):
        """Create an isolated temporary directory and sample file for each test."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.file_path = self.root / "notes.txt"
        self.file_path.write_text("hello", encoding="utf-8")

    def tearDown(self):
        """Remove the temporary directory after test execution."""
        self.tmpdir.cleanup()

    def _assert_os_commands(self, action_target, expected_by_os):
        """Verify command vectors across Windows, Darwin, and Linux for a given action and path."""
        action, path_str = action_target
        for system_name, expected_cmd in expected_by_os.items():
            actual = build_file_manager_command(action, path_str, system_name)
            self.assertEqual(actual, expected_cmd)

    def test_open_directory_commands_are_cross_platform(self):
        """Verify open_directory resolves to Explorer, Finder, or xdg-open per OS."""
        resolved_root = str(self.root.resolve())
        self._assert_os_commands(
            ("open_directory", str(self.root)),
            {
                "Windows": ["explorer", resolved_root],
                "Darwin": ["open", resolved_root],
                "Linux": ["xdg-open", resolved_root],
            },
        )

    def test_reveal_file_uses_native_selection_or_parent_directory(self):
        """Verify reveal_file selects the file on Windows/macOS and opens parent on Linux."""
        resolved_file = str(self.file_path.resolve())
        resolved_root = str(self.root.resolve())
        self._assert_os_commands(
            ("reveal_file", str(self.file_path)),
            {
                "Windows": ["explorer", f"/select,{resolved_file}"],
                "Darwin": ["open", "-R", resolved_file],
                "Linux": ["xdg-open", resolved_root],
            },
        )

    def test_open_file_builds_default_app_command(self):
        """Verify open_file dispatches to the OS default application launcher."""
        resolved_file = str(self.file_path.resolve())
        self._assert_os_commands(
            ("open_file", str(self.file_path)),
            {
                "Windows": ["cmd", "/c", "start", "", resolved_file],
                "Darwin": ["open", resolved_file],
                "Linux": ["xdg-open", resolved_file],
            },
        )

    def test_payload_handler_supports_dry_run(self):
        """Verify handle_file_action_payload returns the planned command in dry_run mode."""
        result = handle_file_action_payload(
            {
                "action": "open_file",
                "path": str(self.file_path),
                "dry_run": True,
            }
        )

        self.assertEqual(result["action"], "open_file")
        self.assertEqual(result["path"], str(self.file_path.resolve()))
        self.assertIn(str(self.file_path.resolve()), result["command"])

    def test_validation_rejects_invalid_actions_and_paths(self):
        """Verify unsupported action strings, empty strings, and mismatched path types fail."""
        invalid_plans = (
            ("delete_file", str(self.file_path)),
            ("", str(self.file_path)),
            ("open_directory", str(self.file_path)),
            ("open_file", str(self.root)),
        )
        for action, target in invalid_plans:
            with self.subTest(action=action, target=target):
                with self.assertRaises(NativeFileActionError):
                    plan_file_action(action, target)

        with self.assertRaises(NativeFileActionError):
            handle_file_action_payload([])

    def test_non_string_actions_raise_validation_error_without_launching(self):
        """Verify unhashable and non-string actions raise NativeFileActionError without Popen."""
        invalid_actions = ([], {}, ["open_file"], {"name": "open_file"}, None, 1, True)
        for action in invalid_actions:
            with self.subTest(action=action), patch("native_file_manager.subprocess.Popen") as popen:
                with self.assertRaises(NativeFileActionError):
                    handle_file_action_payload({"action": action, "path": str(self.file_path)})
                popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
