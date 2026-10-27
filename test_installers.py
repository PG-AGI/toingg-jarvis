import importlib.util
import ntpath
import os
import plistlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import jarvis_launcher

_ROOT = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("installers_build", os.path.join(_ROOT, "installers", "build.py"))
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def _add_data_source(item, sep):
    # Split on the last separator: a Windows source path has a drive-letter colon.
    return item.rsplit(sep, 1)[0]


class VersionTest(unittest.TestCase):
    def test_tags_are_normalized(self):
        self.assertEqual(build.normalize_version("v2.1.0"), "2.1.0")
        self.assertEqual(build.normalize_version("refs/tags/v2.1.0-rc1"), "2.1.0-rc1")
        self.assertEqual(build.normalize_version("3.0.0"), "3.0.0")

    def test_invalid_versions_are_rejected(self):
        for value in ("", "main", "v2.1", "2.1.0 ; rm -rf /"):
            with self.assertRaises(ValueError):
                build.normalize_version(value)

    def test_prerelease_sorts_before_release_in_debian(self):
        self.assertEqual(build.deb_version("2.1.0-rc1"), "2.1.0~rc1")
        self.assertEqual(build.deb_version("2.1.0"), "2.1.0")

    def test_default_version_matches_launcher(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(build.default_version(), jarvis_launcher._app_version(empty))

    def test_launcher_reads_bundled_version(self):
        with tempfile.TemporaryDirectory() as res:
            with open(os.path.join(res, "VERSION"), "w") as f:
                f.write("2.1.0-rc1\n")
            self.assertEqual(jarvis_launcher._app_version(res), "2.1.0-rc1")


class ArtifactTest(unittest.TestCase):
    def test_artifact_names(self):
        self.assertEqual(build.artifact_name("windows", "2.1.0"), "toingg-jarvis-2.1.0-windows-x64-setup.exe")
        self.assertEqual(build.artifact_name("linux", "2.1.0-rc1", "x86_64"), "toingg-jarvis_2.1.0~rc1_amd64.deb")
        self.assertEqual(build.artifact_name("linux", "2.1.0", "aarch64"), "toingg-jarvis_2.1.0_arm64.deb")
        self.assertEqual(build.artifact_name("macos", "2.1.0", "arm64"), "toingg-jarvis-2.1.0-macos-arm64.dmg")
        with self.assertRaises(ValueError):
            build.artifact_name("beos", "2.1.0")

    def test_target_for_host(self):
        self.assertEqual(build.target_for("Windows"), "windows")
        self.assertEqual(build.target_for("Linux"), "linux")
        self.assertEqual(build.target_for("Darwin"), "macos")
        self.assertIsNone(build.target_for("FreeBSD"))

    def test_deb_control(self):
        control = build.deb_control("2.1.0-rc1", "amd64", 1234)
        self.assertIn("Package: toingg-jarvis\n", control)
        self.assertIn("Version: 2.1.0~rc1\n", control)
        self.assertIn("Architecture: amd64\n", control)
        self.assertIn("Installed-Size: 1234\n", control)
        self.assertIn("libportaudio2", control)
        self.assertTrue(control.endswith("\n"))

    def test_info_plist(self):
        plist = build.info_plist("2.1.0-rc1")
        self.assertEqual(plist["CFBundleShortVersionString"], "2.1.0")
        self.assertEqual(plist["CFBundleVersion"], "2.1.0-rc1")
        self.assertEqual(plist["CFBundleExecutable"], "toingg-jarvis")
        self.assertIn("NSMicrophoneUsageDescription", plist)
        plistlib.dumps(plist)

    def test_pyinstaller_bundles_web_files_and_browser_client(self):
        args = build.pyinstaller_args("/tmp/VERSION", sep=":")
        data = [args[i + 1] for i, arg in enumerate(args) if arg == "--add-data"]
        bundled = {os.path.basename(_add_data_source(item, ":")) for item in data}
        self.assertTrue({"VERSION", "jarvis_web.html", "jarvis_visual.html"} <= bundled)
        for item in data:
            self.assertTrue(item.endswith(":."))
        self.assertIn("browserClient", args)
        self.assertIn("--console", args)
        self.assertNotIn("--codesign-identity", args)
        self.assertIn("--codesign-identity", build.pyinstaller_args("/tmp/VERSION", identity="Developer ID"))

    def test_add_data_source_keeps_windows_drive(self):
        source = _add_data_source("D:\\x\\jarvis_web.html:.", ":")
        self.assertEqual(source, "D:\\x\\jarvis_web.html")
        self.assertEqual(ntpath.basename(source), "jarvis_web.html")
        self.assertEqual(_add_data_source("/tmp/VERSION:.", ":"), "/tmp/VERSION")

    def test_data_files_exist(self):
        for name in build.DATA_FILES:
            self.assertTrue(os.path.exists(os.path.join(_ROOT, name)), name)
        self.assertTrue(os.path.exists(os.path.join(_ROOT, "installers", "windows", "jarvis.iss")))
        self.assertTrue(os.path.exists(os.path.join(_ROOT, "installers", "linux", "toingg-jarvis.desktop")))


class LauncherPathsTest(unittest.TestCase):
    def test_source_run_keeps_files_next_to_script(self):
        here = os.path.dirname(os.path.abspath(jarvis_launcher.__file__))
        self.assertEqual(jarvis_launcher._user_data_dir(frozen=False), here)

    def test_installed_build_uses_per_user_dir(self):
        home = os.path.expanduser("~")
        self.assertEqual(
            jarvis_launcher._user_data_dir("Windows", {"APPDATA": r"C:\Users\me\AppData\Roaming"}, frozen=True),
            os.path.join(r"C:\Users\me\AppData\Roaming", "Toingg JARVIS"),
        )
        self.assertEqual(
            jarvis_launcher._user_data_dir("Darwin", {}, frozen=True),
            os.path.join(home, "Library", "Application Support", "Toingg JARVIS"),
        )
        self.assertEqual(
            jarvis_launcher._user_data_dir("Linux", {"XDG_CONFIG_HOME": "/xdg"}, frozen=True),
            os.path.join("/xdg", "toingg-jarvis"),
        )
        self.assertEqual(
            jarvis_launcher._user_data_dir("Linux", {}, frozen=True),
            os.path.join(home, ".config", "toingg-jarvis"),
        )

    def test_browser_client_command(self):
        self.assertEqual(
            jarvis_launcher.browser_client_command(frozen=False)[1:],
            [jarvis_launcher.BROWSER_CLIENT],
        )
        self.assertEqual(jarvis_launcher.browser_client_command(frozen=True)[1:], ["--browser-client"])

    def test_frozen_build_uses_per_user_playwright_browsers(self):
        expected = os.path.join(jarvis_launcher._DIR, "ms-playwright")
        env = {}
        self.assertEqual(jarvis_launcher.configure_playwright_browsers_path(env, frozen=True), expected)
        self.assertEqual(env, {"PLAYWRIGHT_BROWSERS_PATH": expected})

        env = {"PLAYWRIGHT_BROWSERS_PATH": "/custom"}
        self.assertEqual(jarvis_launcher.configure_playwright_browsers_path(env, frozen=True), "/custom")

        env = {}
        self.assertIsNone(jarvis_launcher.configure_playwright_browsers_path(env, frozen=False))
        self.assertEqual(env, {})

    def test_chromium_install_uses_launch_browsers_path(self):
        driver = types.ModuleType("playwright._impl._driver")
        driver.compute_driver_executable = lambda: ("/bundle/node", "/bundle/cli.js")
        driver.get_driver_env = lambda: {"PLAYWRIGHT_BROWSERS_PATH": "0", "PW_LANG_NAME": "python"}
        modules = {
            "playwright": types.ModuleType("playwright"),
            "playwright._impl": types.ModuleType("playwright._impl"),
            "playwright._impl._driver": driver,
        }
        expected = os.path.join(jarvis_launcher._DIR, "ms-playwright")
        with patch.dict(sys.modules, modules), patch.dict(os.environ, clear=True), \
                patch.object(sys, "frozen", True, create=True), \
                patch.object(jarvis_launcher.subprocess, "run") as mock_run:
            jarvis_launcher.ensure_playwright_chromium()
            self.assertEqual(os.environ["PLAYWRIGHT_BROWSERS_PATH"], expected)
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd, ["/bundle/node", "/bundle/cli.js", "install", "chromium"])
        self.assertEqual(mock_run.call_args.kwargs["env"]["PLAYWRIGHT_BROWSERS_PATH"], expected)

    def test_version_flag(self):
        with patch("builtins.print") as mock_print, patch.object(jarvis_launcher, "main") as mock_main:
            jarvis_launcher.run(["--version"])
        mock_main.assert_not_called()
        mock_print.assert_called_once_with(f"Toingg JARVIS {jarvis_launcher.APP_VERSION}")


if __name__ == "__main__":
    unittest.main()
