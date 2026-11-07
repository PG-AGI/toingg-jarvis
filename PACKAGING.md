# Cross-Platform Packaging & Native Installers

This document describes how to build native installer packages and standalone desktop bundles for **Windows**, **Linux (Debian/Ubuntu)**, and **macOS**.

## Supported Target Packages

| Platform | Output Artifacts | Description |
| :--- | :--- | :--- |
| **Windows** | `toingg-jarvis.iss` (Inno Setup), `toingg-jarvis.nsi` (NSIS), `toingg-jarvis-<version>-windows-portable.zip` | Native Windows `.exe` installer scripts with Desktop/Start Menu shortcuts plus portable distribution archive |
| **Linux** | `toingg-jarvis_<version>_amd64.deb` | Debian/Ubuntu `.deb` installer package installing `/usr/bin/toingg-jarvis`, `/opt/toingg-jarvis/`, and `/usr/share/applications/toingg-jarvis.desktop` |
| **macOS** | `ToinggJarvis.app`, `ToinggJarvis-<version>-macos-app.zip` | Native macOS `.app` bundle with `Contents/Info.plist` (`NSMicrophoneUsageDescription`), `Contents/MacOS/toingg-jarvis`, and `Contents/Resources/` |

## Building Native Packages Locally

Run the pure-Python installer builder to generate packages for a specific OS or all platforms at once:

```text
python -m packaging.installer_builder --target all --output-dir dist/installers
```

Or target a single platform:

```text
python -m packaging.installer_builder --target linux --output-dir dist/installers
python -m packaging.installer_builder --target macos --output-dir dist/installers
python -m packaging.installer_builder --target windows --output-dir dist/installers
```

## Building Standalone Frozen Binaries with PyInstaller

To freeze the launcher and bundled HTML/Python assets into a standalone executable directory:

```text
pip install -r requirements.txt
pyinstaller packaging/jarvis.spec --noconfirm
```

## Runtime Asset & User Config Resolution

- `resolve_bundle_root()` and `resolve_runtime_asset()` in `packaging/installer_builder.py` automatically detect frozen PyInstaller environments (`sys._MEIPASS`) as well as standard source and `/opt/toingg-jarvis` installations.
- `resolve_user_config_dir()` resolves OS-appropriate writable configuration directories:
  - **Windows**: `%APPDATA%\ToinggJarvis`
  - **macOS**: `~/Library/Application Support/ToinggJarvis`
  - **Linux**: `$XDG_CONFIG_HOME/toingg-jarvis` (defaulting to `~/.config/toingg-jarvis`)

## Automated GitHub Actions Release Pipeline

The workflow in `.github/workflows/release-packaging.yml` runs across `ubuntu-latest`, `windows-latest`, and `macos-latest`:
1. Executes the packaging test suite (`python -m unittest discover -v -p "test_packaging*.py"`).
2. Builds platform-specific native installer packages (`dist/installers/`).
3. Uploads workflow artifacts and attaches versioned packages automatically when a `v*` tag is pushed.
