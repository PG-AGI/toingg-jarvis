# Native installer packaging

This folder contains maintainer-facing templates for creating native JARVIS installers after a frozen application bundle has been produced.

The templates intentionally do not change runtime behavior. The GitHub Actions workflow template in `packaging/github-actions/package.yml` freezes the launcher with PyInstaller, stages the result under `dist/`, then calls the OS-specific installer template:

- Windows: `dist/JARVIS/`
- Linux: `dist/jarvis/`
- macOS: `dist/JARVIS.app`

For local builds, install the release dependencies first:

```bash
python -m pip install -r requirements.txt pyinstaller
python -m playwright install chromium
```

Then freeze the app:

```bash
pyinstaller packaging/pyinstaller/jarvis.spec --noconfirm
```

## Windows Inno Setup

1. Install Inno Setup.
2. Build or stage the Windows app into `dist/JARVIS/`.
3. Run:

```powershell
iscc packaging/windows/jarvis.iss
```

Output:

```text
dist/installers/JARVIS-Setup.exe
```

## Linux Debian package

1. Stage the Linux app into `dist/jarvis/`.
2. Run:

```bash
bash packaging/linux/build-deb.sh
```

Output:

```text
dist/installers/jarvis_0.1.0_amd64.deb
```

## macOS DMG

1. Stage the app bundle at `dist/JARVIS.app`.
2. Run:

```bash
bash packaging/macos/build-dmg.sh
```

Output:

```text
dist/installers/JARVIS-0.1.0.dmg
```

## Release workflow fit

These templates are designed to be called from a GitHub Actions matrix after PyInstaller or another freezer creates the platform-specific bundle. Signing and notarization can be added by injecting certificates and Apple credentials through GitHub Actions secrets.

To enable the included CI template, copy `packaging/github-actions/package.yml` into `.github/workflows/package.yml`.
