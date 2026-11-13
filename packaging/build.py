#!/usr/bin/env python3
"""Cross-platform build entry point for JARVIS packages.

Builds the PyInstaller executable and then delegates to the
platform-specific packager (Inno Setup on Windows, dpkg-deb on Linux,
hdiutil on macOS).

Usage:
    python packaging/build.py [--version X.Y.Z]
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGING = os.path.join(ROOT, "packaging")
DIST = os.path.join(ROOT, "dist")


def run(cmd, **kwargs):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT, **kwargs)


def build_executable(version):
    spec = os.path.join(PACKAGING, "jarvis.spec")
    run([
        sys.executable, "-m", "PyInstaller", spec,
        "--distpath", DIST,
        "--workpath", os.path.join(ROOT, "build"),
        "--clean", "-y",
        "--define", f"APP_VERSION={version}",
    ])


def package_windows():
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    run([iscc, os.path.join(PACKAGING, "windows", "installer.iss")])


def package_linux():
    run([sys.executable, os.path.join(PACKAGING, "linux", "build_deb.py")])


def package_macos():
    run([sys.executable, os.path.join(PACKAGING, "macos", "build_dmg.py")])


def main():
    parser = argparse.ArgumentParser(description="Build JARVIS native packages")
    parser.add_argument("--version", default="2.0.0", help="release version string")
    args = parser.parse_args()

    build_executable(args.version)

    system = platform.system()
    if system == "Windows":
        package_windows()
    elif system == "Linux":
        package_linux()
    elif system == "Darwin":
        package_macos()
    else:
        print(f"No native packager for {system}; executable is in {DIST}")

    print("Build complete. Artifacts in:", DIST)


if __name__ == "__main__":
    main()
