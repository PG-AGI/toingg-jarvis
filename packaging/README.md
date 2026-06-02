# Native installers

Cross-platform packaging for J.A.R.V.I.S. The `.github/workflows/release.yml`
pipeline runs everything below automatically on every `v*` tag push (and via
`workflow_dispatch`), uploads per-OS artifacts, and attaches them to the
GitHub Release.

## Outputs

| OS      | Format             | Built by                                  |
|---------|--------------------|-------------------------------------------|
| Windows | `.exe` installer   | PyInstaller + [Inno Setup](https://jrsoftware.org/isinfo.php) |
| Linux   | `.deb` (Debian/Ubuntu) | PyInstaller + `dpkg-deb`              |
| macOS   | `.app` bundle + `.dmg` | PyInstaller `BUNDLE` + `hdiutil`      |

## Build locally

```bash
# 1. One-folder + .app build (current OS)
pip install pyinstaller -r packaging/requirements.txt
pyinstaller --noconfirm packaging/jarvis.spec

# 2a. Windows installer (needs Inno Setup 6 on PATH)
iscc /DAppVersion=1.0.0 packaging\windows\installer.iss

# 2b. Linux .deb
VERSION=1.0.0 bash packaging/linux/build_deb.sh

# 2c. macOS .dmg
VERSION=1.0.0 bash packaging/macos/build_dmg.sh
```

## Signing

The workflow ships unsigned binaries by default. To enable signing, add the
relevant secrets (`WINDOWS_PFX_BASE64` / `MACOS_DEVELOPER_ID` / `APPLE_API_KEY`)
and a signing step before the artifact upload — placeholders intentionally
omitted to keep the default pipeline runnable without secret setup.
