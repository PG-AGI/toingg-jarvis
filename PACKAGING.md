# Native packaging

JARVIS ships a single PyInstaller application and wraps it in native installers:

| Platform | Installer | Portable artifact |
| --- | --- | --- |
| Windows x64 | NSIS `.exe` | `.zip` |
| Debian/Ubuntu | `.deb` | `.tar.gz` |
| macOS | `.dmg` containing `JARVIS.app` | app bundle inside the DMG |

The application includes Python, its runtime packages, and Playwright Chromium.
The build does not download Python packages or browser binaries at first launch.

## Automated release

The `Native release` workflow runs unit tests and an executable smoke test on
Windows, Ubuntu, and macOS before it uploads artifacts. Pushing a tag matching
`v*` also creates a GitHub Release containing all native installers. A manual
workflow run builds the same artifacts without publishing a release.

## Local Windows build

```powershell
python -m pip install -r requirements-packaging.txt
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
python -m playwright install --no-shell chromium
pyinstaller jarvis.spec --clean --noconfirm
$env:JARVIS_CONFIG_DIR = "$env:TEMP\jarvis-smoke"
.\dist\JARVIS\JARVIS.exe --packaging-smoke-test
makensis.exe /DAPP_VERSION=0.1.0 /DSOURCE_DIR="$PWD\dist\JARVIS" /DOUTPUT_DIR="$PWD\artifacts" packaging\windows\JARVIS.nsi
```

## Local Linux build

```bash
sudo apt-get install -y dpkg-dev libportaudio2 portaudio19-dev
python -m pip install -r requirements-packaging.txt
PLAYWRIGHT_BROWSERS_PATH=0 python -m playwright install --with-deps --no-shell chromium
PLAYWRIGHT_BROWSERS_PATH=0 pyinstaller jarvis.spec --clean --noconfirm
JARVIS_CONFIG_DIR=/tmp/jarvis-smoke ./dist/JARVIS/JARVIS --packaging-smoke-test
packaging/linux/build_deb.sh dist/JARVIS 0.1.0 artifacts
```

## Local macOS build

```bash
brew install portaudio
python -m pip install -r requirements-packaging.txt
PLAYWRIGHT_BROWSERS_PATH=0 python -m playwright install --no-shell chromium
PLAYWRIGHT_BROWSERS_PATH=0 pyinstaller jarvis.spec --clean --noconfirm
JARVIS_CONFIG_DIR=/tmp/jarvis-smoke ./dist/JARVIS.app/Contents/MacOS/JARVIS --packaging-smoke-test
packaging/macos/build_dmg.sh dist/JARVIS.app 0.1.0 artifacts
```

## Runtime data

Install directories are treated as read-only. Credentials and the persistent
browser profile live in the current user's configuration directory:

- Windows: `%APPDATA%\JARVIS`
- macOS: `~/Library/Application Support/JARVIS`
- Linux: `${XDG_CONFIG_HOME:-~/.config}/jarvis`

`JARVIS_CONFIG_DIR` overrides this location for automation and smoke testing.
Uninstalling JARVIS intentionally leaves user credentials and browser state in
place so an upgrade or reinstall does not erase them.
