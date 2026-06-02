#!/usr/bin/env python3
"""Build native distributable artifacts for JARVIS.

The script creates a PyInstaller app first, then wraps it in the native package
format available on the current runner:

- Windows: NSIS installer when makensis exists, plus a zip fallback.
- macOS: .dmg when hdiutil exists, plus a zip fallback.
- Linux: .deb when dpkg-deb exists, plus a tar.gz fallback.
"""

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


APP_NAME = "JARVIS"
PACKAGE_NAME = "jarvis"
VERSION = os.environ.get("JARVIS_PACKAGE_VERSION", "0.1.0")
ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build" / "native"
PACKAGE_DIR = DIST_DIR / "packages"

LAUNCHER_RESOURCE_FILES = [
    "jarvis_web.html",
    "jarvis_visual.html",
    "config.example.json",
]


def run(command: list[str], *, dry_run: bool = False) -> None:
    print("+", " ".join(command))
    if not dry_run:
        subprocess.run(command, cwd=ROOT, check=True)


def clean() -> None:
    for path in [DIST_DIR, ROOT / "build", ROOT / f"{APP_NAME}.spec", ROOT / "browserClient.spec"]:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)


def pyinstaller_command(
    target_platform: str,
    entrypoint: str,
    name: str,
    *,
    resources: list[str] | None = None,
    windowed: bool = False,
) -> list[str]:
    data_separator = ";" if target_platform == "windows" else ":"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        name,
    ]

    if windowed:
        command.append("--windowed")

    for resource in resources or []:
        command.extend(["--add-data", f"{resource}{data_separator}."])

    command.append(entrypoint)
    return command


