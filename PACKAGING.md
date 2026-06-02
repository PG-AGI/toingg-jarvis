# Packaging J.A.R.V.I.S

This repository includes a packaging scaffold for creating user-friendly release artifacts on Windows, macOS, and Linux.

## Local build

```bash
python -m pip install -r requirements.txt pyinstaller
python -m playwright install chromium
python -m PyInstaller packaging/pyinstaller/JARVIS.spec --noconfirm --clean
```

The PyInstaller output is written to `dist/JARVIS/`.

## macOS `.app`

```bash
python packaging/macos/make_app.py dist/JARVIS/JARVIS dist/JARVIS.app
```

The generated app bundle includes microphone permission metadata. Maintainers can later add signing and notarization before public distribution.

## Linux `.deb`

```bash
VERSION=0.1.0 bash packaging/linux/make_deb.sh dist/JARVIS dist/packages
```

This creates `dist/packages/jarvis_0.1.0_amd64.deb` and links `/usr/bin/jarvis` to the installed launcher.

## Windows installer

The workflow always uploads a Windows zip. If Inno Setup is available on the runner, `packaging/windows/JARVIS.iss` can build `JARVIS-Setup.exe` from `dist/JARVIS/`.

## GitHub Actions release flow

Copy `packaging/github-actions/package.yml` to `.github/workflows/package.yml` in a branch with workflow-write permissions. The `Package JARVIS` workflow runs on:

- manual `workflow_dispatch`
- version tags matching `v*`

It builds an OS matrix and uploads artifacts for each runner. Signing and notarization are intentionally left as maintainer-controlled steps because they require private certificates and should not be stored in the repository.
