#!/usr/bin/env python3
"""Build and stage release artifacts for J.A.R.V.I.S."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import textwrap
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
RELEASES = DIST / "releases"


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except Exception as exc:  # pragma: no cover - import side effect only
        raise SystemExit(
            "PyInstaller is not installed. Run: python -m pip install -r requirements-build.txt"
        ) from exc


def build_binaries() -> tuple[Path, Path]:
    ensure_pyinstaller()
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(ROOT / "packaging" / "jarvis_launcher.spec")])
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(ROOT / "packaging" / "browser_client.spec")])

    suffix = ".exe" if platform.system() == "Windows" else ""
    launcher = DIST / f"JARVIS{suffix}"
    browser = DIST / f"browserClient{suffix}"
    if not launcher.exists():
        raise SystemExit(f"Expected launcher binary missing: {launcher}")
    if not browser.exists():
        raise SystemExit(f"Expected browser client binary missing: {browser}")
    return launcher, browser


def copy_docs(target: Path) -> None:
    for name in ("README.md", "JARVIS_README.md", "LICENSE", "config.example.json"):
        shutil.copy2(ROOT / name, target / name)


def write_info_plist(target: Path) -> None:
    info = textwrap.dedent(
        """\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
          <dict>
            <key>CFBundleDisplayName</key>
            <string>J.A.R.V.I.S</string>
            <key>CFBundleExecutable</key>
            <string>JARVIS</string>
            <key>CFBundleIdentifier</key>
            <string>com.toingg.jarvis</string>
            <key>CFBundleName</key>
            <string>J.A.R.V.I.S</string>
            <key>CFBundlePackageType</key>
            <string>APPL</string>
            <key>CFBundleShortVersionString</key>
            <string>2.0.0</string>
            <key>CFBundleVersion</key>
            <string>2.0.0</string>
            <key>LSMinimumSystemVersion</key>
            <string>10.15</string>
          </dict>
        </plist>
        """
    )
    (target / "Info.plist").write_text(info, encoding="utf-8")


def stage_mac(launcher: Path, browser: Path) -> Path:
    bundle = RELEASES / "JARVIS.app"
    contents = bundle / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    shutil.rmtree(bundle, ignore_errors=True)
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    shutil.copy2(launcher, macos / "JARVIS")
    shutil.copy2(browser, macos / "browserClient")
    os.chmod(macos / "JARVIS", 0o755)
    os.chmod(macos / "browserClient", 0o755)
    copy_docs(resources)
    write_info_plist(contents)
    return bundle


def stage_windows(launcher: Path, browser: Path) -> Path:
    bundle = RELEASES / "JARVIS-windows-x86_64"
    shutil.rmtree(bundle, ignore_errors=True)
    bundle.mkdir(parents=True, exist_ok=True)
    shutil.copy2(launcher, bundle / launcher.name)
    shutil.copy2(browser, bundle / browser.name)
    copy_docs(bundle)
    archive = RELEASES / f"{bundle.name}.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in bundle.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(bundle))
    return archive


def stage_linux(launcher: Path, browser: Path) -> Path:
    bundle = RELEASES / "JARVIS-linux-x86_64"
    shutil.rmtree(bundle, ignore_errors=True)
    bundle.mkdir(parents=True, exist_ok=True)
    shutil.copy2(launcher, bundle / launcher.name)
    shutil.copy2(browser, bundle / browser.name)
    copy_docs(bundle)
    archive = RELEASES / f"{bundle.name}.tar.gz"
    if archive.exists():
        archive.unlink()
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(bundle, arcname=bundle.name)
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description="Package J.A.R.V.I.S release artifacts")
    parser.add_argument(
        "--mode",
        choices=("auto", "windows", "macos", "linux"),
        default="auto",
        help="Select the release layout to stage",
    )
    args = parser.parse_args()

    launcher, browser = build_binaries()
    RELEASES.mkdir(parents=True, exist_ok=True)

    mode = args.mode
    if mode == "auto":
        mode = {"Windows": "windows", "Darwin": "macos"}.get(platform.system(), "linux")

    if mode == "macos":
        artifact = stage_mac(launcher, browser)
    elif mode == "windows":
        artifact = stage_windows(launcher, browser)
    else:
        artifact = stage_linux(launcher, browser)

    print(f"Release artifact ready: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
