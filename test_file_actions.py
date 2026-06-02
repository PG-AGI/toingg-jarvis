import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jarvis_launcher


class FileActionTests(unittest.TestCase):
    def test_platform_commands(self):
        target = os.path.abspath("demo.txt")

        self.assertEqual(
            jarvis_launcher._launch_native_path("open_directory", target, "Windows"),
            ["explorer", target],
        )
        self.assertEqual(
            jarvis_launcher._launch_native_path("reveal_file", target, "Darwin"),
            ["open", "-R", target],
        )
        self.assertEqual(
            jarvis_launcher._launch_native_path("open_file", target, "Linux"),
            ["xdg-open", target],
        )

    def test_run_file_actions_without_launching_real_apps(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td).resolve()
            file_path = folder / "report.txt"
            file_path.write_text("demo", encoding="utf-8")

            calls = []

            def fake_popen(args, **_kwargs):
                calls.append(args)

                class Proc:
                    pass

                return Proc()

            with patch.object(jarvis_launcher._plat, "system", return_value="Darwin"):
                with patch.object(jarvis_launcher.subprocess, "Popen", side_effect=fake_popen):
                    self.assertEqual(
                        jarvis_launcher.run_file_action("open_directory", str(folder)),
                        str(folder),
                    )
                    self.assertEqual(
                        jarvis_launcher.run_file_action("reveal_file", str(file_path)),
                        str(file_path),
                    )
                    self.assertEqual(
                        jarvis_launcher.run_file_action("open_file", str(file_path)),
                        str(file_path),
                    )

            self.assertEqual(
                calls,
                [
                    ["open", str(folder)],
                    ["open", "-R", str(file_path)],
                    ["open", str(file_path)],
                ],
            )

    def test_missing_file_errors(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing.txt"
            with self.assertRaises(FileNotFoundError):
                jarvis_launcher.run_file_action("open_file", str(missing))

    def test_invalid_payload_errors(self):
        with self.assertRaises(ValueError):
            jarvis_launcher.run_file_action("delete_file", ".")
        with self.assertRaises(ValueError):
            jarvis_launcher.run_file_action("open_directory", "")


if __name__ == "__main__":
    unittest.main()
