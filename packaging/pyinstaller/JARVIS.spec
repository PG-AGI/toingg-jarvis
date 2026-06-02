# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the J.A.R.V.I.S desktop launcher."""

from pathlib import Path

ROOT = Path.cwd()

DATA_FILES = [
    (str(ROOT / "jarvis_web.html"), "."),
    (str(ROOT / "jarvis_visual.html"), "."),
    (str(ROOT / "browserClient.py"), "."),
    (str(ROOT / "config.example.json"), "."),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "JARVIS_README.md"), "."),
]

HIDDEN_IMPORTS = [
    "speech_recognition",
    "websocket",
    "playwright.sync_api",
    "playwright_stealth",
]


a = Analysis(
    [str(ROOT / "jarvis_launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=DATA_FILES,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
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
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="JARVIS",
)
