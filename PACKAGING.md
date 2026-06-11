# Packaging J.A.R.V.I.S

This repository ships native packaging helpers for all supported desktop
platforms. The generated packages bundle the application source, launchers, and
dependency manifest; the first launch still installs Python packages and
Playwright Chromium just like the existing `JARVIS.bat` and `JARVIS.command`
entrypoints.

## GitHub Actions

Run **Package native installers** from the Actions tab, or push a version tag
such as `v1.0.0`. The workflow uploads:

- `JARVIS-Setup.exe` for Windows
- `jarvis_<version>_amd64.deb` for Debian/Ubuntu
- `JARVIS.app.zip` and `JARVIS.dmg` for macOS

## Local Builds

### Windows

Install Inno Setup, then run:

```powershell
iscc packaging\windows\JARVIS.iss
```

The installer is written to `packaging/windows/Output/JARVIS-Setup.exe`.

### Linux

Run the Debian packaging script from the repository root:

```bash
bash packaging/linux/build-deb.sh
```

The `.deb` file is written to `dist/linux`.

### macOS

Run the macOS packaging script from the repository root:

```bash
bash packaging/macos/build-macos.sh
```

The `.app` bundle and `.dmg` are written to `dist/macos`.
