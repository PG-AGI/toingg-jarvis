import os
import tempfile
import unittest
from unittest.mock import patch

import jarvis_launcher


class FileManagerActionTests(unittest.TestCase):
    # 先验证三类文件管理器动作能生成对应平台命令。
    def test_open_directory_builds_platform_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("jarvis_launcher._plat.system", return_value="Darwin"):
                command = jarvis_launcher.build_file_manager_command(
                    "open_directory",
                    temp_dir,
                )

        self.assertEqual(command, ["open", temp_dir])

    def test_reveal_file_builds_platform_command(self):
        with tempfile.NamedTemporaryFile() as temp_file:
            with patch("jarvis_launcher._plat.system", return_value="Darwin"):
                command = jarvis_launcher.build_file_manager_command(
                    "reveal_file",
                    temp_file.name,
                )

        self.assertEqual(command, ["open", "-R", temp_file.name])

    def test_open_file_builds_platform_command(self):
        with tempfile.NamedTemporaryFile() as temp_file:
            with patch("jarvis_launcher._plat.system", return_value="Linux"):
                command = jarvis_launcher.build_file_manager_command(
                    "open_file",
                    temp_file.name,
                )

        self.assertEqual(command, ["xdg-open", temp_file.name])

    def test_rejects_missing_path(self):
        with self.assertRaisesRegex(ValueError, "path is required"):
            jarvis_launcher.build_file_manager_command("open_directory", "")

    def test_rejects_unknown_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "unsupported file manager action"):
                jarvis_launcher.build_file_manager_command("delete_file", temp_dir)

    def test_rejects_missing_local_path(self):
        # 在临时目录里构造不存在的子路径，避免和真实文件撞名。
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = os.path.join(temp_dir, "missing-file.txt")

            with self.assertRaisesRegex(FileNotFoundError, "local path does not exist"):
                jarvis_launcher.build_file_manager_command("open_file", missing_path)

    def test_open_directory_requires_directory(self):
        with tempfile.NamedTemporaryFile() as temp_file:
            with self.assertRaisesRegex(NotADirectoryError, "directory path required"):
                jarvis_launcher.build_file_manager_command(
                    "open_directory",
                    temp_file.name,
                )

    def test_open_file_requires_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(IsADirectoryError, "file path required"):
                jarvis_launcher.build_file_manager_command("open_file", temp_dir)


if __name__ == "__main__":
    unittest.main()
