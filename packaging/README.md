# Packaging and release bundles

This directory holds the minimal packaging scaffold for the J.A.R.V.I.S bounty:

- `jarvis_launcher.spec` builds the main launcher executable
- `browser_client.spec` builds the browser automation helper as a separate executable
- `scripts/package.py` runs both builds and stages a platform-appropriate release bundle

## Local build

```bash
python -m pip install -r requirements.txt -r requirements-build.txt
python scripts/package.py
```

The script selects a native bundle layout automatically:

- macOS: `dist/releases/JARVIS.app`
- Windows: `dist/releases/JARVIS-windows-x86_64.zip`
- Linux: `dist/releases/JARVIS-linux-x86_64.tar.gz`

## Runtime behavior

Packaged builds keep the existing source behavior:

- `jarvis_web.html` and `jarvis_visual.html` are bundled as app assets
- `config.json` is stored in the user config directory when frozen
- `browserClient` is started as a sibling executable in the release bundle

## Notes

- Build artifacts are intentionally not committed.
- `config.json` remains ignored in version control.
