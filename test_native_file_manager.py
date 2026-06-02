import tempfile
import unittest
from pathlib import Path
from unittest import mock

from native_file_manager import (
    FileManagerError,
    build_file_manager_command,
    open_in_file_manager,
)


class NativeFileManagerTests(unittest.TestCase):
    def test_windows_reveal_selects_existing_file(self):
        with tempfile.NamedTemporaryFile() as tmp:
            command = build_file_manager_command(tmp.name, action="reveal", system="Windows")

        self.assertEqual(command[0], "explorer")
        self.assertTrue(command[1].startswith("/select,"))
        self.assertIn(Path(tmp.name).name, command[1])

    def test_macos_reveal_uses_open_r(self):
        with tempfile.NamedTemporaryFile() as tmp:
            command = build_file_manager_command(tmp.name, action="reveal", system="Darwin")

        self.assertEqual(command, ["open", "-R", str(Path(tmp.name).resolve())])

    def test_linux_reveal_opens_parent_directory_for_files(self):
        with tempfile.NamedTemporaryFile() as tmp:
            command = build_file_manager_command(tmp.name, action="reveal", system="Linux")

        self.assertEqual(command, ["xdg-open", str(Path(tmp.name).resolve().parent)])

    def test_open_directory_uses_platform_file_manager(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = build_file_manager_command(tmp, system="Linux")

        self.assertEqual(command, ["xdg-open", str(Path(tmp).resolve())])

    def test_missing_path_is_rejected(self):
        with self.assertRaises(FileManagerError):
            build_file_manager_command("/definitely/not/here")

    def test_open_in_file_manager_launches_built_command(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("subprocess.Popen") as popen:
            open_in_file_manager(tmp)

        popen.assert_called_once_with(["xdg-open", str(Path(tmp).resolve())])


if __name__ == "__main__":
    unittest.main()
