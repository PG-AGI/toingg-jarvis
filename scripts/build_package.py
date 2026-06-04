#!/usr/bin/env python3
"""Build a local distributable JARVIS package for the current platform."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PACKAGE_ROOT = ROOT / "package"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def build_zip() -> Path:
    system = platform.system().lower()
    machine = platform.machine().lower() or "unknown"
    package_name = f"jarvis-{system}-{machine}"
    staging = PACKAGE_ROOT / package_name

    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    executable = DIST / ("jarvis.exe" if platform.system() == "Windows" else "jarvis")
    copy_if_exists(executable, staging / executable.name)
    copy_if_exists(ROOT / "config.example.json", staging / "config.example.json")
    copy_if_exists(ROOT / "README.md", staging / "README.md")
    copy_if_exists(ROOT / "docs" / "PACKAGING.md", staging / "PACKAGING.md")

    archive = shutil.make_archive(str(PACKAGE_ROOT / package_name), "zip", staging)
    return Path(archive)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the JARVIS executable package.")
    parser.add_argument(
        "--skip-pyinstaller",
        action="store_true",
        help="Only assemble the package from an existing dist/jarvis binary.",
    )
    args = parser.parse_args()

    if not args.skip_pyinstaller:
        run(["pyinstaller", "--clean", "--noconfirm", "jarvis_launcher.spec"])

    archive = build_zip()
    print(f"Built {archive.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
