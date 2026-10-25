# -*- coding: utf-8 -*-
"""
Cross-Platform Native Installer Builder for Toingg Jarvis (Issue #13)
Builds:
- Windows: PyInstaller bundle + Inno Setup native `.exe` installer
- Linux:   PyInstaller bundle + Debian `.deb` native package (`dpkg-deb`)
- macOS:   PyInstaller `.app` bundle + native `.dmg` disk image (`hdiutil`)
Generates `SHA256SUMS.txt` for all produced installer artifacts.
"""
import argparse
import hashlib
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
PKG_DIR = ROOT_DIR / "installers"
DIST_DIR = ROOT_DIR / "dist"
INSTALLERS_DIR = DIST_DIR / "installers"


def normalize_version(raw_version: str) -> str:
    v = (raw_version or "2.0.0").strip()
    if v.startswith("v"):
        v = v[1:]
    return v or "2.0.0"


def generate_debian_control(version: str, arch: str = "amd64") -> str:
    return (
        f"Package: toingg-jarvis\n"
        f"Version: {version}\n"
        f"Section: utils\n"
        f"Priority: optional\n"
        f"Architecture: {arch}\n"
        f"Maintainer: PG-AGI <admin@pgagi.in>\n"
        f"Homepage: https://github.com/PG-AGI/toingg-jarvis\n"
        f"Description: Toingg Jarvis Voice & Multimodal Desktop Assistant\n"
        f" Native desktop launcher and browser orchestration assistant.\n"
    )


def generate_linux_desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Toingg Jarvis\n"
        "Comment=Voice & Multimodal Desktop Assistant\n"
        "Exec=/usr/bin/toingg-jarvis\n"
        "Terminal=false\n"
        "Categories=Utility;Application;\n"
    )


def stage_debian_tree(staging_root: Path, bundle_dir: Path, version: str, arch: str = "amd64") -> Path:
    pkg_root = staging_root / f"toingg-jarvis_{version}_{arch}"
    if pkg_root.exists():
        shutil.rmtree(pkg_root)

    debian_dir = pkg_root / "DEBIAN"
    opt_dir = pkg_root / "opt" / "toingg-jarvis"
    bin_dir = pkg_root / "usr" / "bin"
    apps_dir = pkg_root / "usr" / "share" / "applications"

    for d in (debian_dir, opt_dir, bin_dir, apps_dir):
        d.mkdir(parents=True, exist_ok=True)

    control_file = debian_dir / "control"
    control_file.write_text(generate_debian_control(version, arch), encoding="utf-8")
    os.chmod(debian_dir, 0o755)
    os.chmod(control_file, 0o644)

    if bundle_dir.exists():
        shutil.copytree(bundle_dir, opt_dir, dirs_exist_ok=True)

    wrapper = bin_dir / "toingg-jarvis"
    wrapper.write_text("#!/bin/sh\nexec /opt/toingg-jarvis/toingg-jarvis \"$@\"\n", encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    desktop_file = apps_dir / "toingg-jarvis.desktop"
    desktop_file.write_text(generate_linux_desktop_entry(), encoding="utf-8")
    return pkg_root


def compute_sha256_manifest(directory: Path) -> Dict[str, str]:
    manifest: Dict[str, str] = {}
    if not directory.exists():
        return manifest
    for fpath in sorted(directory.iterdir()):
        if fpath.is_file() and fpath.name != "SHA256SUMS.txt":
            h = hashlib.sha256()
            with open(fpath, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            manifest[fpath.name] = h.hexdigest()
    if manifest:
        lines = [f"{digest}  {name}" for name, digest in manifest.items()]
        (directory / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def run_pyinstaller() -> Path:
    spec_file = PKG_DIR / "toingg_jarvis.spec"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(spec_file)]
    subprocess.run(cmd, cwd=str(ROOT_DIR), check=True)
    return DIST_DIR / "toingg-jarvis"


def build_windows_installer(version: str) -> Path:
    INSTALLERS_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["JARVIS_VERSION"] = version
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    if iscc:
        subprocess.run([iscc, str(PKG_DIR / "windows_installer.iss")], cwd=str(PKG_DIR), env=env, check=True)
        out = INSTALLERS_DIR / f"toingg-jarvis-setup-{version}-windows-x64.exe"
        if out.exists():
            return out
    archive_base = INSTALLERS_DIR / f"toingg-jarvis-{version}-windows-x64-portable"
    zip_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(DIST_DIR / "toingg-jarvis"))
    return Path(zip_path)


def build_linux_deb(version: str, arch: str = "amd64") -> Path:
    INSTALLERS_DIR.mkdir(parents=True, exist_ok=True)
    staging = ROOT_DIR / "build" / "deb_staging"
    pkg_root = stage_debian_tree(staging, DIST_DIR / "toingg-jarvis", version, arch)
    deb_out = INSTALLERS_DIR / f"toingg-jarvis_{version}_{arch}.deb"
    subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(pkg_root), str(deb_out)], check=True)
    return deb_out


def build_macos_dmg(version: str) -> Path:
    INSTALLERS_DIR.mkdir(parents=True, exist_ok=True)
    app_bundle = DIST_DIR / "ToinggJarvis.app"
    dmg_out = INSTALLERS_DIR / f"ToinggJarvis-{version}-macos.dmg"
    staging = ROOT_DIR / "build" / "dmg_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    if app_bundle.exists():
        shutil.copytree(app_bundle, staging / "ToinggJarvis.app", symlinks=True)
    else:
        shutil.copytree(DIST_DIR / "toingg-jarvis", staging / "ToinggJarvis.app", symlinks=True)
    applications_link = staging / "Applications"
    if not applications_link.exists():
        os.symlink("/Applications", applications_link)
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            "Toingg Jarvis",
            "-srcfolder",
            str(staging),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_out),
        ],
        check=True,
    )
    return dmg_out


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Build native installers for Toingg Jarvis")
    parser.add_argument("--version", default=os.environ.get("JARVIS_VERSION", "2.0.0"))
    parser.add_argument("--skip-pyinstaller", action="store_true")
    args = parser.parse_args(argv)

    version = normalize_version(args.version)
    if not args.skip_pyinstaller:
        run_pyinstaller()

    system = platform.system()
    if system == "Windows":
        artifact = build_windows_installer(version)
    elif system == "Linux":
        artifact = build_linux_deb(version)
    elif system == "Darwin":
        artifact = build_macos_dmg(version)
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    compute_sha256_manifest(INSTALLERS_DIR)
    print(f"Built installer artifact: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
