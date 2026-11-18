import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class PackagingFilesTest(unittest.TestCase):
    def test_version_is_semver(self):
        self.assertRegex(read("packaging", "VERSION").strip(), r"^\d+\.\d+\.\d+$")

    def test_payload_files_exist(self):
        for script in ("build_deb.sh",):
            text = read("packaging", "linux", script)
            for name in re.findall(r'"\$ROOT"/(\w+\.(?:py|html|json))', text):
                self.assertTrue(os.path.exists(os.path.join(ROOT, name)), name)
        iss = read("packaging", "windows", "jarvis.iss")
        for name in re.findall(r'Source: "\.\.\\\.\.\\([\w.]+)"', iss):
            self.assertTrue(os.path.exists(os.path.join(ROOT, name)), name)

    def test_workflow_builds_every_platform(self):
        wf = read(".github", "workflows", "release.yml")
        for needle in ("build_deb.sh", "jarvis.iss", "build_app.sh", "upload-artifact", "action-gh-release"):
            self.assertIn(needle, wf)

    def test_plist_has_version_placeholder(self):
        self.assertIn("@VERSION@", read("packaging", "macos", "Info.plist"))

    @unittest.skipUnless(shutil.which("dpkg-deb"), "dpkg-deb not available")
    def test_deb_builds(self):
        with tempfile.TemporaryDirectory() as out:
            subprocess.run(
                ["sh", os.path.join(ROOT, "packaging", "linux", "build_deb.sh"), "9.9.9", out],
                check=True, capture_output=True,
            )
            deb = os.path.join(out, "toingg-jarvis_9.9.9_all.deb")
            self.assertTrue(os.path.exists(deb))
            listing = subprocess.run(["dpkg-deb", "-c", deb], check=True, capture_output=True, text=True).stdout
            self.assertIn("usr/bin/toingg-jarvis", listing)
            self.assertIn("jarvis_launcher.py", listing)


if __name__ == "__main__":
    unittest.main()
