# Packaging Toingg Jarvis

Toingg Jarvis can be staged as native desktop artifacts with PyInstaller.

## Local build

```bash
python -m pip install -r requirements-build.txt
python scripts/package_app.py
```

The build creates:

- `artifacts/toingg-jarvis-<platform>/`
- `artifacts/toingg-jarvis-<platform>.zip`

The staged folder includes the launcher executable, web UI assets, sample config,
README, and a tiny launch script for the current platform.

## CI release artifacts

The `package` GitHub Actions workflow runs on manual dispatch and release tags.
It builds on:

- Windows
- macOS
- Linux

Each job uploads a zipped artifact named `toingg-jarvis-<platform>.zip`.

## Platform notes

- Windows output includes `toingg-jarvis.exe` and `Launch Toingg Jarvis.bat`.
- macOS/Linux output includes `toingg-jarvis` and `launch-toingg-jarvis.sh`.
- Code signing and notarization are intentionally left to maintainers because
  they require private signing credentials.
