#!/usr/bin/env python3
"""
Cross-Platform Native Installer & Bundle Builder for JARVIS (PG-AGI/toingg-jarvis#13).
Supports staging and building:
- Windows: PyInstaller dist + Inno Setup (.exe) / NSIS installer layout
- Linux: Debian/Ubuntu (.deb) package tree with DEBIAN/control + desktop entry + launcher wrapper
- macOS: Native JARVIS.app bundle (Contents/MacOS, Contents/Resources, Info.plist) + .dmg staging
"""

import argparse
import stat
from pathlib import Path

APP_NAME = "JARVIS"
APP_ID = "ai.pgagi.jarvis"
APP_VERSION = "1.0.0"

REQUIRED_RUNTIME_ASSETS = [
    "jarvis_launcher.py",
    "browserClient.py",
    "native_file_manager.py",
    "pipecat_gemini_tools.py",
    "jarvis_web.html",
    "jarvis_visual.html",
    "config.example.json",
]


def resolve_resource_path(relative_path: str, base_dir: Path | None = None) -> Path:
    """
    Resolves bundled runtime assets when running from source or inside a PyInstaller (_MEIPASS) frozen bundle.
    """
    import sys
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / relative_path
    root = base_dir or Path(__file__).resolve().parent.parent
    return root / relative_path


def stage_debian_tree(staging_root: Path, version: str = APP_VERSION, arch: str = "amd64") -> Path:
    """
    Creates a valid Debian package directory layout (`jarvis_<version>_<arch>`) ready for `dpkg-deb --build`.
    """
    pkg_dir = staging_root / f"jarvis_{version}_{arch}"
    debian_dir = pkg_dir / "DEBIAN"
    opt_dir = pkg_dir / "opt" / "jarvis"
    bin_dir = pkg_dir / "usr" / "bin"
    apps_dir = pkg_dir / "usr" / "share" / "applications"

    for d in (debian_dir, opt_dir, bin_dir, apps_dir):
        d.mkdir(parents=True, exist_ok=True)

    control_content = "\n".join([
        f"Package: jarvis-assistant",
        f"Version: {version}",
        "Section: utils",
        "Priority: optional",
        f"Architecture: {arch}",
        "Maintainer: PG-AGI <maintainers@pg-agi.ai>",
        "Description: JARVIS AI Desktop Voice & Browser Assistant",
        "",
    ])
    (debian_dir / "control").write_text(control_content, encoding="utf-8")

    launcher_wrapper = "#!/usr/bin/env bash\nset -e\nexec /opt/jarvis/jarvis \"$@\"\n"
    wrapper_path = bin_dir / "jarvis"
    wrapper_path.write_text(launcher_wrapper, encoding="utf-8")
    wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    desktop_entry = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=JARVIS Assistant",
        "Comment=AI Voice & Browser Automation Assistant",
        "Exec=/usr/bin/jarvis",
        "Terminal=false",
        "Categories=Utility;Development;",
        "",
    ])
    (apps_dir / "jarvis.desktop").write_text(desktop_entry, encoding="utf-8")

    return pkg_dir


def stage_macos_app_bundle(staging_root: Path, version: str = APP_VERSION) -> Path:
    """
    Creates a native macOS `JARVIS.app` bundle structure (`Contents/Info.plist`, `Contents/MacOS/JARVIS`, `Contents/Resources`).
    """
    app_dir = staging_root / f"{APP_NAME}.app"
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    for d in (macos_dir, resources_dir):
        d.mkdir(parents=True, exist_ok=True)

    info_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>{APP_NAME} Assistant</string>
    <key>CFBundleIdentifier</key>
    <string>{APP_ID}</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>CFBundleShortVersionString</key>
    <string>{version}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>{APP_NAME}</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
"""
    (contents_dir / "Info.plist").write_text(info_plist, encoding="utf-8")

    entry_script = "#!/usr/bin/env bash\nDIR=\"$(cd \"$(dirname \"$0\")/../Resources\" && pwd)\"\nexec \"$DIR/jarvis\" \"$@\"\n"
    exe_path = macos_dir / APP_NAME
    exe_path.write_text(entry_script, encoding="utf-8")
    exe_path.chmod(exe_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return app_dir


def generate_inno_setup_script(output_path: Path, version: str = APP_VERSION) -> Path:
    """
    Generates an Inno Setup (.iss) configuration for building the Windows `.exe` installer.
    """
    iss = f"""; Inno Setup Installer Script for JARVIS ({version})
[Setup]
AppId={{{{{APP_ID}}}}}
AppName={APP_NAME} Assistant
AppVersion={version}
DefaultDirName={{autopf}}\\{APP_NAME}
DefaultGroupName={APP_NAME}
OutputDir=dist\\installers
OutputBaseFilename=JARVIS-Setup-{version}-win64
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\\..\\dist\\jarvis\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{APP_NAME} Assistant"; Filename: "{{app}}\\jarvis.exe"
Name: "{{autodesktop}}\\{APP_NAME} Assistant"; Filename: "{{app}}\\jarvis.exe"
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(iss, encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage cross-platform native installer trees for JARVIS.")
    parser.add_argument("--target", choices=["all", "linux", "macos", "windows"], default="all")
    parser.add_argument("--out-dir", default="build/installers")
    parser.add_argument("--version", default=APP_VERSION)
    args = parser.parse_args()

    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if args.target in ("all", "linux"):
        stage_debian_tree(out / "linux", version=args.version)
    if args.target in ("all", "macos"):
        stage_macos_app_bundle(out / "macos", version=args.version)
    if args.target in ("all", "windows"):
        generate_inno_setup_script(out / "windows" / "jarvis.iss", version=args.version)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
