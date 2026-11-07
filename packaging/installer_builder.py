"""Cross-platform packaging and native installer builder for Windows, Linux, and macOS."""

import argparse
from dataclasses import dataclass
import io
import os
from pathlib import Path
import plistlib
import shutil
import stat
import sys
import tarfile
import time
import zipfile

BUNDLED_ASSET_FILES: tuple[str, ...] = (
    "jarvis_launcher.py",
    "browserClient.py",
    "native_file_manager.py",
    "pipecat_gemini_tools.py",
    "jarvis_web.html",
    "jarvis_visual.html",
    "config.example.json",
)


@dataclass(frozen=True)
class PackageMetadata:
    """Immutable release metadata describing versioned native installer packages."""

    app_name: str = "ToinggJarvis"
    app_id: str = "com.pgagi.toingg-jarvis"
    package_slug: str = "toingg-jarvis"
    version: str = "2.0.0"
    architecture: str = "amd64"
    maintainer: str = "PG-AGI Maintainers <opensource@pg-agi.com>"
    description: str = "Voice-activated desktop assistant and browser automation launcher"


def resolve_bundle_root(anchor_file: str | Path | None = None) -> Path:
    """Resolve runtime directory for frozen PyInstaller bundles or source checkouts."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).resolve()
    if anchor_file is not None:
        return Path(anchor_file).resolve().parent
    return Path(__file__).resolve().parent.parent


def resolve_runtime_asset(
    asset_name: str, anchor_file: str | Path | None = None
) -> Path:
    """Locate a bundled HTML, JSON, or Python asset inside frozen or local runtimes."""
    cleaned = asset_name.strip().lstrip("/\\")
    if not cleaned or ".." in Path(cleaned).parts:
        raise ValueError(f"Invalid runtime asset path: {asset_name!r}")
    return resolve_bundle_root(anchor_file) / cleaned


def resolve_user_config_dir(
    platform_name: str | None = None, env_map: dict[str, str] | None = None
) -> Path:
    """Resolve OS-native writable configuration directory for user credentials and state."""
    system_name = (platform_name or sys.platform).lower()
    env = env_map if env_map is not None else dict(os.environ)
    home = Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    if system_name.startswith("win"):
        appdata = Path(env.get("APPDATA") or (home / "AppData" / "Roaming"))
        return appdata / "ToinggJarvis"
    if system_name in ("darwin", "macos", "mac"):
        return home / "Library" / "Application Support" / "ToinggJarvis"
    xdg_config = Path(env.get("XDG_CONFIG_HOME") or (home / ".config"))
    return xdg_config / "toingg-jarvis"


def _copy_available_assets(source_root: Path, destination_dir: Path) -> list[str]:
    """Copy shipped runtime assets from repository root into a package staging folder."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for filename in BUNDLED_ASSET_FILES:
        src = source_root / filename
        if src.is_file():
            shutil.copy2(src, destination_dir / filename)
            copied.append(filename)
    return copied


def _mark_executable(target_path: Path) -> None:
    """Grant owner, group, and world execute permissions on a staged launcher script."""
    current_mode = target_path.stat().st_mode
    target_path.chmod(
        current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )


def render_windows_inno_script(metadata: PackageMetadata) -> str:
    """Generate Inno Setup (.iss) script for compiling a Windows .exe installer."""
    return (
        "[Setup]\n"
        f"AppId={{{{{metadata.app_id}}}}}\n"
        f"AppName={metadata.app_name}\n"
        f"AppVersion={metadata.version}\n"
        f"DefaultDirName={{autopf}}\\{metadata.app_name}\n"
        f"DefaultGroupName={metadata.app_name}\n"
        f"OutputBaseFilename={metadata.package_slug}-{metadata.version}-windows-setup\n"
        "Compression=lzma2\n"
        "SolidCompression=yes\n"
        "PrivilegesRequired=lowest\n\n"
        "[Files]\n"
        'Source: "bundle\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs\n\n'
        "[Icons]\n"
        f'Name: "{{group}}\\{metadata.app_name}"; Filename: "{{app}}\\{metadata.package_slug}.exe"\n'
        f'Name: "{{autodesktop}}\\{metadata.app_name}"; Filename: "{{app}}\\{metadata.package_slug}.exe"\n'
    )


