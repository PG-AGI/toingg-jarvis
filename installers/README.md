# Native Cross-Platform Installers (`toingg-jarvis`)

This directory contains the automated packaging & native installer suite for **Toingg Jarvis** across Windows, Linux, and macOS (resolving Issue #13).

## Supported Target Packages

| Platform | Native Package Format | Tooling Used | Output Artifact |
| :--- | :--- | :--- | :--- |
| **Windows (x64)** | `.exe` Native Setup Installer (+ Portable `.zip` fallback) | PyInstaller + Inno Setup (`iscc`) | `dist/installers/toingg-jarvis-setup-<version>-windows-x64.exe` |
| **Linux (Debian/Ubuntu)** | `.deb` Debian Package (with `/usr/share/applications/toingg-jarvis.desktop`) | PyInstaller + `dpkg-deb` | `dist/installers/toingg-jarvis_<version>_amd64.deb` |
| **macOS (Universal/Arm64)** | `.app` Bundle + `.dmg` Disk Image | PyInstaller + `hdiutil` | `dist/installers/ToinggJarvis-<version>-macos.dmg` |

## Local Build Usage

```bash
pip install pyinstaller
python installers/build_installers.py --version 2.0.0
```

All generated installers and `SHA256SUMS.txt` are output to `dist/installers/`.

## Automated CI/CD Release Pipeline

The workflow `.github/workflows/release-installers.yml` automatically builds all 3 OS native installers on `windows-latest`, `ubuntu-latest`, and `macos-latest`, verifies all unit tests (`python -m unittest discover -v`), computes `SHA256SUMS.txt`, and publishes a versioned GitHub Release whenever a `v*` tag is pushed.
