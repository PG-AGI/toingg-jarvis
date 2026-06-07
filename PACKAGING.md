# Cross-Platform Packaging

This release path stages the files needed to build JARVIS as a native desktop
artifact without changing runtime behavior.

## Local Smoke Test

```bash
python scripts/package_release.py --platform linux
python scripts/package_release.py --platform macos
python scripts/package_release.py --platform windows
```

Each command writes `dist/release/<platform>/release-manifest.json` and copies
the launcher, browser client, HTML assets, config template, and dependency
manifests into a clean staging directory.

## Build With PyInstaller

```bash
python -m pip install -r requirements-build.txt
python scripts/package_release.py --platform linux --build
```

The build uses `jarvis.spec`, which bundles:

- `jarvis_launcher.py` as the executable entry point.
- `jarvis_web.html` and `jarvis_visual.html`.
- `browserClient.py` and `native_file_manager.py`.
- `config.example.json`.
- User-facing setup docs.

## GitHub Actions

The `Package JARVIS` workflow runs on release tags and manual dispatch. It:

1. Installs Python dependencies.
2. Runs the staging script for the runner platform.
3. Runs PyInstaller from `jarvis.spec`.
4. Uploads both the staged manifest folder and built `dist` output as artifacts.

## Notes

- Code signing and installer-specific tools such as Inno Setup, NSIS, or DMG
  signing are intentionally left as a later release step because they require
  maintainer-owned certificates and secrets.
- The package builder can be run without PyInstaller, which gives maintainers a
  fast validation path for pull requests.
