# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for packaging the standalone ToinggJarvis desktop binary."""

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent

BUNDLED_DATAS = [
    (str(PROJECT_ROOT / "jarvis_web.html"), "."),
    (str(PROJECT_ROOT / "jarvis_visual.html"), "."),
    (str(PROJECT_ROOT / "browserClient.py"), "."),
    (str(PROJECT_ROOT / "native_file_manager.py"), "."),
    (str(PROJECT_ROOT / "pipecat_gemini_tools.py"), "."),
    (str(PROJECT_ROOT / "config.example.json"), "."),
]

HIDDEN_IMPORTS = [
    "native_file_manager",
    "pipecat_gemini_tools",
    "browserClient",
    "packaging.installer_builder",
]

a = Analysis(
    [str(PROJECT_ROOT / "jarvis_launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=BUNDLED_DATAS,
    hiddenimports=HIDDEN_IMPORTS,
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
