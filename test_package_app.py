import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import package_app


class PackageAppTests(unittest.TestCase):
    def test_platform_slug_normalizes_major_desktop_platforms(self):
        self.assertEqual(package_app.platform_slug("Darwin"), "macos")
        self.assertEqual(package_app.platform_slug("Linux"), "linux")
        self.assertEqual(package_app.platform_slug("Windows"), "windows")

    def test_executable_name_is_windows_specific(self):
        self.assertEqual(package_app.executable_name("Windows"), "toingg-jarvis.exe")
        self.assertEqual(package_app.executable_name("Linux"), "toingg-jarvis")

    def test_dry_run_invokes_pyinstaller_without_staging(self):
        with patch.object(package_app, "clean_outputs") as clean_outputs, \
                patch.object(package_app, "run") as run:
            result = package_app.build(platform_name="linux", dry_run=True)

        clean_outputs.assert_called_once()
        run.assert_called_once()
        self.assertIsNone(result)
        self.assertIn("PyInstaller", run.call_args.args[0])

    def test_zip_artifact_preserves_staged_folder_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            stage_dir = artifact_dir / "toingg-jarvis-linux"
            stage_dir.mkdir()
            (stage_dir / "toingg-jarvis").write_text("bin", encoding="utf-8")

            with patch.object(package_app, "ARTIFACT_DIR", artifact_dir):
                archive = package_app.zip_artifact(stage_dir, "linux")

            self.assertTrue(archive.exists())
            self.assertEqual(archive.name, "toingg-jarvis-linux.zip")


if __name__ == "__main__":
    unittest.main()
