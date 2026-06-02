import os
import tempfile
import unittest

from jarvis_launcher import (
    build_native_file_command,
    normalize_file_action,
    resolve_local_file_path,
)


class NativeFileManagerTests(unittest.TestCase):
    def test_action_aliases_are_canonical(self):
        self.assertEqual(normalize_file_action("open-folder"), "open_directory")
        self.assertEqual(normalize_file_action("show_in_folder"), "reveal_file")
        self.assertEqual(normalize_file_action("file"), "open_file")

    def test_resolve_default_directory_uses_home(self):
        resolved = resolve_local_file_path("", "open_directory")
        self.assertEqual(resolved, os.path.abspath(os.path.expanduser("~")))

    def test_rejects_missing_paths(self):
        with self.assertRaises(FileNotFoundError):
            resolve_local_file_path("/definitely/missing/jarvis-file.txt", "open_file")

    def test_macos_reveal_uses_open_dash_r(self):
        with tempfile.NamedTemporaryFile() as tmp:
            command = build_native_file_command("reveal_file", tmp.name, system="Darwin")
        self.assertEqual(command[:2], ["open", "-R"])

    def test_windows_reveal_uses_explorer_select(self):
        with tempfile.NamedTemporaryFile() as tmp:
            command = build_native_file_command("reveal_file", tmp.name, system="Windows")
        self.assertEqual(command[0], "explorer")
        self.assertTrue(command[1].startswith("/select,"))


if __name__ == "__main__":
    unittest.main()
