# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPECPATH)

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all(
    "playwright"
)
stealth_datas, stealth_binaries, stealth_hiddenimports = collect_all(
    "playwright_stealth"
)

datas = [
    (str(ROOT / "jarvis_web.html"), "."),
    (str(ROOT / "jarvis_visual.html"), "."),
    (str(ROOT / "config.example.json"), "."),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "README.md"), "."),
] + playwright_datas + stealth_datas

hiddenimports = [
    "browserClient",
    "native_file_manager",
    "numpy",
    "pyaudio",
    "speech_recognition",
    "websocket",
    "playwright.sync_api",
    "playwright_stealth",
] + playwright_hiddenimports + stealth_hiddenimports

analysis = Analysis(
    [str(ROOT / "jarvis_launcher.py")],
    pathex=[str(ROOT)],
    binaries=playwright_binaries + stealth_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="JARVIS",
)

if sys.platform == "darwin":
    app = BUNDLE(
        collection,
        name="JARVIS.app",
        bundle_identifier="com.pgagi.jarvis",
        info_plist={
            "CFBundleDisplayName": "JARVIS",
            "NSMicrophoneUsageDescription": (
                "JARVIS uses the microphone to listen for the wake word and voice commands."
            ),
        },
    )
