# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for J.A.R.V.I.S – cross-platform packaging.

Build:
    pip install pyinstaller
    pyinstaller jarvis.spec --clean

Output:
    dist/JARVIS/  (directory)         → run `./JARVIS` or `JARVIS.exe`
    dist/JARVIS.exe --onedir single   (add --onefile for a single binary)
"""

import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

block_cipher = None

DATA_FILES = [
    (str(ROOT / "jarvis_web.html"), "."),
    (str(ROOT / "jarvis_visual.html"), "."),
    (str(ROOT / "config.example.json"), "."),
    (str(ROOT / "REWARD_SYSTEM.md"), "."),
    (str(ROOT / "CONTRIBUTING.md"), "."),
    (str(ROOT / "CODE_OF_CONDUCT.md"), "."),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "JARVIS.bat"), "."),
    (str(ROOT / "JARVIS.command"), "."),
    (str(ROOT / "setup_mac.sh"), "."),
    (str(ROOT / "NATIVE_FILE_MANAGER.md"), "."),
    (str(ROOT / "JARVIS_README.md"), "."),
    (str(ROOT / "README.md"), "."),
]

HIDDEN_IMPORTS = [
    "sounddevice",
    "numpy",
    "speech_recognition",
    "websocket",
    "playwright",
    "playwright_stealth",
    "rich",
    "http.server",
    "ctypes",
    "json",
    "threading",
    "uuid",
    "webbrowser",
]

EXCLUDES = [
    "tkinter",
    "test",
    "unittest",
    "setuptools",
    "pip",
]

EXE_NAME = "JARVIS" if sys.platform != "win32" else "JARVIS.exe"

a = Analysis(
    [str(ROOT / "jarvis_launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=DATA_FILES,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="JARVIS",
)
