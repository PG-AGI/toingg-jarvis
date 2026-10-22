# -*- mode: python ; coding: utf-8 -*-
"""One-directory native bundle; keep settings and credentials OUT of the image."""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH)
datas = [
    (str(root / "jarvis_web.html"), "."),
    (str(root / "jarvis_visual.html"), "."),
    (str(root / "config.example.json"), "."),
]
# Playwright and stealth require non-Python driver/JS resources in the bundle.
datas += collect_data_files("playwright_stealth")
hidden = [
    "browserClient",
    "native_file_manager",
    "speech_recognition",
    "pyaudio",
    "numpy",
    "websocket",
    "rich",
    "playwright.__main__",
]
hidden += collect_submodules("playwright_stealth")

a = Analysis(
    [str(root / "jarvis_launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tensorflow", "torch", "transformers", "pandas", "scipy", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="JARVIS",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="JARVIS.app",
        bundle_identifier="com.pgagi.jarvis",
        info_plist={
            "NSMicrophoneUsageDescription": "JARVIS listens for a wake phrase when activated.",
            "NSAppleEventsUsageDescription": "JARVIS can open browser windows on request.",
            "LSMinimumSystemVersion": "10.15",
        },
    )
