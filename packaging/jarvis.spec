# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building native JARVIS binaries on Windows, Linux and macOS."""

import os

block_cipher = None

datas = [
    ("jarvis_web.html", "."),
    ("jarvis_visual.html", "."),
    ("browserClient.py", "."),
]

a = Analysis(
    ["jarvis_launcher.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "native_file_manager",
        "pipecat_gemini_tools",
        "sounddevice",
        "numpy",
        "speech_recognition",
        "websocket",
        "rich",
        "requests",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="JARVIS",
)

# macOS .app bundle (applies automatically when building on darwin)
app = BUNDLE(
    coll,
    name="JARVIS.app",
    icon=None,
    bundle_identifier="com.pgagi.toingg-jarvis",
)
