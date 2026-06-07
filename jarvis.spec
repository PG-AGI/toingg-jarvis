# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ROOT = Path.cwd()

datas = [
    (str(ROOT / "config.example.json"), "."),
    (str(ROOT / "jarvis_web.html"), "."),
    (str(ROOT / "jarvis_visual.html"), "."),
    (str(ROOT / "JARVIS_README.md"), "."),
    (str(ROOT / "NATIVE_FILE_MANAGER.md"), "."),
    (str(ROOT / "browserClient.py"), "."),
    (str(ROOT / "native_file_manager.py"), "."),
]

hiddenimports = [
    "playwright",
    "playwright.sync_api",
    "playwright_stealth",
    "speech_recognition",
    "websocket",
]

a = Analysis(
    ["jarvis_launcher.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="jarvis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
