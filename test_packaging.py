#!/usr/bin/env python3
"""
Unit tests for PG-AGI/toingg-jarvis#13 cross-platform native installer builder.
"""

import tempfile
import unittest
from pathlib import Path
from installers.build_installers import (
    APP_ID,
    APP_NAME,
    generate_inno_setup_script,
    stage_debian_tree,
    stage_macos_app_bundle,
)


class TestCrossPlatformPackaging(unittest.TestCase):

    def test_stage_debian_tree_creates_control_wrapper_and_desktop_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = stage_debian_tree(Path(tmp), version="1.2.0", arch="amd64")
            control = (pkg_dir / "DEBIAN" / "control").read_text(encoding="utf-8")
            self.assertIn("Package: jarvis-assistant", control)
            self.assertIn("Version: 1.2.0", control)
            self.assertIn("Architecture: amd64", control)

            wrapper = pkg_dir / "usr" / "bin" / "jarvis"
            self.assertTrue(wrapper.exists())
            self.assertTrue(wrapper.stat().st_mode & 0o111)

            desktop = (pkg_dir / "usr" / "share" / "applications" / "jarvis.desktop").read_text(encoding="utf-8")
            self.assertIn("Exec=/usr/bin/jarvis", desktop)

    def test_stage_macos_app_bundle_creates_plist_and_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = stage_macos_app_bundle(Path(tmp), version="1.2.0")
            plist = (app_dir / "Contents" / "Info.plist").read_text(encoding="utf-8")
            self.assertIn(f"<string>{APP_ID}</string>", plist)
            self.assertIn("<string>1.2.0</string>", plist)

            exe = app_dir / "Contents" / "MacOS" / APP_NAME
            self.assertTrue(exe.exists())
            self.assertTrue(exe.stat().st_mode & 0o111)

    def test_generate_inno_setup_script_outputs_valid_iss(self):
        with tempfile.TemporaryDirectory() as tmp:
            iss_path = generate_inno_setup_script(Path(tmp) / "jarvis.iss", version="1.2.0")
            content = iss_path.read_text(encoding="utf-8")
            self.assertIn("OutputBaseFilename=JARVIS-Setup-1.2.0-win64", content)
            self.assertIn(r'Filename: "{app}\jarvis.exe"', content)


if __name__ == "__main__":
    unittest.main()