def render_windows_nsis_script(metadata: PackageMetadata) -> str:
    """Generate NSIS (.nsi) installer definition for producing a Windows Setup .exe."""
    installer_name = f"{metadata.package_slug}-{metadata.version}-windows-setup.exe"
    return (
        f'!define APP_NAME "{metadata.app_name}"\n'
        f'!define APP_VERSION "{metadata.version}"\n'
        f'Name "${{APP_NAME}} ${{APP_VERSION}}"\n'
        f'OutFile "{installer_name}"\n'
        f'InstallDir "$LOCALAPPDATA\\{metadata.app_name}"\n'
        "RequestExecutionLevel user\n"
        "Page directory\n"
        "Page instfiles\n\n"
        'Section "Install"\n'
        '  SetOutPath "$INSTDIR"\n'
        '  File /r "bundle\\*.*"\n'
        '  WriteUninstaller "$INSTDIR\\Uninstall.exe"\n'
        f'  CreateShortCut "$DESKTOP\\{metadata.app_name}.lnk" "$INSTDIR\\{metadata.package_slug}.exe"\n'
        "SectionEnd\n\n"
        'Section "Uninstall"\n'
        f'  Delete "$DESKTOP\\{metadata.app_name}.lnk"\n'
        '  RMDir /r "$INSTDIR"\n'
        "SectionEnd\n"
    )


def _render_debian_control(metadata: PackageMetadata) -> str:
    """Format DEBIAN/control metadata fields for Debian and Ubuntu .deb packages."""
    return (
        f"Package: {metadata.package_slug}\n"
        f"Version: {metadata.version}\n"
        "Section: utils\n"
        "Priority: optional\n"
        f"Architecture: {metadata.architecture}\n"
        "Depends: python3 (>= 3.10)\n"
        f"Maintainer: {metadata.maintainer}\n"
        f"Description: {metadata.description}\n"
    )


def _render_linux_desktop_entry(metadata: PackageMetadata) -> str:
    """Format freedesktop.org .desktop launcher entry for Linux desktop environments."""
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={metadata.app_name}\n"
        f"Comment={metadata.description}\n"
        f"Exec=/usr/bin/{metadata.package_slug}\n"
        "Terminal=true\n"
        "Categories=Utility;Accessibility;\n"
    )


def _render_python_entrypoint_script(install_root: str) -> str:
    """Generate a POSIX Python launcher entrypoint that dispatches jarvis_launcher.py."""
    return (
        "#!/usr/bin/env python3\n"
        "import os\n"
        "import runpy\n"
        "import sys\n\n"
        f'APP_DIR = "{install_root}"\n'
        "if APP_DIR not in sys.path:\n"
        "    sys.path.insert(0, APP_DIR)\n"
        "os.chdir(APP_DIR)\n"
        'runpy.run_path(os.path.join(APP_DIR, "jarvis_launcher.py"), run_name="__main__")\n'
    )


def stage_linux_deb_tree(
    output_dir: Path, metadata: PackageMetadata | None = None
) -> Path:
    """Create Debian package directory structure with control file and desktop launcher."""
    meta = metadata or PackageMetadata()
    stage_root = output_dir / f"{meta.package_slug}_{meta.version}_{meta.architecture}"
    debian_dir = stage_root / "DEBIAN"
    bin_dir = stage_root / "usr" / "bin"
    apps_dir = stage_root / "usr" / "share" / "applications"
    opt_dir = stage_root / "opt" / meta.package_slug

    for folder in (debian_dir, bin_dir, apps_dir, opt_dir):
        folder.mkdir(parents=True, exist_ok=True)

    (debian_dir / "control").write_text(_render_debian_control(meta), encoding="utf-8")
    (apps_dir / f"{meta.package_slug}.desktop").write_text(
        _render_linux_desktop_entry(meta), encoding="utf-8"
    )
    launcher_bin = bin_dir / meta.package_slug
    launcher_bin.write_text(
        _render_python_entrypoint_script(f"/opt/{meta.package_slug}"), encoding="utf-8"
    )
    _mark_executable(launcher_bin)
    _copy_available_assets(resolve_bundle_root(), opt_dir)
    return stage_root


