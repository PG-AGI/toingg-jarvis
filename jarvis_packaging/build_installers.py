"""Cross-platform packaging and native installer generator for Toingg JARVIS (#13).

Supports generating:
- Windows `.exe` standalone bundle (PyInstaller) + Inno Setup `.iss` native installer script
- Debian/Ubuntu Linux `.deb` package structure (`DEBIAN/control`, `/usr/bin/toingg-jarvis`, `.desktop` entry)
- macOS `.app` bundle (`Contents/Info.plist`, `Contents/MacOS/toingg-jarvis`) + `.dmg` build script
"""

from __future__ import annotations

import os
import platform
import stat
from pathlib import Path

APP_NAME = "ToinggJarvis"
APP_SLUG = "toingg-jarvis"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Toingg JARVIS Voice-Activated AI Desktop Launcher"
APP_MAINTAINER = "PG-AGI <opensource@pg-agi.com>"
ENTRY_SCRIPT = "jarvis_launcher.py"

BUNDLE_DATA_FILES = [
    "jarvis_web.html",
    "jarvis_visual.html",
    "config.example.json",
]


def get_pyinstaller_args(target_os: str | None = None) -> list[str]:
    """Builds the deterministic PyInstaller CLI argument list for the current or specified OS."""
    system = (target_os or platform.system()).lower()
    sep = ";" if "win" in system else ":"
    args = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_SLUG,
        "--onefile",
    ]
    if "win" in system or "darwin" in system or "mac" in system:
        args.append("--windowed")
    for asset in BUNDLE_DATA_FILES:
        args.extend(["--add-data", f"{asset}{sep}."])
    args.append(ENTRY_SCRIPT)
    return args


def generate_windows_inno_setup_script(version: str = APP_VERSION) -> str:
    """Generates the Inno Setup (.iss) configuration for building the Windows .exe installer."""
    lines = [
        "[Setup]",
        "AppId={{B7432B92-54A1-4E39-9E71-88F092D5A013}}",
        f"AppName={APP_NAME}",
        f"AppVersion={version}",
        "AppPublisher=PG-AGI",
        f"DefaultDirName={{autopf}}\\\\{APP_NAME}",
        f"DefaultGroupName={APP_NAME}",
        "OutputDir=dist\\\\installers",
        f"OutputBaseFilename={APP_SLUG}-setup-{version}-win64",
        "Compression=lzma2",
        "SolidCompression=yes",
        "WizardStyle=modern",
        "ArchitecturesInstallIn64BitMode=x64compatible",
        "",
        "[Tasks]",
        'Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"',
        "",
        "[Files]",
        f'Source: "..\\\\..\\\\dist\\\\{APP_SLUG}.exe"; DestDir: "{{app}}"; Flags: ignoreversion',
        'Source: "..\\\\..\\\\jarvis_web.html"; DestDir: "{app}"; Flags: ignoreversion',
        'Source: "..\\\\..\\\\jarvis_visual.html"; DestDir: "{app}"; Flags: ignoreversion',
        'Source: "..\\\\..\\\\config.example.json"; DestDir: "{app}"; Flags: ignoreversion',
        "",
        "[Icons]",
        f'Name: "{{group}}\\\\{APP_NAME}"; Filename: "{{app}}\\\\{APP_SLUG}.exe"',
        f'Name: "{{autodesktop}}\\\\{APP_NAME}"; Filename: "{{app}}\\\\{APP_SLUG}.exe"; Tasks: desktopicon',
        "",
        "[Run]",
        f'Filename: "{{app}}\\\\{APP_SLUG}.exe"; Description: "Launch {APP_NAME}"; Flags: nowait postinstall skipifsilent',
    ]
    return "\n".join(lines) + "\n"


def generate_debian_control(version: str = APP_VERSION, arch: str = "amd64") -> str:
    """Generates the Debian/Ubuntu DEBIAN/control manifest for dpkg-deb packaging."""
    return (
        f"Package: {APP_SLUG}\n"
        f"Version: {version}\n"
        "Section: utils\n"
        "Priority: optional\n"
        f"Architecture: {arch}\n"
        f"Maintainer: {APP_MAINTAINER}\n"
        "Depends: libc6 (>= 2.31), libportaudio2\n"
        f"Description: {APP_DESCRIPTION}\n"
        " Native voice-activated desktop assistant and browser grid controller.\n"
    )


def generate_linux_desktop_entry() -> str:
    """Generates the freedesktop.org .desktop launcher file for Linux desktop environments."""
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Comment={APP_DESCRIPTION}\n"
        f"Exec=/usr/bin/{APP_SLUG}\n"
        "Terminal=false\n"
        "Categories=Utility;AudioVideo;ArtificialIntelligence;\n"
    )


def generate_macos_info_plist(version: str = APP_VERSION) -> str:
    """Generates the macOS .app bundle Info.plist including NSMicrophoneUsageDescription."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleExecutable</key>
    <string>{APP_SLUG}</string>
    <key>CFBundleIdentifier</key>
    <string>com.pgagi.{APP_SLUG}</string>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>{version}</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>{APP_NAME} requires microphone access for wake-word detection and voice commands.</string>
</dict>
</plist>
"""


def stage_debian_tree(staging_root: Path, binary_path: Path | None = None, version: str = APP_VERSION) -> dict[str, Path]:
    """Creates a complete dpkg-deb staging directory layout for building the .deb installer."""
    debian_dir = staging_root / "DEBIAN"
    bin_dir = staging_root / "usr" / "bin"
    apps_dir = staging_root / "usr" / "share" / "applications"

    debian_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)

    control_file = debian_dir / "control"
    control_file.write_text(generate_debian_control(version=version), encoding="utf-8")

    desktop_file = apps_dir / f"{APP_SLUG}.desktop"
    desktop_file.write_text(generate_linux_desktop_entry(), encoding="utf-8")

    target_bin = bin_dir / APP_SLUG
    if binary_path and binary_path.exists():
        target_bin.write_bytes(binary_path.read_bytes())
    else:
        target_bin.write_text(
            "#!/usr/bin/env sh\nexec python3 /usr/share/toingg-jarvis/jarvis_launcher.py \"$@\"\n",
            encoding="utf-8",
        )
    os.chmod(target_bin, os.stat(target_bin).st_mode | stat.S_IEXEC)

    return {
        "control": control_file,
        "desktop": desktop_file,
        "binary": target_bin,
    }
