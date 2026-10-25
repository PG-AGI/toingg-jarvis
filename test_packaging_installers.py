# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from installers import build_installers


class TestCrossPlatformPackaging(unittest.TestCase):
    def test_normalize_version(self):
        self.assertEqual(build_installers.normalize_version("v2.1.0"), "2.1.0")
        self.assertEqual(build_installers.normalize_version("2.0.0"), "2.0.0")
        self.assertEqual(build_installers.normalize_version(""), "2.0.0")

    def test_debian_staging_structure_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bundle = tmp_path / "bundle"
            fake_bundle.mkdir()
            (fake_bundle / "toingg-jarvis").write_text("binary-placeholder", encoding="utf-8")

            pkg_root = build_installers.stage_debian_tree(tmp_path / "stage", fake_bundle, "2.0.0", "amd64")
            control = (pkg_root / "DEBIAN" / "control").read_text(encoding="utf-8")
            self.assertIn("Package: toingg-jarvis", control)
            self.assertIn("Version: 2.0.0", control)
            self.assertIn("Architecture: amd64", control)
            self.assertTrue((pkg_root / "usr" / "bin" / "toingg-jarvis").exists())
            self.assertTrue((pkg_root / "usr" / "share" / "applications" / "toingg-jarvis.desktop").exists())
            self.assertTrue((pkg_root / "opt" / "toingg-jarvis" / "toingg-jarvis").exists())

    def test_sha256_manifest_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst_dir = Path(tmp)
            sample = inst_dir / "toingg-jarvis_2.0.0_amd64.deb"
            sample.write_bytes(b"toingg-jarvis-installer-payload")

            manifest = build_installers.compute_sha256_manifest(inst_dir)
            self.assertIn("toingg-jarvis_2.0.0_amd64.deb", manifest)
            sums_file = inst_dir / "SHA256SUMS.txt"
            self.assertTrue(sums_file.exists())
            self.assertIn(manifest["toingg-jarvis_2.0.0_amd64.deb"], sums_file.read_text(encoding="utf-8"))

    def test_packaging_configurations_exist(self):
        root = build_installers.ROOT_DIR
        self.assertTrue((root / "installers" / "toingg_jarvis.spec").exists())
        self.assertTrue((root / "installers" / "windows_installer.iss").exists())
        self.assertTrue((root / "installers" / "release-installers.yml").exists())


if __name__ == "__main__":
    unittest.main()
