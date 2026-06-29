# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

datas = [
    (str(root / "jarvis_web.html"), "."),
    (str(root / "jarvis_visual.html"), "."),
    (str(root / "config.example.json"), "."),
    (str(root / "browserClient.py"), "."),
    (str(root / "native_file_manager.py"), "."),
    (str(root / "pipecat_gemini_tools.py"), "."),
]

a = Analysis(
    ["jarvis_launcher.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "websocket",
        "playwright",
        "playwright.sync_api",
        "playwright_stealth",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="toingg-jarvis",
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