def _build_tar_gz_bytes(root_dir: Path, include_children: list[Path]) -> bytes:
    """Serialize selected directory subtrees into a reproducible gzip-compressed tar stream."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for item in include_children:
            arcname = "./" + item.relative_to(root_dir).as_posix()
            tar.add(item, arcname=arcname, recursive=True)
    return buffer.getvalue()


def _format_ar_member(member_name: str, payload: bytes) -> bytes:
    """Encode a single GNU ar archive member with 60-byte ASCII header and 2-byte alignment."""
    timestamp = int(time.time())
    header = (
        f"{member_name:<16}"
        f"{timestamp:<12}"
        f"{0:<6}"
        f"{0:<6}"
        f"{'100644':<8}"
        f"{len(payload):<10}"
        "`\n"
    ).encode("ascii")
    padding = b"\n" if len(payload) % 2 == 1 else b""
    return header + payload + padding


def build_deb_package(staging_dir: Path, output_deb_path: Path) -> Path:
    """Assemble a standard Debian 2.0 (.deb) ar archive in pure Python without external tools."""
    debian_dir = staging_dir / "DEBIAN"
    control_children = sorted(debian_dir.iterdir())
    data_children = [
        p for p in sorted(staging_dir.iterdir()) if p.name != "DEBIAN"
    ]
    control_tar = _build_tar_gz_bytes(debian_dir, control_children)
    data_tar = _build_tar_gz_bytes(staging_dir, data_children)

    output_deb_path.parent.mkdir(parents=True, exist_ok=True)
    ar_stream = (
        b"!<arch>\n"
        + _format_ar_member("debian-binary", b"2.0\n")
        + _format_ar_member("control.tar.gz", control_tar)
        + _format_ar_member("data.tar.gz", data_tar)
    )
    output_deb_path.write_bytes(ar_stream)
    return output_deb_path


def stage_macos_app_bundle(
    output_dir: Path, metadata: PackageMetadata | None = None
) -> Path:
    """Create a native macOS .app bundle with Info.plist, MacOS launcher, and Resources."""
    meta = metadata or PackageMetadata()
    app_bundle = output_dir / f"{meta.app_name}.app"
    contents_dir = app_bundle / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    info_plist = {
        "CFBundleName": meta.app_name,
        "CFBundleDisplayName": meta.app_name,
        "CFBundleIdentifier": meta.app_id,
        "CFBundleVersion": meta.version,
        "CFBundleShortVersionString": meta.version,
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": meta.package_slug,
        "LSMinimumSystemVersion": "12.0",
        "NSMicrophoneUsageDescription": "JARVIS requires microphone access for wake-word detection.",
    }
    with (contents_dir / "Info.plist").open("wb") as fp:
        plistlib.dump(info_plist, fp)

    executable_path = macos_dir / meta.package_slug
    executable_path.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import os, runpy, sys\n"
        'RES = str((Path(__file__).resolve().parent.parent / "Resources"))\n'
        "sys.path.insert(0, RES)\n"
        "os.chdir(RES)\n"
        'runpy.run_path(os.path.join(RES, "jarvis_launcher.py"), run_name="__main__")\n',
        encoding="utf-8",
    )
    _mark_executable(executable_path)
    _copy_available_assets(resolve_bundle_root(), resources_dir)
    return app_bundle


def _create_zip_archive(source_dir: Path, zip_path: Path) -> Path:
    """Compress a directory tree into a portable zip distribution archive."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(source_dir.parent))
    return zip_path


def _build_windows_artifacts(output_dir: Path, meta: PackageMetadata) -> dict[str, str]:
    """Stage Windows bundle, Inno Setup/NSIS installer scripts, and portable zip archive."""
    win_root = output_dir / "windows"
    bundle_dir = win_root / "bundle"
    _copy_available_assets(resolve_bundle_root(), bundle_dir)
    inno_path = win_root / f"{meta.package_slug}.iss"
    nsis_path = win_root / f"{meta.package_slug}.nsi"
    inno_path.write_text(render_windows_inno_script(meta), encoding="utf-8")
    nsis_path.write_text(render_windows_nsis_script(meta), encoding="utf-8")
    zip_path = _create_zip_archive(
        bundle_dir,
        output_dir / f"{meta.package_slug}-{meta.version}-windows-portable.zip",
    )
    return {
        "inno_script": str(inno_path),
        "nsis_script": str(nsis_path),
        "portable_zip": str(zip_path),
    }


def build_platform_artifacts(
    output_dir: str | Path, target_os: str = "all"
) -> dict[str, str]:
    """Generate native installer packages and bundles for the requested target OS."""
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    meta = PackageMetadata()
    normalized = target_os.strip().lower()
    artifacts: dict[str, str] = {}

    if normalized in ("all", "windows", "win32"):
        artifacts.update(_build_windows_artifacts(out, meta))
    if normalized in ("all", "linux"):
        stage_dir = stage_linux_deb_tree(out / "linux", meta)
        deb_file = out / f"{meta.package_slug}_{meta.version}_{meta.architecture}.deb"
        build_deb_package(stage_dir, deb_file)
        artifacts["linux_deb"] = str(deb_file)
    if normalized in ("all", "macos", "darwin"):
        app_bundle = stage_macos_app_bundle(out / "macos", meta)
        mac_zip = _create_zip_archive(
            app_bundle,
            out / f"{meta.app_name}-{meta.version}-macos-app.zip",
        )
        artifacts["macos_app"] = str(app_bundle)
        artifacts["macos_archive"] = str(mac_zip)
    return artifacts


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for building cross-platform native installer packages."""
    parser = argparse.ArgumentParser(
        description="Build native Windows, Linux (.deb), and macOS (.app) packages for JARVIS."
    )
    parser.add_argument("--target", default="all", choices=["all", "windows", "linux", "macos"])
    parser.add_argument("--output-dir", default="dist/installers")
    args = parser.parse_args(argv)
    built = build_platform_artifacts(args.output_dir, args.target)
    for key, path in built.items():
        print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
