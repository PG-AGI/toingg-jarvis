#!/usr/bin/env python3
"""Create a distributable JARVIS.dmg from the PyInstaller JARVIS.app bundle.

Requires the .app bundle at dist/JARVIS.app (produced by packaging/jarvis.spec
on macOS).
"""

import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST = os.path.join(ROOT, "dist")

VERSION = os.environ.get("JARVIS_VERSION", "2.0.0")
APP = os.path.join(DIST, "JARVIS.app")
DMG = os.path.join(DIST, f"JARVIS-{VERSION}.dmg")
STAGING = os.path.join(DIST, "dmg-staging")


def build_dmg():
    if not os.path.isdir(APP):
        raise SystemExit(f"Missing {APP} - run PyInstaller first (packaging/build.py)")

    if os.path.exists(STAGING):
        shutil.rmtree(STAGING)
    os.makedirs(STAGING)
    shutil.copytree(APP, os.path.join(STAGING, "JARVIS.app"))
    # Finder convenience link to /Applications
    subprocess.check_call([
        "ln", "-s", "/Applications", os.path.join(STAGING, "Applications")
    ])

    if os.path.exists(DMG):
        os.remove(DMG)

    subprocess.check_call([
        "hdiutil", "create",
        "-volname", "JARVIS",
        "-srcfolder", STAGING,
        "-ov", "-format", "UDZO",
        DMG,
    ])
    print("Built:", DMG)


if __name__ == "__main__":
    build_dmg()
