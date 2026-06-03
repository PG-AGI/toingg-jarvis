# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
block_cipher = None

a = Analysis(
    [str(ROOT / "browserClient.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=["playwright", "playwright.sync_api", "playwright_stealth", "websocket"],
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
    name="browserClient",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
