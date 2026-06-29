# Packaging Toingg Jarvis

This repo can produce Windows, Linux, and macOS release artifacts with PyInstaller.

## Local Build

```bash
python -m pip install -r requirements-build.txt
python -m playwright install chromium
pyinstaller --clean --noconfirm jarvis_launcher.spec
python scripts/package_release.py --frozen-dist dist/toingg-jarvis --output artifacts
```

The final archive is written to `artifacts/toingg-jarvis-<platform>-<arch>.zip`.

## GitHub Actions

The `Package Toingg Jarvis` workflow runs on tags matching `v*` and by manual dispatch. It builds a PyInstaller bundle on:

- `ubuntu-latest`
- `macos-latest`
- `windows-latest`

Each run uploads one platform zip artifact.

## Artifact Layout

Each zip contains:

- a `toingg-jarvis/` PyInstaller bundle when the build produced one
- source fallback files for local debugging
- `run-toingg-jarvis.sh` or `run-toingg-jarvis.bat`
- `RELEASE_NOTES.txt`

The launcher prefers the frozen bundle and falls back to `python jarvis_launcher.py` if needed.
