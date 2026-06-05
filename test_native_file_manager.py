import tempfile
import unittest
from pathlib import Path

from native_file_manager import (
    NativeFileActionError,
    build_file_manager_command,
    handle_file_action_payload,
    plan_file_action,
)


class NativeFileManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.file_path = self.root / "notes.txt"
        self.file_path.write_text("hello", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_open_directory_commands_are_cross_platform(self):
        self.assertEqual(
            build_file_manager_command("open_directory", str(self.root), "Windows"),
            ["explorer", str(self.root.resolve())],
        )
        self.assertEqual(
            build_file_manager_command("open_directory", str(self.root), "Darwin"),
            ["open", str(self.root.resolve())],
        )
        self.assertEqual(
            build_file_manager_command("open_directory", str(self.root), "Linux"),
            ["xdg-open", str(self.root.resolve())],
        )

    def test_reveal_file_uses_native_selection_or_parent_directory(self):
        self.assertEqual(
            build_file_manager_command("reveal_file", str(self.file_path), "Windows"),
            ["explorer", f"/select,{self.file_path.resolve()}"],
        )
        self.assertEqual(
            build_file_manager_command("reveal_file", str(self.file_path), "Darwin"),
            ["open", "-R", str(self.file_path.resolve())],
        )
        self.assertEqual(
            build_file_manager_command("reveal_file", str(self.file_path), "Linux"),
            ["xdg-open", str(self.root.resolve())],
        )

    def test_open_file_builds_default_app_command(self):
        self.assertEqual(
            build_file_manager_command("open_file", str(self.file_path), "Windows"),
            ["cmd", "/c", "start", "", str(self.file_path.resolve())],
        )
        self.assertEqual(
            build_file_manager_command("open_file", str(self.file_path), "Darwin"),
            ["open", str(self.file_path.resolve())],
        )
        self.assertEqual(
            build_file_manager_command("open_file", str(self.file_path), "Linux"),
            ["xdg-open", str(self.file_path.resolve())],
        )

    def test_payload_handler_supports_dry_run(self):
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
        with self.assertRaises(NativeFileActionError):
            plan_file_action("delete_file", str(self.file_path))
        with self.assertRaises(NativeFileActionError):
            plan_file_action("open_directory", str(self.file_path))
        with self.assertRaises(NativeFileActionError):
            plan_file_action("open_file", str(self.root))
        with self.assertRaises(NativeFileActionError):
            handle_file_action_payload([])


if __name__ == "__main__":
    unittest.main()
