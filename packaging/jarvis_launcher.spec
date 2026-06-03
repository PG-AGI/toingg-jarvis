# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
block_cipher = None

datas = [
    (str(ROOT / "jarvis_web.html"), "."),
    (str(ROOT / "jarvis_visual.html"), "."),
    (str(ROOT / "config.example.json"), "."),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "JARVIS_README.md"), "."),
    (str(ROOT / "LICENSE"), "."),
]

a = Analysis(
    [str(ROOT / "jarvis_launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["numpy", "pyaudio", "rich", "speech_recognition"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
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
)
