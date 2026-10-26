#!/usr/bin/env python3
"""
Cross-Platform Packaging & Native Installer Orchestrator for J.A.R.V.I.S
========================================================================
Builds standalone executables via PyInstaller and native OS installers:
  - Windows : PyInstaller bundle + Inno Setup (.exe installer)
  - macOS   : PyInstaller .app bundle + hdiutil (.dmg disk image)
  - Linux   : PyInstaller bundle + dpkg-deb (.deb package) & AppImage layout

Usage:
  python packaging/build_package.py --platform windows --installer --dry-run
  python packaging/build_package.py --platform macos --installer
  python packaging/build_package.py --platform linux --installer
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_VERSION = "2.0.0"
APP_NAME = "JARVIS"
APP_ID = "com.pgagi.toingg.jarvis"
ENTRYPOINT = "jarvis_launcher.py"

REQUIRED_ASSETS = [
    "jarvis_launcher.py",
    "browserClient.py",
    "native_file_manager.py",
    "jarvis_web.html",
    "jarvis_visual.html",
    "config.example.json",
]

DATA_FILES = [
    ("jarvis_web.html", "."),
    ("jarvis_visual.html", "."),
    ("browserClient.py", "."),
    ("native_file_manager.py", "."),
    ("config.example.json", "."),
]

HIDDEN_IMPORTS = [
    "native_file_manager",
    "speech_recognition",
    "websocket",
    "playwright",
    "playwright_stealth",
    "rich",
    "numpy",
]


def get_repo_root(root_dir: Optional[os.PathLike] = None) -> Path:
    if root_dir is not None:
        return Path(root_dir).resolve()
    return Path(__file__).resolve().parent.parent


def normalize_platform(platform_name: Optional[str] = None) -> str:
    """Normalize OS/platform identifier to 'windows', 'macos', or 'linux'."""
    raw = (platform_name or sys.platform or platform.system()).strip().lower()
    if raw in ("windows", "win32", "win64", "cygwin", "msys"):
        return "windows"
    if raw in ("macos", "darwin", "mac", "osx"):
        return "macos"
    if raw.startswith("linux") or raw in ("ubuntu", "debian", "fedora"):
        return "linux"
    raise ValueError(f"Unsupported target platform: {platform_name!r}. Choose windows, macos, or linux.")


def verify_required_assets(root_dir: Optional[os.PathLike] = None) -> Dict[str, str]:
    """Verify all required entrypoints and web/config assets exist in root_dir."""
    root = get_repo_root(root_dir)
    verified: Dict[str, str] = {}
    missing: List[str] = []

    for rel_path in REQUIRED_ASSETS:
        full_path = root / rel_path
        if not full_path.is_file():
            missing.append(rel_path)
        else:
            verified[rel_path] = str(full_path)

    if missing:
        raise FileNotFoundError(
            f"Missing required packaging assets in {root}: {', '.join(missing)}"
        )
    return verified


def get_data_separator(platform_name: str) -> str:
    """Return PyInstaller --add-data path separator for the target platform."""
    target = normalize_platform(platform_name)
    return ";" if target == "windows" else ":"


def build_pyinstaller_args(
    platform_name: Optional[str] = None,
    root_dir: Optional[os.PathLike] = None,
    output_dir: Optional[os.PathLike] = None,
    onefile: bool = False,
) -> List[str]:
    """Construct PyInstaller CLI arguments for the specified target platform."""
    target = normalize_platform(platform_name)
    root = get_repo_root(root_dir)
    dist_dir = Path(output_dir).resolve() if output_dir else (root / "dist")
    build_dir = root / "build" / target
    sep = get_data_separator(target)

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        f"--name={APP_NAME}",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        "--onedir" if not onefile else "--onefile",
    ]

    if target == "macos":
        args.append(f"--osx-bundle-identifier={APP_ID}")

    for src_rel, dest_rel in DATA_FILES:
        src_path = root / src_rel
        args.append(f"--add-data={src_path}{sep}{dest_rel}")

    for mod in HIDDEN_IMPORTS:
        args.append(f"--hidden-import={mod}")

    args.append(str(root / ENTRYPOINT))
    return args


def generate_pyinstaller_spec(
    platform_name: Optional[str] = None,
    root_dir: Optional[os.PathLike] = None,
    version: str = DEFAULT_VERSION,
) -> str:
    """Generate a deterministic PyInstaller .spec file for JARVIS."""
    target = normalize_platform(platform_name)
    root = get_repo_root(root_dir)

    datas_repr = "[\n"
    for src_rel, dest_rel in DATA_FILES:
        src_posix = (root / src_rel).as_posix()
        datas_repr += f"    ({src_posix!r}, {dest_rel!r}),\n"
    datas_repr += "]"

    hidden_repr = repr(HIDDEN_IMPORTS)
    entry_posix = (root / ENTRYPOINT).as_posix()

    spec = f"""# -*- mode: python ; coding: utf-8 -*-
# Auto-generated PyInstaller spec for {APP_NAME} v{version} ({target})

block_cipher = None

a = Analysis(
    [{entry_posix!r}],
    pathex=[{root.as_posix()!r}],
    binaries=[],
    datas={datas_repr},
    hiddenimports={hidden_repr},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name={APP_NAME!r},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name={APP_NAME!r},
)
"""
    if target == "macos":
        spec += f"""
