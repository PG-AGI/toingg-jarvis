"""Unit tests for cross-platform packaging, frozen asset lookup, and native installers."""

from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from packaging.installer_builder import (
    PackageMetadata,
    build_deb_package,
    build_platform_artifacts,
    render_windows_inno_script,
    render_windows_nsis_script,
    resolve_bundle_root,
    resolve_runtime_asset,
    resolve_user_config_dir,
    stage_linux_deb_tree,
    stage_macos_app_bundle,
)


class TestPackagingInstallers(unittest.TestCase):
    """Verify asset path resolution and native installer generation for all target OSes."""

    def test_resolve_bundle_root_prefers_frozen_meipass(self) -> None:
        """Verify PyInstaller _MEIPASS directory takes precedence when running frozen."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sys, "_MEIPASS", tmp, create=True):
                resolved = resolve_bundle_root()
                self.assertEqual(resolved, Path(tmp).resolve())
                asset = resolve_runtime_asset("jarvis_web.html")
                self.assertEqual(asset, Path(tmp).resolve() / "jarvis_web.html")

    def test_resolve_runtime_asset_rejects_path_traversal(self) -> None:
        """Verify relative path traversal sequences are rejected during asset lookup."""
        with self.assertRaises(ValueError):
            resolve_runtime_asset("../outside.txt")

    def test_resolve_user_config_dir_across_operating_systems(self) -> None:
        """Verify OS-specific writable config paths for Windows, macOS, and Linux."""
        env = {
            "HOME": "/home/alice",
            "APPDATA": "C:/Users/alice/AppData/Roaming",
            "XDG_CONFIG_HOME": "/home/alice/.xdg",
        }
        win_dir = resolve_user_config_dir("win32", env)
        mac_dir = resolve_user_config_dir("darwin", env)
        linux_dir = resolve_user_config_dir("linux", env)

        self.assertTrue(str(win_dir).endswith("ToinggJarvis"))
        self.assertEqual(
            mac_dir,
            Path("/home/alice/Library/Application Support/ToinggJarvis"),
        )
        self.assertEqual(linux_dir, Path("/home/alice/.xdg/toingg-jarvis"))

    def test_stage_and_build_linux_deb_package(self) -> None:
        """Verify Debian .deb staging layout and valid GNU ar archive header generation."""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            meta = PackageMetadata(version="2.1.0")
            stage_dir = stage_linux_deb_tree(out_dir, meta)
            control_text = (stage_dir / "DEBIAN" / "control").read_text(encoding="utf-8")
            self.assertIn("Package: toingg-jarvis", control_text)
            self.assertIn("Version: 2.1.0", control_text)

            deb_path = out_dir / "toingg-jarvis_2.1.0_amd64.deb"
            build_deb_package(stage_dir, deb_path)
            raw_deb = deb_path.read_bytes()
            self.assertTrue(raw_deb.startswith(b"!<arch>\ndebian-binary"))
            self.assertIn(b"control.tar.gz", raw_deb)
            self.assertIn(b"data.tar.gz", raw_deb)

    def test_stage_macos_app_bundle_creates_valid_plist(self) -> None:
        """Verify macOS .app bundle directory hierarchy and Info.plist metadata keys."""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            meta = PackageMetadata(version="2.1.0")
            app_dir = stage_macos_app_bundle(out_dir, meta)
            plist_path = app_dir / "Contents" / "Info.plist"
            self.assertTrue(plist_path.is_file())
            with plist_path.open("rb") as fp:
                plist_data = plistlib.load(fp)
            self.assertEqual(plist_data["CFBundleIdentifier"], "com.pgagi.toingg-jarvis")
            self.assertEqual(plist_data["CFBundleShortVersionString"], "2.1.0")
            launcher_bin = app_dir / "Contents" / "MacOS" / "toingg-jarvis"
            self.assertTrue(launcher_bin.is_file())

    def test_windows_installer_scripts_and_all_platform_build(self) -> None:
        """Verify Inno Setup, NSIS scripts, and multi-platform artifact builder output."""
        meta = PackageMetadata(version="2.0.0")
        inno = render_windows_inno_script(meta)
        nsis = render_windows_nsis_script(meta)
        self.assertIn("OutputBaseFilename=toingg-jarvis-2.0.0-windows-setup", inno)
        self.assertIn('OutFile "toingg-jarvis-2.0.0-windows-setup.exe"', nsis)

        with tempfile.TemporaryDirectory() as tmp:
            built = build_platform_artifacts(tmp, "all")
            self.assertIn("linux_deb", built)
            self.assertIn("macos_archive", built)
            self.assertIn("portable_zip", built)
            self.assertTrue(Path(built["linux_deb"]).is_file())
            self.assertTrue(Path(built["macos_archive"]).is_file())
            self.assertTrue(Path(built["portable_zip"]).is_file())


if __name__ == "__main__":
    unittest.main()
