"""
Unit tests validating the cross-platform packaging configuration for PG-AGI/toingg-jarvis (#13).
"""
import unittest
from pathlib import Path

PATCH_ROOT = Path(__file__).resolve().parent


class TestCrossPlatformPackaging(unittest.TestCase):
    def test_pyinstaller_spec_bundles_core_files(self) -> None:
        spec = (PATCH_ROOT / "packaging" / "jarvis.spec").read_text(encoding="utf-8")
        for req in ("jarvis_launcher.py", "jarvis_web.html", "jarvis_visual.html", "native_file_manager.py"):
            self.assertIn(req, spec)

    def test_windows_inno_setup_script(self) -> None:
        iss = (PATCH_ROOT / "packaging" / "windows" / "jarvis_installer.iss").read_text(encoding="utf-8")
        self.assertIn("toingg-jarvis.exe", iss)
        self.assertIn("[Setup]", iss)
        self.assertIn("[Files]", iss)

    def test_linux_deb_script(self) -> None:
        sh = (PATCH_ROOT / "packaging" / "linux" / "build_deb.sh").read_text(encoding="utf-8")
        self.assertIn("dpkg-deb --build", sh)
        self.assertIn("DEBIAN/control", sh)
        self.assertIn(".desktop", sh)

    def test_macos_dmg_script(self) -> None:
        sh = (PATCH_ROOT / "packaging" / "macos" / "build_dmg.sh").read_text(encoding="utf-8")
        self.assertIn("Info.plist", sh)
        self.assertIn("hdiutil create", sh)

    def test_github_actions_workflow_covers_all_three_os(self) -> None:
        wf = (PATCH_ROOT / ".github" / "workflows" / "release-installers.yml").read_text(encoding="utf-8")
        for runner in ("windows-latest", "ubuntu-latest", "macos-latest"):
            self.assertIn(runner, wf)


if __name__ == "__main__":
    unittest.main()
