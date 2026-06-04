# Packaging JARVIS

This project can be packaged as a single-file desktop launcher with PyInstaller. The package includes the launcher, browser client, visual HTML assets, web terminal HTML, and example config.

## Local Build

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/build_package.py
```

The build writes a platform-specific zip under `package/`, for example:

```text
package/jarvis-darwin-arm64.zip
package/jarvis-linux-x86_64.zip
package/jarvis-windows-amd64.zip
```

## GitHub Actions

The `package.yml` workflow builds artifacts on Windows, macOS, and Linux. It installs Python dependencies, installs Chromium for Playwright, runs the packaging script, and uploads the generated zip package from each runner.

## Notes

- The package is unsigned. Maintainers can add code signing, notarization, or installer generation after validating the artifact layout.
- Playwright browser installation is still required during packaging so bundled browser automation dependencies are available.
- End users should copy `config.example.json` to `config.json` next to the executable and add their Toingg token before launching.
