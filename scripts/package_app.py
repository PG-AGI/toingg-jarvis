#!/usr/bin/env python3
import argparse
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
ARTIFACT_DIR = ROOT / "artifacts"
SPEC_FILE = ROOT / "jarvis_launcher.spec"


def platform_slug(system: Optional[str] = None) -> str:
    system = system or platform.system()
    mapping = {
        "Darwin": "macos",
        "Linux": "linux",
        "Windows": "windows",
    }
    return mapping.get(system, system.lower() or "unknown")


def executable_name(system: Optional[str] = None) -> str:
    return "toingg-jarvis.exe" if (system or platform.system()) == "Windows" else "toingg-jarvis"


def run(cmd: list[str], dry_run: bool = False) -> None:
    print("+", " ".join(cmd))
    if not dry_run:
        subprocess.run(cmd, cwd=ROOT, check=True)


def clean_outputs() -> None:
    for path in (DIST_DIR, BUILD_DIR):
        if path.exists():
            shutil.rmtree(path)
    ARTIFACT_DIR.mkdir(exist_ok=True)


def write_launcher(platform_name: str, stage_dir: Path) -> None:
    exe = executable_name("Windows" if platform_name == "windows" else platform.system())
    if platform_name == "windows":
        (stage_dir / "Launch Toingg Jarvis.bat").write_text(
            "@echo off\r\n"
            "cd /d %~dp0\r\n"
            f'"{exe}"\r\n',
            encoding="utf-8",
        )
    else:
        launcher = stage_dir / "launch-toingg-jarvis.sh"
        launcher.write_text(
            "#!/usr/bin/env sh\n"
            "set -eu\n"
            'cd "$(dirname "$0")"\n'
            f'./{exe}\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)


def stage_artifact(platform_name: str) -> Path:
    source_exe = DIST_DIR / executable_name()
    if not source_exe.exists():
        raise FileNotFoundError(f"PyInstaller output not found: {source_exe}")

    stage_dir = ARTIFACT_DIR / f"toingg-jarvis-{platform_name}"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    shutil.copy2(source_exe, stage_dir / executable_name())
    for filename in (
        "README.md",
        "config.example.json",
        "jarvis_web.html",
        "jarvis_visual.html",
    ):
        source = ROOT / filename
        if source.exists():
            shutil.copy2(source, stage_dir / filename)

    write_launcher(platform_name, stage_dir)
    return stage_dir


def zip_artifact(stage_dir: Path, platform_name: str) -> Path:
    archive_path = ARTIFACT_DIR / f"{stage_dir.name}.zip"
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage_dir.rglob("*")):
            archive.write(path, path.relative_to(ARTIFACT_DIR))
    return archive_path


def build(platform_name: Optional[str] = None, dry_run: bool = False) -> Optional[Path]:
    platform_name = platform_name or platform_slug()
    clean_outputs()
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(SPEC_FILE),
        ],
        dry_run=dry_run,
    )
    if dry_run:
        return None
    stage_dir = stage_artifact(platform_name)
    archive_path = zip_artifact(stage_dir, platform_name)
    print(f"Created {archive_path.relative_to(ROOT)}")
    return archive_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Toingg Jarvis native artifacts.")
    parser.add_argument("--platform", choices=["windows", "linux", "macos"], default=None)
    parser.add_argument("--dry-run", action="store_true", help="Print commands without building")
    args = parser.parse_args()
    build(platform_name=args.platform, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
