import tempfile
import unittest
from pathlib import Path

from cross_platform_packager import (
    PackagingError,
    build_pyinstaller_command,
    generate_linux_desktop_entry,
    generate_macos_plist,
    handle_package_payload,
    normalize_os,
)


class CrossPlatformPackagerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        (self.root / "jarvis_launcher.py").write_text("print('jarvis')", encoding="utf-8")
        (self.root / "jarvis_web.html").write_text("<html></html>", encoding="utf-8")
        (self.root / "jarvis_visual.html").write_text("<html></html>", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_normalize_os_supports_windows_macos_linux(self):
        self.assertEqual(normalize_os("windows"), "Windows")
        self.assertEqual(normalize_os("win32"), "Windows")
        self.assertEqual(normalize_os("macos"), "Darwin")
        self.assertEqual(normalize_os("darwin"), "Darwin")
        self.assertEqual(normalize_os("linux"), "Linux")
        with self.assertRaises(PackagingError):
            normalize_os("freebsd")

    def test_windows_plan_uses_semicolon_data_separator_and_exe(self):
        plan = build_pyinstaller_command(self.root, os_name="Windows", onefile=True)
        self.assertEqual(plan.os_name, "Windows")
        self.assertEqual(plan.data_sep, ";")
        self.assertIn("--onefile", plan.pyinstaller_cmd)
        self.assertIn("--windowed", plan.pyinstaller_cmd)
        self.assertTrue(plan.installer_artifact.endswith("JarvisAssistant-Setup-Windows.exe"))

    def test_macos_and_linux_plans_use_colon_separator_and_native_artifacts(self):
        mac = build_pyinstaller_command(self.root, os_name="Darwin", onefile=False)
        self.assertEqual(mac.data_sep, ":")
        self.assertIn("--onedir", mac.pyinstaller_cmd)
        self.assertTrue(mac.installer_artifact.endswith("JarvisAssistant-macOS.dmg"))

        lin = build_pyinstaller_command(self.root, os_name="Linux", onefile=True)
        self.assertEqual(lin.data_sep, ":")
        self.assertNotIn("--windowed", lin.pyinstaller_cmd)
        self.assertTrue(lin.installer_artifact.endswith("JarvisAssistant-Linux-x86_64.AppImage"))

    def test_manifests_and_dry_run_payload(self):
        desktop = generate_linux_desktop_entry()
        self.assertIn("[Desktop Entry]", desktop)
        plist = generate_macos_plist()
        self.assertIn("NSMicrophoneUsageDescription", plist)

        res = handle_package_payload({"project_root": str(self.root), "os_name": "Linux", "dry_run": True})
        self.assertFalse(res["executed"])
        self.assertEqual(res["os_name"], "Linux")


if __name__ == "__main__":
    unittest.main()