def build_pyinstaller_app(target_platform: str, *, dry_run: bool = False) -> None:
    run(
        pyinstaller_command(target_platform, "browserClient.py", "browserClient"),
        dry_run=dry_run,
    )
    run(
        pyinstaller_command(
            target_platform,
            "jarvis_launcher.py",
            APP_NAME,
            resources=LAUNCHER_RESOURCE_FILES + ["browserClient.py"],
            windowed=target_platform == "macos",
        ),
        dry_run=dry_run,
    )

    if dry_run:
        return

    browser_dist = DIST_DIR / "browserClient"
    if target_platform == "macos":
        browser_destination = DIST_DIR / f"{APP_NAME}.app" / "Contents" / "Resources" / "browserClient"
    else:
        browser_destination = DIST_DIR / APP_NAME / "browserClient"

    if browser_dist.exists():
        copy_tree(browser_dist, browser_destination)


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def zip_path(source: Path, destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    if source.is_dir():
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in source.rglob("*"):
                archive.write(path, path.relative_to(source.parent))
    else:
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(source, source.name)


def package_windows(*, dry_run: bool = False) -> None:
    app_dir = DIST_DIR / APP_NAME
    installer_script = BUILD_DIR / "jarvis-installer.nsi"
    installer = PACKAGE_DIR / f"{APP_NAME}-{VERSION}-windows-installer.exe"
    zip_artifact = PACKAGE_DIR / f"{APP_NAME}-{VERSION}-windows.zip"

    if dry_run:
        print(f"Would package Windows app from {app_dir}")
        return

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    installer_script.write_text(
        textwrap.dedent(
            f"""
            Unicode True
            Name "{APP_NAME}"
            OutFile "{installer}"
            InstallDir "$PROGRAMFILES\\{APP_NAME}"
            RequestExecutionLevel admin

            Page directory
            Page instfiles

            Section "Install"
              SetOutPath "$INSTDIR"
              File /r "{app_dir}\\*"
              CreateShortcut "$DESKTOP\\{APP_NAME}.lnk" "$INSTDIR\\{APP_NAME}.exe"
              CreateShortcut "$SMPROGRAMS\\{APP_NAME}.lnk" "$INSTDIR\\{APP_NAME}.exe"
            SectionEnd
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    makensis = shutil.which("makensis")
    if makensis:
        run([makensis, str(installer_script)])
    else:
        print("makensis not found; skipping .exe installer and creating zip fallback")

    zip_path(app_dir, zip_artifact)
    print(f"Created {zip_artifact}")


def package_macos(*, dry_run: bool = False) -> None:
    app_bundle = DIST_DIR / f"{APP_NAME}.app"
    zip_artifact = PACKAGE_DIR / f"{APP_NAME}-{VERSION}-macos-app.zip"
    dmg_artifact = PACKAGE_DIR / f"{APP_NAME}-{VERSION}-macos.dmg"

    if dry_run:
        print(f"Would package macOS app from {app_bundle}")
        return

    if app_bundle.exists() and shutil.which("hdiutil"):
        run(
            [
                "hdiutil",
                "create",
                "-volname",
                APP_NAME,
                "-srcfolder",
                str(app_bundle),
                "-ov",
                "-format",
                "UDZO",
                str(dmg_artifact),
            ]
        )
    else:
        print("hdiutil or .app bundle not found; skipping .dmg artifact")

    if app_bundle.exists():
        zip_path(app_bundle, zip_artifact)
        print(f"Created {zip_artifact}")
    else:
        zip_path(DIST_DIR / APP_NAME, zip_artifact)
        print(f"Created {zip_artifact}")


def write_file(path: Path, contents: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def package_linux(*, dry_run: bool = False) -> None:
    app_dir = DIST_DIR / APP_NAME
    package_root = BUILD_DIR / f"{PACKAGE_NAME}_{VERSION}_amd64"
    opt_dir = package_root / "opt" / PACKAGE_NAME
    bin_launcher = package_root / "usr" / "bin" / PACKAGE_NAME
    desktop_file = package_root / "usr" / "share" / "applications" / "jarvis.desktop"
    control_file = package_root / "DEBIAN" / "control"
    deb_artifact = PACKAGE_DIR / f"{PACKAGE_NAME}_{VERSION}_amd64.deb"
    tar_artifact = PACKAGE_DIR / f"{APP_NAME}-{VERSION}-linux.tar.gz"

    if dry_run:
        print(f"Would package Linux app from {app_dir}")
        return

    if package_root.exists():
        shutil.rmtree(package_root)
    copy_tree(app_dir, opt_dir / APP_NAME)

    write_file(
        bin_launcher,
        textwrap.dedent(
            f"""
            #!/bin/sh
            exec /opt/{PACKAGE_NAME}/{APP_NAME}/{APP_NAME} "$@"
            """
        ).lstrip(),
        mode=0o755,
    )
    write_file(
        desktop_file,
        textwrap.dedent(
            f"""
            [Desktop Entry]
            Type=Application
            Name=JARVIS
            Comment=AI voice terminal powered by Toingg
            Exec=/usr/bin/{PACKAGE_NAME}
            Terminal=true
            Categories=Utility;AudioVideo;
            """
        ).lstrip(),
    )
    write_file(
        control_file,
        textwrap.dedent(
            f"""
            Package: {PACKAGE_NAME}
            Version: {VERSION}
            Section: utils
            Priority: optional
            Architecture: amd64
            Maintainer: PG-AGI
            Description: JARVIS AI voice terminal powered by Toingg
             Native package generated from the toingg-jarvis project.
            """
        ).lstrip(),
    )

    dpkg_deb = shutil.which("dpkg-deb")
    if dpkg_deb:
        run([dpkg_deb, "--build", str(package_root), str(deb_artifact)])
    else:
        print("dpkg-deb not found; skipping .deb artifact")

    with tarfile.open(tar_artifact, "w:gz") as archive:
        archive.add(app_dir, arcname=APP_NAME)
    print(f"Created {tar_artifact}")


def detect_platform() -> str:
    system = platform.system()
    if system == "Windows":
        return "windows"
    if system == "Darwin":
        return "macos"
    return "linux"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build native JARVIS packages")
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux"],
        default=detect_platform(),
        help="Target packaging platform. Defaults to the current OS.",
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Keep existing build/dist directories before packaging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print build steps without invoking PyInstaller or package tools.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_clean and not args.dry_run:
        clean()
    else:
        PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    build_pyinstaller_app(args.platform, dry_run=args.dry_run)

    if args.platform == "windows":
        package_windows(dry_run=args.dry_run)
    elif args.platform == "macos":
        package_macos(dry_run=args.dry_run)
    else:
        package_linux(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
