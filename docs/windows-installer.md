# Windows installer (bounty #13 slice)

One-click Windows install path: PyInstaller one-dir bundle (`dist\JARVIS\JARVIS.exe`)
wrapped in an Inno Setup installer, built by `.github/workflows/build-windows.yml`.

## Install (end user)

1. Run `JARVIS-Setup-2.0.0-Windows.exe`.
2. Copy `config.example.json` to `config.json` (done automatically on first
   install) and fill in `TOKEN` / `CAMP_ID` (see README Data Requirements).
3. Install the browser engine once (not bundled, saves ~150 MB):
   `python -m playwright install chromium`
4. Optional, for microphone input: `pip install pipwin && pipwin install pyaudio`.
5. Launch JARVIS from the Start Menu. Say "Hey Jarvis".

## Build locally

```bat
pip install -r requirements.txt pyinstaller
pyinstaller jarvis.spec --noconfirm
dist\JARVIS\JARVIS.exe --version
dist\JARVIS\JARVIS.exe --help
dist\JARVIS\JARVIS.exe --browser-client --help
```

Installer (needs Inno Setup 6, `choco install innosetup`):

```bat
iscc installer\jarvis.iss
```

## Design notes

- Single exe: the browser-automation client runs as `JARVIS.exe --browser-client`,
  so the frozen launcher (`subprocess` spawn) needs no Python on the target.
- Frozen path handling (`sys._MEIPASS` / exe dir) only affects where bundled
  `jarvis_web.html` / `jarvis_visual.html` are found; runtime logic is unchanged.
- `config.json` is never overwritten by upgrades (`onlyifdoesntexist`).
- Budget guard: CI fails the build if the bundle exceeds 500 MB.

## Follow-ups (out of scope for this slice)

- Code-signing the exe/installer.
- Per-user `%APPDATA%\JARVIS\config.json` credential store for Program Files installs.
- Bundled Chromium (`PLAYWRIGHT_BROWSERS_PATH`) for fully offline setup.
- Linux `.deb` / macOS `.app` slices.