app = BUNDLE(
    coll,
    name='{APP_NAME}.app',
    icon=None,
    bundle_identifier={APP_ID!r},
    info_plist={{
        'CFBundleName': {APP_NAME!r},
        'CFBundleDisplayName': 'J.A.R.V.I.S Voice Terminal',
        'CFBundleShortVersionString': {version!r},
        'CFBundleVersion': {version!r},
        'NSMicrophoneUsageDescription': 'JARVIS requires microphone access for wake-word and voice commands.',
        'NSAppleEventsUsageDescription': 'JARVIS uses AppleEvents to position and focus desktop windows.',
    }},
)
"""
    return spec


def get_installer_metadata(
    platform_name: Optional[str] = None,
    version: str = DEFAULT_VERSION,
    root_dir: Optional[os.PathLike] = None,
    output_dir: Optional[os.PathLike] = None,
) -> Dict[str, object]:
    """Return native installer configuration and command for the target platform."""
    target = normalize_platform(platform_name)
    root = get_repo_root(root_dir)
    dist_dir = Path(output_dir).resolve() if output_dir else (root / "dist")

    if target == "windows":
        script_path = root / "packaging" / "windows" / "jarvis_installer.iss"
        artifact_name = f"JARVIS-Setup-{version}-Windows-x64.exe"
        cmd = [
            "iscc",
            f"/DMyAppVersion={version}",
            f"/DSourceDistDir={dist_dir / APP_NAME}",
            f"/DOutputDir={dist_dir}",
            str(script_path),
        ]
        return {
            "platform": "windows",
            "installer_type": "inno_setup_exe",
            "script_path": str(script_path),
            "artifact_path": str(dist_dir / artifact_name),
            "command": cmd,
        }

    if target == "macos":
        script_path = root / "packaging" / "macos" / "build_dmg.sh"
        artifact_name = f"JARVIS-{version}-macOS.dmg"
        cmd = [
            "bash",
            str(script_path),
            "--version",
            version,
            "--dist-dir",
            str(dist_dir),
        ]
        return {
            "platform": "macos",
            "installer_type": "macos_dmg",
            "script_path": str(script_path),
            "artifact_path": str(dist_dir / artifact_name),
            "command": cmd,
        }

    script_path = root / "packaging" / "linux" / "build_deb.sh"
    artifact_name = f"jarvis_{version}_amd64.deb"
    cmd = [
        "bash",
        str(script_path),
        "--version",
        version,
        "--dist-dir",
        str(dist_dir),
    ]
    return {
        "platform": "linux",
        "installer_type": "linux_deb",
        "script_path": str(script_path),
        "artifact_path": str(dist_dir / artifact_name),
        "command": cmd,
    }


def run_build(
    platform_name: Optional[str] = None,
    build_installer: bool = False,
    dry_run: bool = False,
    root_dir: Optional[os.PathLike] = None,
    output_dir: Optional[os.PathLike] = None,
    version: str = DEFAULT_VERSION,
    onefile: bool = False,
) -> Dict[str, object]:
    """
    Validate assets, write PyInstaller spec, and optionally execute PyInstaller +
    native OS installer build (or return full build plan when dry_run=True).
    """
    target = normalize_platform(platform_name)
    root = get_repo_root(root_dir)
    dist_dir = Path(output_dir).resolve() if output_dir else (root / "dist")
    verified_assets = verify_required_assets(root)

    pyinstaller_args = build_pyinstaller_args(
        platform_name=target,
        root_dir=root,
        output_dir=dist_dir,
        onefile=onefile,
    )
    spec_content = generate_pyinstaller_spec(
        platform_name=target,
        root_dir=root,
        version=version,
    )
    installer_meta = get_installer_metadata(
        platform_name=target,
        version=version,
        root_dir=root,
        output_dir=dist_dir,
    )

    installer_script = Path(str(installer_meta["script_path"]))
    if build_installer and not installer_script.is_file():
        raise FileNotFoundError(f"Installer script not found: {installer_script}")

    result: Dict[str, object] = {
        "ok": True,
        "platform": target,
        "version": version,
        "dry_run": dry_run,
        "root_dir": str(root),
        "dist_dir": str(dist_dir),
        "verified_assets": verified_assets,
        "pyinstaller_args": pyinstaller_args,
        "spec_generated": True,
        "installer": installer_meta if build_installer else None,
    }

    if dry_run:
        return result

    dist_dir.mkdir(parents=True, exist_ok=True)
    spec_path = root / "build" / f"{APP_NAME}-{target}.spec"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(spec_content, encoding="utf-8")
    result["spec_path"] = str(spec_path)

    subprocess.run(pyinstaller_args, cwd=str(root), check=True)

    # Copy config.example.json alongside built binary for convenience
    bundle_dir = dist_dir / APP_NAME
    if bundle_dir.is_dir():
        shutil.copy2(root / "config.example.json", bundle_dir / "config.example.json")

    if build_installer:
        cmd = list(installer_meta["command"])  # type: ignore[arg-type]
        subprocess.run(cmd, cwd=str(root), check=True)

    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build cross-platform J.A.R.V.I.S executables and native installers."
    )
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux"],
        default=None,
        help="Target OS platform (defaults to current host OS).",
    )
    parser.add_argument(
        "--installer",
        action="store_true",
        help="Also build the native OS installer (.exe / .dmg / .deb).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate assets and output build plan JSON without invoking PyInstaller.",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Package into a single executable binary.",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help=f"Release version string (default: {DEFAULT_VERSION}).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Custom output directory (default: <repo>/dist).",
    )

    args = parser.parse_args(argv)
    plan = run_build(
        platform_name=args.platform,
        build_installer=args.installer,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        version=args.version,
        onefile=args.onefile,
    )
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
