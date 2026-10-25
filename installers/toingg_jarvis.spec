# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "jarvis_web.html"), "."),
    (str(ROOT / "jarvis_visual.html"), "."),
    (str(ROOT / "browserClient.py"), "."),
    (str(ROOT / "native_file_manager.py"), "."),
    (str(ROOT / "pipecat_gemini_tools.py"), "."),
    (str(ROOT / "config.example.json"), "."),
]

a = Analysis(
    [str(ROOT / "jarvis_launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["native_file_manager", "pipecat_gemini_tools", "browserClient"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="toingg-jarvis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="toingg-jarvis",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="ToinggJarvis.app",
        icon=None,
        bundle_identifier="in.pgagi.toingg.jarvis",
        info_plist={
            "CFBundleName": "Toingg Jarvis",
            "CFBundleDisplayName": "Toingg Jarvis",
            "CFBundleShortVersionString": "2.0.0",
            "CFBundleVersion": "2.0.0",
            "NSMicrophoneUsageDescription": "Toingg Jarvis requires microphone access for voice wake-word detection.",
            "NSHighResolutionCapable": True,
        },
    )
