#!/usr/bin/env python3
"""Stage a portable Toingg Jarvis release artifact for the current platform."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = [
    "README.md",
    "JARVIS_README.md",
    "NATIVE_FILE_MANAGER.md",
    "PIPECAT_GEMINI_TOOLS.md",
    "config.example.json",
    "jarvis_web.html",
    "jarvis_visual.html",
    "browserClient.py",
    "jarvis_launcher.py",
    "native_file_manager.py",
    "pipecat_gemini_tools.py",
]


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_sources(dst: Path) -> None:
    for name in SOURCE_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, dst / name)


def write_launcher(dst: Path, system: str) -> None:
    if system == "Windows":
        launcher = dst / "run-toingg-jarvis.bat"
        launcher.write_text(
            "@echo off\r\n"
            "cd /d \"%~dp0\"\r\n"
            "if exist toingg-jarvis\\toingg-jarvis.exe (\r\n"
            "  toingg-jarvis\\toingg-jarvis.exe\r\n"
            ") else (\r\n"
            "  python jarvis_launcher.py\r\n"
            ")\r\n",
            encoding="utf-8",
        )
        return

    launcher = dst / "run-toingg-jarvis.sh"
    launcher.write_text(
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        "cd \"$(dirname \"$0\")\"\n"
        "if [ -x \"./toingg-jarvis/toingg-jarvis\" ]; then\n"
        "  exec ./toingg-jarvis/toingg-jarvis\n"
        "fi\n"
        "exec python3 jarvis_launcher.py\n",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_release_notes(dst: Path, system: str, machine: str) -> None:
    (dst / "RELEASE_NOTES.txt").write_text(
        "Toingg Jarvis packaged artifact\n"
        f"Platform: {system} {machine}\n\n"
        "Run the platform launcher in this folder. If the PyInstaller bundle is present, "
        "the launcher uses it; otherwise it falls back to the source launcher.\n\n"
        "First run may still require Playwright browser installation on systems where "
        "Chromium is not already cached.\n",
        encoding="utf-8",
    )


def make_zip(src: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(src.rglob("*")):
            archive.write(path, path.relative_to(src.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-dist", default="dist/toingg-jarvis")
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()

    system = platform.system() or "unknown"
    machine = platform.machine() or "unknown"
    artifact_name = f"toingg-jarvis-{system.lower()}-{machine.lower()}"
    output_dir = ROOT / args.output
    stage_dir = output_dir / artifact_name

    output_dir.mkdir(parents=True, exist_ok=True)
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    frozen_dist = ROOT / args.frozen_dist
    if frozen_dist.exists():
        copy_tree(frozen_dist, stage_dir / "toingg-jarvis")

    copy_sources(stage_dir)
    write_launcher(stage_dir, system)
    write_release_notes(stage_dir, system, machine)
    make_zip(stage_dir, output_dir / f"{artifact_name}.zip")

    print(f"Created {output_dir / f'{artifact_name}.zip'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
