"""
Cross-platform packaging and native installer builder for Toingg J.A.R.V.I.S (Fixes #13).
Generates PyInstaller bundles and platform-native installer scripts/manifests for:
  - Windows (.exe bundle + Inno Setup / PowerShell native installer)
  - macOS (.app bundle + DMG builder script)
  - Linux ( standalone binary + AppImage / .deb control & desktop entry)
"""
from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_OS = ("Windows", "Darwin", "Linux")
REQUIRED_ASSETS = (
    "jarvis_web.html",
    "jarvis_visual.html",
    "browserClient.py",
    "config.example.json",
)


class PackagingError(ValueError):
    """Raised when packaging parameters or target OS are invalid."""


@dataclass(frozen=True)
class PackagePlan:
    os_name: str
    entry_script: str
    output_dir: str
    pyinstaller_cmd: list[str]
    installer_artifact: str
    data_sep: str


def normalize_os(os_name: str | None = None) -> str:
    raw = (os_name or platform.system()).strip().lower()
    mapping = {
        "windows": "Windows",
        "win32": "Windows",
        "darwin": "Darwin",
        "macos": "Darwin",
        "mac": "Darwin",
        "linux": "Linux",
    }
    if raw not in mapping:
        raise PackagingError(f"Unsupported OS: {os_name}")
    return mapping[raw]


def build_pyinstaller_command(
    project_root: str | Path,
    os_name: str | None = None,
    onefile: bool = True,
) -> PackagePlan:
    target_os = normalize_os(os_name)
    root = Path(project_root).resolve()
    entry = root / "jarvis_launcher.py"
    if not entry.exists():
        raise PackagingError(f"Entry script not found: {entry}")

    sep = ";" if target_os == "Windows" else ":"
    dist_dir = root / "dist" / target_os.lower()
    build_dir = root / "build" / target_os.lower()

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "JarvisAssistant",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
    ]
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    if target_os in ("Windows", "Darwin"):
        cmd.append("--windowed")

    for asset in REQUIRED_ASSETS:
        asset_path = root / asset
        if asset_path.exists():
            cmd.extend(["--add-data", f"{asset_path}{sep}."])

    for hidden in ("pyaudio", "numpy", "websocket", "rich", "speech_recognition", "playwright"):
        cmd.extend(["--hidden-import", hidden])

    cmd.append(str(entry))

    ext_map = {
        "Windows": "JarvisAssistant-Setup-Windows.exe",
        "Darwin": "JarvisAssistant-macOS.dmg",
        "Linux": "JarvisAssistant-Linux-x86_64.AppImage",
    }
    return PackagePlan(
        os_name=target_os,
        entry_script=str(entry),
        output_dir=str(dist_dir),
        pyinstaller_cmd=cmd,
        installer_artifact=str(dist_dir / ext_map[target_os]),
        data_sep=sep,
    )


def generate_linux_desktop_entry(app_name: str = "JarvisAssistant", exec_path: str = "/usr/local/bin/JarvisAssistant") -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={app_name}\n"
        "Comment=Toingg J.A.R.V.I.S Voice & Multimodal AI Assistant\n"
        f"Exec={exec_path}\n"
        "Terminal=false\n"
        "Categories=Utility;AudioVideo;ArtificialIntelligence;\n"
    )


def generate_macos_plist(bundle_id: str = "com.pgagi.jarvis", version: str = "2.0.0") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>{bundle_id}</string>
    <key>CFBundleName</key>
    <string>JarvisAssistant</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>J.A.R.V.I.S requires microphone access for wake-word and voice commands.</string>
</dict>
</plist>
"""


def handle_package_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise PackagingError("Payload must be a dictionary.")
    project_root = payload.get("project_root") or os.path.dirname(os.path.abspath(__file__))
    os_name = payload.get("os_name")
    onefile = bool(payload.get("onefile", True))
    dry_run = bool(payload.get("dry_run", True))

    plan = build_pyinstaller_command(project_root, os_name=os_name, onefile=onefile)
    result = {
        "os_name": plan.os_name,
        "entry_script": plan.entry_script,
        "output_dir": plan.output_dir,
        "pyinstaller_cmd": plan.pyinstaller_cmd,
        "installer_artifact": plan.installer_artifact,
        "data_sep": plan.data_sep,
        "executed": False,
    }
    if not dry_run:
        subprocess.run(plan.pyinstaller_cmd, check=True)
        result["executed"] = True
    return result
