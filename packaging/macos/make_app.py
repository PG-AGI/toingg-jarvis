#!/usr/bin/env python3
"""Create a minimal macOS .app bundle around the PyInstaller JARVIS executable."""

from __future__ import annotations

import argparse
import plistlib
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build JARVIS.app from a PyInstaller executable")
    parser.add_argument("executable", type=Path, help="Path to dist/JARVIS/JARVIS")
    parser.add_argument("app", type=Path, nargs="?", default=Path("dist/JARVIS.app"))
    args = parser.parse_args()

    executable = args.executable.resolve()
    if not executable.exists():
        raise SystemExit(f"Executable not found: {executable}")

    app = args.app.resolve()
    contents = app / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    if app.exists():
        shutil.rmtree(app)
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    target = macos / "JARVIS"
    shutil.copy2(executable, target)
    target.chmod(0o755)

    plist = {
        "CFBundleName": "JARVIS",
        "CFBundleDisplayName": "J.A.R.V.I.S",
        "CFBundleIdentifier": "in.pgagi.jarvis",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleExecutable": "JARVIS",
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "10.15",
        "NSMicrophoneUsageDescription": "JARVIS listens for wake words and voice commands.",
    }
    with (contents / "Info.plist").open("wb") as f:
        plistlib.dump(plist, f)

    print(f"Created {app}")


if __name__ == "__main__":
    main()
