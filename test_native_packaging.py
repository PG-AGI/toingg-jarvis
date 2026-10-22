"""Regression checks for issue #13 native paths and deterministic packaging."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import jarvis_launcher

BUILD_DEB = Path(__file__).parent / "packaging" / "linux" / "build_deb.py"
SPEC = importlib.util.spec_from_file_location("jarvis_build_deb", BUILD_DEB)
build_deb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_deb)


class FrozenRuntimeTests(unittest.TestCase):
    def test_resource_dir_uses_unpack_path_only_when_frozen(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "_MEIPASS", "/test/bundle", create=True
        ):
            self.assertEqual(jarvis_launcher._resources_dir(), "/test/bundle")
        self.assertEqual(jarvis_launcher._resources_dir(), jarvis_launcher._DIR)

    def test_source_checkout_keeps_existing_config_location(self):
        self.assertEqual(
            jarvis_launcher._config_path(),
            str(Path(jarvis_launcher.__file__).parent / "config.json"),
        )

    def test_native_state_locations_for_all_three_platforms(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(sys, "frozen", True, create=True):
                with patch.object(jarvis_launcher._plat, "system", return_value="Windows"):
                    with patch.dict(os.environ, {"APPDATA": temp}):
                        self.assertEqual(
                            jarvis_launcher._config_path(),
                            str(Path(temp) / "JARVIS" / "config.json"),
                        )
                with patch.object(jarvis_launcher._plat, "system", return_value="Darwin"):
                    with patch.dict(os.environ, {"HOME": temp}):
                        self.assertEqual(
                            jarvis_launcher._config_path(),
                            str(Path(temp) / "Library" / "Application Support" / "JARVIS" / "config.json"),
                        )
                with patch.object(jarvis_launcher._plat, "system", return_value="Linux"):
                    with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp}):
                        self.assertEqual(
                            jarvis_launcher._config_path(),
                            str(Path(temp) / "jarvis" / "config.json"),
                        )

    def test_native_config_writes_only_to_writable_user_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "state"
            with patch.object(jarvis_launcher, "_writable_state_dir", return_value=str(state)):
                jarvis_launcher._save_token("test-token-value-with-24chars")
                self.assertEqual(jarvis_launcher._load_token(), "test-token-value-with-24chars")
                self.assertTrue((state / "config.json").is_file())
                if os.name != "nt":
                    self.assertEqual(stat.S_IMODE((state / "config.json").stat().st_mode), 0o600)

    def test_native_browser_client_uses_bundled_executable_and_writable_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(sys, "frozen", True, create=True), patch.object(
                jarvis_launcher, "_writable_state_dir", return_value=temp
            ), patch.object(jarvis_launcher, "_browser_client_proc", None), patch.object(
                jarvis_launcher.subprocess, "Popen"
            ) as popen:
                jarvis_launcher.start_browser_client()
                popen.assert_called_once_with([sys.executable, "--browser-client"], cwd=temp)

    def test_version_and_help_do_not_prompt_for_api_key(self):
        for args, expected in ((["--help"], "Usage"), (["--version"], "2.0.0")):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), patch.object(
                jarvis_launcher, "check_api_key", side_effect=AssertionError("prompted")
            ):
                self.assertTrue(jarvis_launcher._dispatch_cli(args))
            self.assertIn(expected, output.getvalue())

    def test_browser_client_switch_restores_argv(self):
        fake = types.ModuleType("browserClient")
        seen = []
        fake.main = lambda: seen.append(list(sys.argv))
        before = list(sys.argv)
        with patch.dict(sys.modules, {"browserClient": fake}):
            self.assertTrue(jarvis_launcher._dispatch_cli(["--browser-client", "--help"]))
        self.assertEqual(seen[0][1:], ["--help"])
        self.assertEqual(sys.argv, before)


class DebianStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bundle = self.base / "bundle"
        self.bundle.mkdir()
        (self.bundle / "JARVIS").write_bytes(b"#!/bin/sh\nexit 0\n")
        (self.bundle / "JARVIS").chmod(0o755)
        (self.bundle / "_internal").mkdir()
        (self.bundle / "_internal" / "jarvis_web.html").write_text("<html></html>")
        self.stage = self.base / "stage"

    def test_stage_contents_and_metadata(self):
        build_deb.make_stage(self.bundle, self.stage, "2.0.0", "amd64")
        self.assertEqual((self.stage / "opt/jarvis/JARVIS").read_bytes(), (self.bundle / "JARVIS").read_bytes())
        self.assertTrue((self.stage / "opt/jarvis/_internal/jarvis_web.html").is_file())
        self.assertIn("Architecture: amd64", (self.stage / "DEBIAN/control").read_text())
        self.assertIn("exec /opt/jarvis/JARVIS", (self.stage / "usr/bin/jarvis").read_text())
        self.assertEqual(stat.S_IMODE((self.stage / "usr/bin/jarvis").stat().st_mode), 0o755)
        self.assertIn("Terminal=true", (self.stage / "usr/share/applications/jarvis.desktop").read_text())

    def test_arm64_is_supported(self):
        build_deb.make_stage(self.bundle, self.stage, "2.0.0", "arm64")
        self.assertIn("Architecture: arm64", (self.stage / "DEBIAN/control").read_text())

    def test_invalid_version_or_architecture_does_not_create_stage(self):
        with self.assertRaises(ValueError):
            build_deb.make_stage(self.bundle, self.stage, "../../foo", "amd64")
        self.assertFalse(self.stage.exists())
        with self.assertRaises(ValueError):
            build_deb.make_stage(self.bundle, self.stage, "2.0.0", "mips")
        self.assertFalse(self.stage.exists())

    def test_refuses_missing_executable_and_existing_stage(self):
        (self.bundle / "JARVIS").unlink()
        with self.assertRaises(FileNotFoundError):
            build_deb.make_stage(self.bundle, self.stage, "2.0.0", "amd64")
        (self.bundle / "JARVIS").write_text("x")
        (self.bundle / "JARVIS").chmod(0o755)
        self.stage.mkdir()
        with self.assertRaises(FileExistsError):
            build_deb.make_stage(self.bundle, self.stage, "2.0.0", "amd64")


if __name__ == "__main__":
    unittest.main()
