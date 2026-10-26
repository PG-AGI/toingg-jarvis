import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_BUILD_PKG_PATH = Path(__file__).resolve().parent / "packaging" / "build_package.py"
_SPEC = importlib.util.spec_from_file_location("jarvis_build_package", _BUILD_PKG_PATH)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

APP_ID = _MOD.APP_ID
APP_NAME = _MOD.APP_NAME
REQUIRED_ASSETS = _MOD.REQUIRED_ASSETS
build_pyinstaller_args = _MOD.build_pyinstaller_args
generate_pyinstaller_spec = _MOD.generate_pyinstaller_spec
get_data_separator = _MOD.get_data_separator
get_installer_metadata = _MOD.get_installer_metadata
get_repo_root = _MOD.get_repo_root
normalize_platform = _MOD.normalize_platform
run_build = _MOD.run_build
verify_required_assets = _MOD.verify_required_assets


class TestCrossPlatformPackaging(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = get_repo_root()

    def test_01_normalize_platform_variants(self) -> None:
        self.assertEqual(normalize_platform("windows"), "windows")
        self.assertEqual(normalize_platform("Win32"), "windows")
        self.assertEqual(normalize_platform("macos"), "macos")
        self.assertEqual(normalize_platform("Darwin"), "macos")
        self.assertEqual(normalize_platform("linux"), "linux")
        self.assertEqual(normalize_platform("ubuntu"), "linux")
        with self.assertRaises(ValueError):
            normalize_platform("freebsd-unknown")

    def test_02_verify_required_assets_in_repo(self) -> None:
        verified = verify_required_assets(self.repo_root)
        for asset in REQUIRED_ASSETS:
            self.assertIn(asset, verified)
            self.assertTrue(Path(verified[asset]).is_file())

    def test_03_verify_required_assets_raises_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "jarvis_launcher.py").write_text("# stub", encoding="utf-8")
            with self.assertRaises(FileNotFoundError) as ctx:
                verify_required_assets(tmp_path)
            self.assertIn("jarvis_web.html", str(ctx.exception))

    def test_04_pyinstaller_args_windows_uses_semicolon_separator(self) -> None:
        args = build_pyinstaller_args(platform_name="windows", root_dir=self.repo_root)
        self.assertEqual(get_data_separator("windows"), ";")
        add_data_flags = [a for a in args if a.startswith("--add-data=")]
        self.assertGreaterEqual(len(add_data_flags), 5)
        for flag in add_data_flags:
            self.assertIn(";.", flag)
        self.assertIn("--onedir", args)

    def test_05_pyinstaller_args_macos_and_linux_use_colon_separator(self) -> None:
        mac_args = build_pyinstaller_args(platform_name="macos", root_dir=self.repo_root)
        linux_args = build_pyinstaller_args(platform_name="linux", root_dir=self.repo_root, onefile=True)
        self.assertIn(f"--osx-bundle-identifier={APP_ID}", mac_args)
        self.assertIn("--onefile", linux_args)
        for flag in [a for a in mac_args if a.startswith("--add-data=")]:
            self.assertIn(":.", flag)
        for flag in [a for a in linux_args if a.startswith("--add-data=")]:
            self.assertIn(":.", flag)

    def test_06_generate_pyinstaller_spec_all_platforms(self) -> None:
        win_spec = generate_pyinstaller_spec("windows", root_dir=self.repo_root, version="2.1.0")
        mac_spec = generate_pyinstaller_spec("macos", root_dir=self.repo_root, version="2.1.0")
        lin_spec = generate_pyinstaller_spec("linux", root_dir=self.repo_root, version="2.1.0")

        self.assertIn("jarvis_launcher.py", win_spec)
        self.assertIn("jarvis_web.html", win_spec)
        self.assertNotIn("BUNDLE(", win_spec)
        self.assertNotIn("BUNDLE(", lin_spec)

        self.assertIn("BUNDLE(", mac_spec)
        self.assertIn("NSMicrophoneUsageDescription", mac_spec)
        self.assertIn(APP_ID, mac_spec)

    def test_07_installer_metadata_per_platform(self) -> None:
        win_meta = get_installer_metadata("windows", version="2.0.0", root_dir=self.repo_root)
        mac_meta = get_installer_metadata("macos", version="2.0.0", root_dir=self.repo_root)
        lin_meta = get_installer_metadata("linux", version="2.0.0", root_dir=self.repo_root)

        self.assertEqual(win_meta["installer_type"], "inno_setup_exe")
        self.assertTrue(str(win_meta["artifact_path"]).endswith("JARVIS-Setup-2.0.0-Windows-x64.exe"))
        self.assertTrue(Path(str(win_meta["script_path"])).is_file())

        self.assertEqual(mac_meta["installer_type"], "macos_dmg")
        self.assertTrue(str(mac_meta["artifact_path"]).endswith("JARVIS-2.0.0-macOS.dmg"))
        self.assertTrue(Path(str(mac_meta["script_path"])).is_file())

        self.assertEqual(lin_meta["installer_type"], "linux_deb")
        self.assertTrue(str(lin_meta["artifact_path"]).endswith("jarvis_2.0.0_amd64.deb"))
        self.assertTrue(Path(str(lin_meta["script_path"])).is_file())

    def test_08_inno_setup_script_contains_required_sections(self) -> None:
        iss_path = self.repo_root / "packaging" / "windows" / "jarvis_installer.iss"
        content = iss_path.read_text(encoding="utf-8")
        for section in ("[Setup]", "[Tasks]", "[Files]", "[Icons]", "[Run]", "[UninstallDelete]"):
            self.assertIn(section, content)
        self.assertIn("config.example.json", content)
        self.assertIn("onlyifdoesntexist", content)

    def test_09_macos_and_linux_scripts_contain_bundle_metadata(self) -> None:
        dmg_script = (self.repo_root / "packaging" / "macos" / "build_dmg.sh").read_text(encoding="utf-8")
        deb_script = (self.repo_root / "packaging" / "linux" / "build_deb.sh").read_text(encoding="utf-8")

        self.assertIn("NSMicrophoneUsageDescription", dmg_script)
        self.assertIn("hdiutil create", dmg_script)
        self.assertIn("DEBIAN/control", deb_script)
        self.assertIn("jarvis.desktop", deb_script)
        self.assertIn("dpkg-deb --build", deb_script)

    def test_10_github_workflow_matrix_exists(self) -> None:
        wf_path = self.repo_root / ".github" / "workflows" / "release-installers.yml"
        self.assertTrue(wf_path.is_file())
        wf_text = wf_path.read_text(encoding="utf-8")
        self.assertIn("windows-latest", wf_text)
        self.assertIn("macos-latest", wf_text)
        self.assertIn("ubuntu-latest", wf_text)
        self.assertIn("packaging/build_package.py", wf_text)

    def test_11_run_build_dry_run_across_all_platforms(self) -> None:
        for target in ("windows", "macos", "linux"):
            res = run_build(
                platform_name=target,
                build_installer=True,
                dry_run=True,
                root_dir=self.repo_root,
                version="2.0.0",
            )
            self.assertTrue(res["ok"])
            self.assertEqual(res["platform"], target)
            self.assertTrue(res["dry_run"])
            self.assertIsNotNone(res["installer"])

    def test_12_cli_dry_run_outputs_valid_json(self) -> None:
        script = self.repo_root / "packaging" / "build_package.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--platform", "windows", "--installer", "--dry-run"],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["platform"], "windows")
        self.assertEqual(payload["installer"]["installer_type"], "inno_setup_exe")


if __name__ == "__main__":
    unittest.main()
