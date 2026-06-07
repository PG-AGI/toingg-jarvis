#!/usr/bin/env python3
"""Create reproducible JARVIS release staging folders.

The default mode is dependency-free and safe for CI smoke tests: it verifies the
files required by the PyInstaller spec, copies launch assets into a platform
staging directory, and writes a manifest. Use --build to run PyInstaller too.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "release"
REQUIRED_ASSETS = [
    "jarvis_launcher.py",
    "browserClient.py",
    "native_file_manager.py",
    "jarvis_web.html",
    "jarvis_visual.html",
    "config.example.json",
    "JARVIS_README.md",
    "NATIVE_FILE_MANAGER.md",
    "requirements.txt",
    "requirements-build.txt",
    "jarvis.spec",
]


def detect_platform() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return "linux"


def verify_assets() -> list[Path]:
    missing = [name for name in REQUIRED_ASSETS if not (ROOT / name).exists()]
    if missing:
        raise SystemExit(f"Missing release assets: {', '.join(missing)}")
    return [ROOT / name for name in REQUIRED_ASSETS]


def copy_assets(target: Path, assets: list[Path]) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for src in assets:
        shutil.copy2(src, target / src.name)


def write_manifest(target: Path, package_platform: str, assets: list[Path]) -> None:
    manifest = {
        "name": "toingg-jarvis",
        "platform": package_platform,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entrypoint": "jarvis_launcher.py",
        "pyinstaller_spec": "jarvis.spec",
        "assets": [src.name for src in assets],
        "commands": {
            "install_build_deps": f"{sys.executable} -m pip install -r requirements-build.txt",
            "build_binary": "pyinstaller --clean --noconfirm jarvis.spec",
        },
    }
    (target / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def run_pyinstaller() -> None:
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "jarvis.spec"],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage or build JARVIS release artifacts.")
    parser.add_argument(
        "--platform",
        default=detect_platform(),
        choices=["windows", "macos", "linux"],
        help="Target platform name for the staging directory.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run PyInstaller after staging release files.",
    )
    args = parser.parse_args()

    assets = verify_assets()
    target = DIST / args.platform
    copy_assets(target, assets)
    write_manifest(target, args.platform, assets)

    if args.build:
        run_pyinstaller()

    print(f"Release staging ready: {target.relative_to(ROOT)}")
    print(f"Manifest: {(target / 'release-manifest.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
