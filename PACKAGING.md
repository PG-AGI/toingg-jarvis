# Packaging JARVIS

Native installers are built automatically by the
[Release workflow](.github/workflows/release.yml) on every `v*.*.*` tag.

## Targets

| Platform | Artifact | Tool |
|----------|----------|------|
| Windows  | `JARVIS-Setup-<version>.exe` | PyInstaller + Inno Setup |
| Linux    | `jarvis_<version>_amd64.deb` | PyInstaller + dpkg-deb |
| macOS    | `JARVIS-<version>.dmg` (contains `JARVIS.app`) | PyInstaller + hdiutil |

## Local build

```bash
pip install -r requirements.txt
python packaging/build.py --version 2.0.0
```

Artifacts are written to `dist/`. On Windows, Inno Setup must be installed;
on Linux, `dpkg-deb`; on macOS, `hdiutil` (included with macOS).
