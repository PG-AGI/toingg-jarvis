# -*- mode: python ; coding: utf-8 -*-
# Target path in repo: packaging/jarvis.spec
# Build command: pyinstaller --clean --noconfirm packaging/jarvis.spec

block_cipher = None

a = Analysis(
    ['../jarvis_launcher.py'],
    pathex=['..'],
    binaries=[],
    datas=[
        ('../jarvis_web.html', '.'),
        ('../jarvis_visual.html', '.'),
        ('../config.example.json', '.'),
        ('../browserClient.py', '.'),
        ('../native_file_manager.py', '.'),
        ('../pipecat_gemini_tools.py', '.'),
    ],
    hiddenimports=[
        'native_file_manager',
        'pipecat_gemini_tools',
        'browserClient',
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
    [],
    exclude_binaries=True,
    name='toingg-jarvis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='toingg-jarvis',
)
