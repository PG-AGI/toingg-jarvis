# PyInstaller spec for J.A.R.V.I.S — builds one-folder app for the current OS.
# Run from repo root:  pyinstaller packaging/jarvis.spec
import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

datas = [
    ('jarvis_web.html', '.'),
    ('jarvis_visual.html', '.'),
    ('browserClient.py', '.'),
    ('config.example.json', '.'),
]

hiddenimports = (
    collect_submodules('speech_recognition')
    + collect_submodules('playwright')
    + ['pyaudio', 'numpy', 'websocket', 'rich', 'sounddevice']
)

a = Analysis(
    ['jarvis_launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JARVIS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='JARVIS',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='JARVIS.app',
        bundle_identifier='com.pgagi.jarvis',
        info_plist={
            'NSMicrophoneUsageDescription': 'JARVIS needs microphone access for wake-word detection.',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.14',
        },
    )
