#!/usr/bin/env python3
"""Build a relocatable Debian package from a tested PyInstaller onedir bundle."""
import argparse
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[+~.-][A-Za-z0-9.-]+)?$")
ARCHITECTURES = {"x86_64": "amd64", "aarch64": "arm64"}


def make_stage(bundle: Path, stage: Path, version: str, arch: str) -> None:
    """Prepare a Debian root without touching /opt or the host package DB."""
    if not VERSION.fullmatch(version):
        raise ValueError("Invalid package version")
    if arch not in {"amd64", "arm64"}:
        raise ValueError(f"Unsupported Debian architecture: {arch}")
    executable = bundle / "JARVIS"
    if not executable.is_file():
        raise FileNotFoundError(f"Missing PyInstaller executable: {executable}")
    if stage.exists():
        raise FileExistsError(f"Refusing to overwrite existing stage: {stage}")

    installed = stage / "opt" / "jarvis"
    shutil.copytree(bundle, installed, symlinks=True)
    if not (installed / "JARVIS").stat().st_mode & 0o111:
        raise ValueError("JARVIS executable is not executable")
    control = stage / "DEBIAN" / "control"
    control.parent.mkdir(parents=True)
    control.write_text(
        "Package: jarvis-voice\n"
        f"Version: {version}\n"
        "Section: utils\n"
        "Priority: optional\n"
        f"Architecture: {arch}\n"
        "Maintainer: PG-AGI contributors\n"
        "Depends: libc6, libportaudio2, libnss3\n"
        "Description: JARVIS local voice assistant\n"
        " Native bundled Python application with browser and voice interfaces.\n",
        encoding="utf-8",
    )
    bindir = stage / "usr" / "bin"
    bindir.mkdir(parents=True)
    launcher = bindir / "jarvis"
    launcher.write_text('#!/bin/sh\nexec /opt/jarvis/JARVIS "$@"\n', encoding="utf-8")
    launcher.chmod(0o755)

    apps = stage / "usr" / "share" / "applications"
    apps.mkdir(parents=True)
    (apps / "jarvis.desktop").write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=JARVIS\n"
        "Comment=Local voice and browser assistant\n"
        "Exec=/usr/bin/jarvis\n"
        "Terminal=true\n"
        "Categories=Utility;\n",
        encoding="utf-8",
    )


def build(bundle: Path, output: Path, version: str, arch: str) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    result = output / f"jarvis_{version}_{arch}.deb"
    with tempfile.TemporaryDirectory(prefix="jarvis-deb-") as tmp:
        stage = Path(tmp) / "package"
        make_stage(bundle, stage, version, arch)
        subprocess.run(
            ["dpkg-deb", "--build", "--root-owner-group", str(stage), str(result)],
            check=True,
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("dist/JARVIS"))
    parser.add_argument("--output", type=Path, default=Path("dist/installers"))
    parser.add_argument("--version", default=os.environ.get("JARVIS_VERSION", "2.0.0"))
    parser.add_argument(
        "--arch",
        default=ARCHITECTURES.get(platform.machine().lower(), "unsupported"),
    )
    args = parser.parse_args()
    print(build(args.bundle, args.output, args.version, args.arch))
