#!/usr/bin/env python3
"""Assemble the JARVIS .deb package from the PyInstaller output in dist/.

Layout produced:
    /opt/jarvis/JARVIS            (PyInstaller one-file executable)
    /opt/jarvis/config.example.json
    /usr/share/applications/jarvis.desktop
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGING = os.path.join(ROOT, "packaging", "linux")
DIST = os.path.join(ROOT, "dist")
STAGE = os.path.join(DIST, "deb-stage")

VERSION = os.environ.get("JARVIS_VERSION", "2.0.0")
ARCH = "amd64"


def stage_files():
    if os.path.exists(STAGE):
        shutil.rmtree(STAGE)

    opt = os.path.join(STAGE, "opt", "jarvis")
    apps = os.path.join(STAGE, "usr", "share", "applications")
    debian = os.path.join(STAGE, "DEBIAN")
    os.makedirs(opt)
    os.makedirs(apps)
    os.makedirs(debian)

    exe = os.path.join(DIST, "JARVIS")
    if not os.path.exists(exe):
        sys.exit(f"Missing {exe} - run PyInstaller first (packaging/build.py)")
    shutil.copy2(exe, opt)
    shutil.copy2(os.path.join(ROOT, "config.example.json"), opt)

    shutil.copy2(os.path.join(PACKAGING, "jarvis.desktop"), apps)

    control_src = os.path.join(PACKAGING, "debian", "control")
    control_dst = os.path.join(debian, "control")
    with open(control_src, encoding="utf-8") as fh:
        content = fh.read().replace("Version: 2.0.0", f"Version: {VERSION}")
    with open(control_dst, "w", encoding="utf-8") as fh:
        fh.write(content)

    postinst_src = os.path.join(PACKAGING, "debian", "postinst")
    postinst_dst = os.path.join(debian, "postinst")
    shutil.copy2(postinst_src, postinst_dst)
    os.chmod(postinst_dst, 0o755)


def build_deb():
    out = os.path.join(DIST, f"jarvis_{VERSION}_{ARCH}.deb")
    subprocess.check_call(["dpkg-deb", "--build", STAGE, out])
    print("Built:", out)


if __name__ == "__main__":
    stage_files()
    build_deb()
