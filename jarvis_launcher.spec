# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ROOT = Path.cwd()
DATA_FILES = [
    ("browserClient.py", "."),
    ("jarvis_web.html", "."),
    ("jarvis_visual.html", "."),
    ("native_file_manager.py", "."),
    ("pipecat_gemini_tools.py", "."),
    ("config.example.json", "."),
    ("README.md", "."),
    ("JARVIS_README.md", "."),
    ("NATIVE_FILE_MANAGER.md", "."),
    ("PIPECAT_GEMINI_TOOLS.md", "."),
]


a = Analysis(
    ["jarvis_launcher.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / src), dest) for src, dest in DATA_FILES if (ROOT / src).exists()],
    hiddenimports=[
        "websocket",
        "speech_recognition",
        "playwright",
        "playwright.sync_api",
        "playwright_stealth",
    ],
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
    [],
    exclude_binaries=True,
    name="toingg-jarvis",
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
    name="toingg-jarvis",
)
