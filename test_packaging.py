import os
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
PACKAGING = ROOT / "packaging"
WORKFLOWS = ROOT / ".github" / "workflows"


class PackagingAssetsTests(unittest.TestCase):
    def test_pyinstaller_spec_targets_launcher(self):
        spec = (PACKAGING / "jarvis.spec").read_text(encoding="utf-8")
        self.assertIn("jarvis_launcher.py", spec)
        self.assertIn("jarvis_web.html", spec)
        self.assertIn("JARVIS.app", spec)

    def test_windows_installer_script_exists(self):
        iss = (PACKAGING / "windows" / "installer.iss").read_text(encoding="utf-8")
        self.assertIn("[Setup]", iss)
        self.assertIn("JARVIS.exe", iss)

    def test_linux_deb_packaging_files_exist(self):
        control = (PACKAGING / "linux" / "debian" / "control").read_text(encoding="utf-8")
        self.assertIn("Package: jarvis", control)
        self.assertTrue((PACKAGING / "linux" / "debian" / "postinst").exists())
        desktop = (PACKAGING / "linux" / "jarvis.desktop").read_text(encoding="utf-8")
        self.assertIn("[Desktop Entry]", desktop)

    def test_macos_packaging_script_exists(self):
        script = (PACKAGING / "macos" / "build_dmg.py").read_text(encoding="utf-8")
        self.assertIn("hdiutil", script)
        self.assertIn("JARVIS.app", script)

    def test_build_entry_point_is_valid_python(self):
        for script in (
            PACKAGING / "build.py",
            PACKAGING / "linux" / "build_deb.py",
            PACKAGING / "macos" / "build_dmg.py",
        ):
            compile(script.read_text(encoding="utf-8"), str(script), "exec")


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow_path = WORKFLOWS / "release.yml"
        with open(self.workflow_path, encoding="utf-8") as fh:
            self.workflow = yaml.safe_load(fh)

    def test_workflow_triggers_on_version_tags(self):
        triggers = self.workflow[True] if True in self.workflow else self.workflow["on"]
        self.assertIn("v*.*.*", triggers["push"]["tags"])

    def test_workflow_builds_all_three_platforms(self):
        matrix = self.workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
        runners = {entry["os"] for entry in matrix}
        self.assertEqual(
            runners, {"windows-latest", "ubuntu-latest", "macos-latest"}
        )

    def test_workflow_uploads_artifacts_and_creates_release(self):
        jobs = self.workflow["jobs"]
        self.assertIn("upload-artifact", str(jobs["build"]["steps"]))
        self.assertIn("release", jobs)
        self.assertEqual(jobs["release"]["needs"], "build")


if __name__ == "__main__":
    unittest.main()
