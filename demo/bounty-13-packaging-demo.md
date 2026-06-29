# Bounty #13 Packaging Demo

This PR adds the release path expected by the bounty:

```bash
python -m pip install -r requirements-build.txt
python -m playwright install chromium
pyinstaller --clean --noconfirm jarvis_launcher.spec
python scripts/package_release.py --frozen-dist dist/toingg-jarvis --output artifacts
```

Expected output:

```text
artifacts/
└── toingg-jarvis-<platform>-<arch>.zip
```

The GitHub Actions workflow runs the same steps on Windows, macOS, and Linux and uploads the zip artifacts for each platform.
