import sys ; sys.setrecursionlimit(5000)
from PyInstaller.utils.hooks import collect_data_files
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Windows one-dir bundle.

Produces dist/JARVIS/JARVIS.exe. The browser-automation client is included
as a run mode of the same exe (``JARVIS.exe --browser-client``), so the
frozen launcher needs no Python on the target machine.

Playwright's Chromium is intentionally NOT bundled (adds ~150 MB);
see docs/windows-installer.md post-install step.
"""

block_cipher = None


a = Analysis(
    ["jarvis_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("jarvis_web.html", "."),
        ("jarvis_visual.html", "."),
        ("config.example.json", "."),
    ] + collect_data_files("playwright_stealth"),
    hiddenimports=["browserClient", "speech_recognition"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["AppKit", "pipecat", "pytest", "tkinter", "unittest", "torch", "torchvision", "torchaudio", "transformers", "pandas", "scipy", "matplotlib", "cv2", "sklearn", "sqlalchemy", "pyarrow", "duckdb", "boto3", "botocore", "onnxruntime", "datasets", "altair", "numba", "llvmlite", "IPython", "notebook", "sphinx"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
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
    upx=False,
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JARVIS",
)
